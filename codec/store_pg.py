"""PgStore — PGVector-backed StoreBackend (M4, D67 commodity-rails).

Division of labor: Postgres/pgvector owns the VECTORS (storage, scoring,
later HNSW); the symbolic sidecar (ids / content_ids / texts / shadowed)
is mirrored in-process because the walker reads it per hop (set algebra on
eids), and round-tripping SQL per hand-off would be silly. Both live
durably in the table; the mirror is loaded once at attach.

Semantics contract (identical to MemoryStore/PQStore, D33/D55/D68):
  - hybrid score = dense inner product + id_weight * |q∩ids|/|q|
  - supersede: vector + address-ids inherit; content_ids NEVER union
  - exhaustion returns [] (never a placeholder)
  - indices are 0-based insertion order, stable across reconnects

Parity is proven by battery (K6/J4 through this class), never assumed —
the D67 caution, in code form.
"""

from __future__ import annotations

import numpy as np

from codec.memory_store import id_tokens

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS {t} (
    idx         integer PRIMARY KEY,
    z           vector({dim}),
    ids         text[] NOT NULL DEFAULT '{{}}',
    content_ids text[] NOT NULL DEFAULT '{{}}',
    body        text NOT NULL DEFAULT '',
    shadowed    boolean NOT NULL DEFAULT false,
    -- Covalence Lesson 4 (D69): federation-ready columns cost nothing now
    -- and are near-impossible to retrofit. UNUSED by current semantics.
    clearance   smallint NOT NULL DEFAULT 0,
    valid_from  timestamptz,
    valid_until timestamptz,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    invalidated_by integer,
    source_ref  text
);
"""


class PgStore:
    def __init__(self, dsn: str = "host=/var/run/postgresql dbname=foundation",
                 table: str = "entries", dim: int = 1024,
                 fresh: bool = False):
        import psycopg
        from pgvector.psycopg import register_vector
        self.dim = dim
        self.table = table
        self._conn = psycopg.connect(dsn, autocommit=True)
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)   # after the extension exists
        with self._conn.cursor() as cur:
            if fresh:
                cur.execute(f"DROP TABLE IF EXISTS {table}")
            cur.execute(DDL.format(t=table, dim=dim))
        # in-process symbolic mirror (authoritative copy lives in PG)
        self.ids: list[set] = []
        self.content_ids: list[set] = []
        self.texts: list[str] = []
        self.shadowed: list[bool] = []
        self._load_mirror()

    def _load_mirror(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT idx, ids, content_ids, body, shadowed "
                        f"FROM {self.table} ORDER BY idx")
            for idx, ids, cids, body, sh in cur.fetchall():
                assert idx == len(self.texts), "index gap in table"
                self.ids.append(set(ids))
                self.content_ids.append(set(cids))
                self.texts.append(body)
                self.shadowed.append(sh)

    # ---- writes -----------------------------------------------------------
    def add(self, z: np.ndarray, identities: list[str], text: str) -> int:
        z = np.asarray(z, np.float32)
        if z.shape != (self.dim,):
            raise ValueError(f"expected ({self.dim},), got {z.shape}")
        z = z / (np.linalg.norm(z) + 1e-12)
        idx = len(self.texts)
        toks = id_tokens(identities)
        with self._conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self.table} (idx, z, ids, content_ids, body) "
                f"VALUES (%s, %s, %s, %s, %s)",
                (idx, z, sorted(toks), sorted(toks), text))
        self.ids.append(toks)
        self.content_ids.append(set(toks))
        self.texts.append(text)
        self.shadowed.append(False)
        return idx

    def add_batch(self, Z, ids_list, texts) -> None:
        Z = np.asarray(Z, np.float32)
        Z = Z / (np.linalg.norm(Z, axis=1, keepdims=True) + 1e-12)
        rows = []
        for z, ids_, t in zip(Z, ids_list, texts):
            idx = len(self.texts)
            toks = ids_ if isinstance(ids_, set) else id_tokens(ids_)
            rows.append((idx, z, sorted(toks), sorted(toks), t))
            self.ids.append(set(toks))
            self.content_ids.append(set(toks))
            self.texts.append(t)
            self.shadowed.append(False)
        with self._conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO {self.table} (idx, z, ids, content_ids, body) "
                f"VALUES (%s, %s, %s, %s, %s)", rows)

    def shadow(self, idx: int) -> None:
        self.shadowed[idx] = True
        with self._conn.cursor() as cur:
            cur.execute(f"UPDATE {self.table} SET shadowed=true "
                        f"WHERE idx=%s", (idx,))

    def supersede(self, old_idx: int, new_idx: int) -> None:
        self.ids[new_idx] = self.ids[new_idx] | self.ids[old_idx]
        self.shadowed[old_idx] = True
        with self._conn.cursor() as cur:
            cur.execute(f"UPDATE {self.table} n SET z = o.z, "
                        f"ids = (SELECT array_agg(DISTINCT u) FROM unnest(n.ids || o.ids) u) "
                        f"FROM {self.table} o WHERE n.idx=%s AND o.idx=%s",
                        (new_idx, old_idx))
            cur.execute(f"UPDATE {self.table} SET shadowed=true WHERE idx=%s",
                        (old_idx,))

    # ---- reads ------------------------------------------------------------
    def vec(self, idx: int) -> np.ndarray:
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT z FROM {self.table} WHERE idx=%s", (idx,))
            v = cur.fetchone()[0]
            if isinstance(v, np.ndarray):
                return v.astype(np.float32)
            return np.asarray(v.to_list(), np.float32)   # pgvector Vector

    def query(self, z_q, query_ids=None, k: int = 5, id_weight: float = 0.5,
              demote_ids=None, exclude=None):
        if not self.texts:
            return []
        z_q = np.asarray(z_q, np.float32)
        z_q = z_q / (np.linalg.norm(z_q) + 1e-12)
        parts = [f"-(z <#> %s)"]          # <#> is negative inner product
        params: list = [z_q]
        if query_ids and id_weight:
            qa = sorted(set(query_ids))
            parts.append(
                f"+ %s * (SELECT count(*) FROM unnest(ids) t "
                f"WHERE t = ANY(%s))::float / %s")
            params += [id_weight, qa, max(len(qa), 1)]
        if demote_ids and id_weight:
            da = sorted(set(demote_ids))
            parts.append(
                f"- %s * (SELECT count(*) FROM unnest(ids) t "
                f"WHERE t = ANY(%s))::float / %s")
            params += [id_weight, da, max(len(da), 1)]
        score = " ".join(parts)
        where = "NOT shadowed"
        if exclude:
            where += " AND NOT (idx = ANY(%s))"
        sql = (f"SELECT idx, {score} AS s, body FROM {self.table} "
               f"WHERE {where} ORDER BY s DESC LIMIT %s")
        if exclude:
            params.append(sorted(exclude))
        params.append(k)
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return [(int(i), float(s), b) for i, s, b in cur.fetchall()]

    # ---- maintenance ------------------------------------------------------
    def build_hnsw(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {self.table}_hnsw ON "
                        f"{self.table} USING hnsw (z vector_ip_ops)")

    @classmethod
    def from_store(cls, store, **kw) -> "PgStore":
        pg = cls(fresh=True, **kw)
        Z = np.stack([store.vec(i) for i in range(len(store.texts))])
        pg.add_batch(Z, [set(x) for x in store.ids], list(store.texts))
        pg.content_ids = [set(x) for x in store.content_ids]
        for i, sh in enumerate(store.shadowed):
            if sh:
                pg.shadow(i)
        with pg._conn.cursor() as cur:
            for i in range(len(store.texts)):
                cur.execute(f"UPDATE {pg.table} SET ids=%s, content_ids=%s "
                            f"WHERE idx=%s",
                            (sorted(store.ids[i]),
                             sorted(store.content_ids[i]), i))
        pg.ids = [set(x) for x in store.ids]
        return pg
