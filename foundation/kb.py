"""Knowledge layer: claims -> registry individuation -> store rows ->
answer surfaces (ask / chain / edit / views / brief / status).

Semantics carried over from the measured stack, unchanged:
- identity != surface form: eids minted by the closed-form resolver,
  provenance batch = source page (D49/D52);
- address/content id separation at supersession (D55): supersede unions
  ADDRESS ids only, content never;
- functional-pid disagreement is a CONFLICT surface, never a silent pick
  (D74/D78 set); multi-valued pids accumulate;
- answers are store entries + citations; briefs render at evidence
  strength (quote-never-reconstruct, D81).

Backends: "memory" (tests/CI, no persistence) or "pg" (PgStore primary,
claims mirrored in a companion table; registry rebuilt deterministically
from the claims log on open — no pickled state).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from codec.brief import FUNCTIONAL_PIDS, canon_value, subject_brief
from codec.individuation import EntityRegistry, is_value
from codec.memory_store import MemoryStore, id_tokens

_norm = lambda s: re.sub(r"\s+", " ",
                         re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()

CLAIMS_DDL = """
CREATE TABLE IF NOT EXISTS {t}_claims (
    idx      integer PRIMARY KEY,
    subject  text NOT NULL,
    subj_eid text NOT NULL,
    pid      text NOT NULL,
    object   text NOT NULL,
    obj_eid  text,
    page     text NOT NULL,
    sid      text NOT NULL
);
"""


class KB:
    def __init__(self, backend: str = "pg",
                 dsn: str = "host=/var/run/postgresql dbname=foundation",
                 table: str = "poc", fresh: bool = False):
        self.backend = backend
        self.reg = EntityRegistry()
        self.claims: list[dict] = []          # row-aligned with store idx
        self._canonical: dict[str, str] = {}  # form -> eid (D82)
        self._enc = None
        if backend == "pg":
            from codec.store_pg import PgStore
            self.store = PgStore(dsn=dsn, table=table, fresh=fresh)
            self._conn = self.store._conn
            with self._conn.cursor() as cur:
                if fresh:
                    cur.execute(f"DROP TABLE IF EXISTS {table}_claims")
                cur.execute(CLAIMS_DDL.format(t=table))
                cur.execute(f"SELECT idx, subject, subj_eid, pid, object, "
                            f"obj_eid, page, sid FROM {table}_claims "
                            f"ORDER BY idx")
                for r in cur.fetchall():
                    self.claims.append(dict(zip(
                        ("idx", "subject", "subj_eid", "pid", "object",
                         "obj_eid", "page", "sid"), r)))
            self._replay_registry()
        else:
            self.store = MemoryStore()
            self._conn = None

    # ---- registry replay (deterministic; claims log is the truth) ---------
    def _replay_registry(self) -> None:
        for c in self.claims:
            self._resolve(c["subject"], c["pid"], c["object"], c["page"],
                          record=False)

    def _record(self, eid: str, form: str, pid: str, role: str,
                other: str | None, z) -> None:
        """resolve_write's bookkeeping for a pre-resolved eid (canonical
        hit) — registry API stays frozen for the probes."""
        e = self.reg._get(eid)
        e.forms.add(form)
        e.form_tokens |= id_tokens([form])
        self.reg.by_form.setdefault(form, set()).add(e.eid)
        e.slots[(pid, role)] = e.slots.get((pid, role), 0) + 1
        if other is not None:
            e.neighbors.add(other)
        if z is not None:
            e.anchor = (np.asarray(z, np.float32).copy()
                        if e.anchor is None
                        else (e.anchor * e.n_anchor + z) / (e.n_anchor + 1))
            e.n_anchor += 1

    def _entity(self, form: str, pid: str, role: str, other: str | None,
                page: str, z) -> str:
        """Resolve a mention with TITLE-ENTITY CANONICALIZATION (D82):
        the entity first seen on its own page (form == page title) is
        canonical for that form; later same-form mentions absorb into it
        regardless of functional disagreement — for attributed corpora,
        disagreement is a Track I CONFLICT surface, not individual
        fission (the D49 gate's closed-world prior inverts here).
        Distinct same-name individuals still separate via Wikipedia's
        disambiguated titles (different forms)."""
        canon = self._canonical.get(form)
        if canon is not None:
            self._record(canon, form, pid, role, other, z)
            eid = self.reg._get(canon).eid
        else:
            eid = self.reg.resolve_write(form, pid, role, other, z,
                                         functional=False, batch=page)
        if form == page:
            self._canonical.setdefault(form, eid)
        return eid

    def _resolve(self, subject: str, pid: str, obj: str, page: str,
                 z: np.ndarray | None = None, record: bool = True):
        """Individuate one claim (write-time). Returns (subj_eid, obj_eid,
        id-token set for the store row)."""
        fn = pid in FUNCTIONAL_PIDS
        if is_value(obj):
            se = self._entity(subject, pid, "s",
                              "v:" + obj.replace(",", ""), page, z)
            return se, None, {se} | id_tokens([obj]) | {f"p:{pid}"}
        se = self._entity(subject, pid, "s", None, page, z)
        oe = self._entity(obj, pid, "o", se, page, z)
        if fn:
            e = self.reg._get(se)
            held = e.functional.get((pid, "s"))
            e.functional[(pid, "s")] = held if held is not None else oe
        self.reg._get(se).neighbors.add(oe)
        return se, oe, {se, oe, f"p:{pid}"}

    # ---- ingest ------------------------------------------------------------
    def _encoder(self):
        if self._enc is None:
            from codec.encode import M3Encoder
            self._enc = M3Encoder()
        return self._enc

    def _embed(self, texts: list[str]) -> np.ndarray:
        dense, _ = self._encoder().encode(texts, sparse=False)
        return np.asarray(dense, np.float32)

    def ingest_shards(self, shard_dir: str | Path,
                      embed: bool = True) -> dict:
        """Load extracted-claim shards (out_*.jsonl with pid, subject,
        object, statement, page). Vetoed rows (pid null) are skipped —
        the veto happened upstream and stays honored."""
        rows = []
        for f in sorted(Path(shard_dir).glob("out_*.jsonl")):
            for ln, line in enumerate(f.read_text().splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("pid") and d.get("subject") and d.get("object") \
                        and d.get("statement"):
                    rows.append({"subject": str(d["subject"]),
                                 "pid": str(d["pid"]),
                                 "object": str(d["object"]),
                                 "statement": str(d["statement"]),
                                 "page": str(d.get("page", "?")),
                                 "sid": f"{f.name}:{ln}"})
        # canonical-page claims first: the title entity must exist before
        # off-page mentions of the same form try to absorb into it (D82)
        rows.sort(key=lambda r: r["subject"] != r["page"])
        Z = (self._embed([r["statement"] for r in rows])
             if embed and rows else
             np.zeros((len(rows), getattr(self.store, "dim", 1024)),
                      np.float32))
        new = []
        for r, z in zip(rows, Z):
            se, oe, toks = self._resolve(r["subject"], r["pid"],
                                         r["object"], r["page"], z)
            idx = self.store.add(np.asarray(z, np.float32), [],
                                 r["statement"])
            self.store.ids[idx] = set(toks)
            if hasattr(self.store, "content_ids"):
                self.store.content_ids[idx] = set(toks)
            c = {"idx": idx, "subject": r["subject"], "subj_eid": se,
                 "pid": r["pid"], "object": r["object"], "obj_eid": oe,
                 "page": r["page"], "sid": r["sid"]}
            self.claims.append(c)
            new.append(c)
        if self._conn is not None and new:
            with self._conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO {self.store.table}_claims (idx, subject, "
                    f"subj_eid, pid, object, obj_eid, page, sid) VALUES "
                    f"(%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(c["idx"], c["subject"], c["subj_eid"], c["pid"],
                      c["object"], c["obj_eid"], c["page"], c["sid"])
                     for c in new])
            for c in new:      # persist the token sets set post-add
                with self._conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE {self.store.table} SET ids=%s, "
                        f"content_ids=%s, source_ref=%s WHERE idx=%s",
                        (sorted(self.store.ids[c["idx"]]),
                         sorted(self.store.ids[c["idx"]]),
                         c["page"], c["idx"]))
        return {"ingested": len(new),
                "eids": len(self.reg.entities),
                "pages": len({c["page"] for c in new})}

    # ---- shared lookups ------------------------------------------------------
    def _live(self, c: dict) -> bool:
        return not self.store.shadowed[c["idx"]]

    def _claims_for(self, eid: str, pid: str | None = None) -> list[dict]:
        out = [c for c in self.claims
               if c["subj_eid"] == eid and self._live(c)]
        return [c for c in out if c["pid"] == pid] if pid else out

    def resolve_subject(self, form: str, pid: str | None = None):
        """Registry candidates; relation-existence gate when pid given."""
        cands = self.reg.resolve_query(form, pid, "s") if pid \
            else [c.eid for c in self.reg.candidates(form)]
        return sorted(set(self.reg._get(e).eid for e in cands))

    # ---- answer surfaces ------------------------------------------------------
    def ask(self, subject: str, pid: str) -> dict:
        """Honest statuses: answered / ambiguous / abstain / conflict."""
        eids = self.resolve_subject(subject, pid)
        if not eids:
            known = self.resolve_subject(subject)
            return {"status": "abstain",
                    "reason": (f"no stored {pid} claims for known entity "
                               f"{subject!r}" if known else
                               f"unknown entity {subject!r}"),
                    "answers": []}
        if len(eids) > 1:
            return {"status": "ambiguous",
                    "reason": f"{subject!r} matches {len(eids)} distinct "
                              f"individuals — qualify the question",
                    "candidates": [
                        {"eid": e,
                         "sample": [c["object"] for c in
                                    self._claims_for(e, pid)][:3]}
                        for e in eids],
                    "answers": []}
        cl = self._claims_for(eids[0], pid)
        if not cl:
            return {"status": "abstain",
                    "reason": f"entity known but no live {pid} claim",
                    "answers": []}
        objs = defaultdict(list)
        for c in cl:
            key = canon_value(c["object"]) if pid in FUNCTIONAL_PIDS \
                else _norm(c["object"])
            objs[key].append(c)
        if pid in FUNCTIONAL_PIDS and len(objs) > 1:
            return {"status": "conflict",
                    "reason": f"{pid} is functional but sources disagree",
                    "answers": [{"object": v[0]["object"],
                                 "sources": sorted({x["page"] for x in v}),
                                 "citations": [x["sid"] for x in v]}
                                for v in objs.values()]}
        return {"status": "answered",
                "answers": [{"object": v[0]["object"],
                             "sources": sorted({x["page"] for x in v}),
                             "citations": [x["sid"] for x in v]}
                            for v in objs.values()]}

    def chain(self, subject: str, pids: list[str]) -> dict:
        """Multi-hop with symbolic identity hand-off (D26/D27): each hop's
        object eids become the next hop's subjects. Statuses propagate."""
        frontier = [(subject, None)]
        trace = []
        for hop, pid in enumerate(pids):
            nxt, answers = [], []
            for form, eid in frontier:
                r = self.ask(form, pid)
                trace.append({"hop": hop, "subject": form, "pid": pid,
                              "status": r["status"]})
                if r["status"] != "answered":
                    if len(frontier) == 1:
                        return {"status": r["status"], "hop": hop,
                                "detail": r, "trace": trace, "answers": []}
                    continue
                answers.extend(r["answers"])
                for a in r["answers"]:
                    nxt.append((a["object"], None))
            if not nxt and hop < len(pids) - 1:
                return {"status": "abstain", "hop": hop,
                        "reason": "chain broke: no entity answers to hand "
                                  "off", "trace": trace, "answers": []}
            frontier = nxt or frontier
            last = answers
        return {"status": "answered" if last else "abstain",
                "answers": last, "trace": trace}

    def edit(self, subject: str, pid: str, new_object: str,
             source: str = "user:edit") -> dict:
        """Supersede: new claim row; every live same-(eid,pid) row is
        superseded (address ids union per D55 — PgStore.supersede owns
        that semantics). Subject resolution honors provenance (D49)."""
        eids = self.resolve_subject(subject, pid) \
            or self.resolve_subject(subject)
        if not eids:
            return {"status": "abstain",
                    "reason": f"unknown entity {subject!r} — refusing to "
                              f"mint on edit"}
        if len(eids) > 1:
            return {"status": "ambiguous",
                    "reason": f"{len(eids)} candidates; qualify"}
        eid = eids[0]
        old = self._claims_for(eid, pid)
        stmt = f"{subject} ({pid}): {new_object} [per {source}]"
        z = (self._embed([stmt])[0]
             if self.backend == "pg" else
             np.zeros(getattr(self.store, "dim", 1024), np.float32))
        se, oe, toks = self._resolve(subject, pid, new_object, source, z)
        idx = self.store.add(np.asarray(z, np.float32), [], stmt)
        self.store.ids[idx] = set(toks)
        if hasattr(self.store, "content_ids"):
            self.store.content_ids[idx] = set(toks)
        c = {"idx": idx, "subject": subject, "subj_eid": se, "pid": pid,
             "object": new_object, "obj_eid": oe, "page": source,
             "sid": f"edit:{idx}"}
        self.claims.append(c)
        if self._conn is not None:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {self.store.table}_claims (idx, subject, "
                    f"subj_eid, pid, object, obj_eid, page, sid) VALUES "
                    f"(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (c["idx"], c["subject"], c["subj_eid"], c["pid"],
                     c["object"], c["obj_eid"], c["page"], c["sid"]))
                cur.execute(
                    f"UPDATE {self.store.table} SET ids=%s, content_ids=%s,"
                    f" source_ref=%s WHERE idx=%s",
                    (sorted(toks), sorted(toks), source, idx))
        for o in old:
            self.store.supersede(o["idx"], idx)
        return {"status": "edited", "superseded": [o["idx"] for o in old],
                "new_idx": idx,
                "ripple": {"eid": eid,
                           "live_claims": len(self._claims_for(eid))}}

    def views(self, subject: str, pid: str | None = None) -> dict:
        """'According to X' — live claims grouped by source page."""
        eids = self.resolve_subject(subject, pid)
        if len(eids) != 1:
            return {"status": "ambiguous" if eids else "abstain",
                    "views": {}}
        by_page = defaultdict(list)
        for c in self._claims_for(eids[0], pid):
            by_page[c["page"]].append(
                {"pid": c["pid"], "object": c["object"], "sid": c["sid"]})
        return {"status": "answered", "eid": eids[0],
                "views": dict(sorted(by_page.items()))}

    def brief(self, subject: str) -> dict:
        eids = self.resolve_subject(subject)
        pool = [
            {"subject": subject, "pid": c["pid"], "object": c["object"],
             "statement": self.store.texts[c["idx"]], "page": c["page"],
             "sid": c["sid"]}
            for e in eids for c in self._claims_for(e)]
        return subject_brief(subject, pool)

    def status(self) -> dict:
        live = sum(1 for c in self.claims if self._live(c))
        return {"backend": self.backend,
                "claims": len(self.claims), "live": live,
                "shadowed": len(self.claims) - live,
                "eids": len(self.reg.entities),
                "pages": len({c["page"] for c in self.claims}),
                "pids": len({c["pid"] for c in self.claims})}
