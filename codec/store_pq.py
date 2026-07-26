"""PQStore — product-quantized store engine (L3, from J2b's measured price
list: S=128 subvectors × 256 centroids = 1024 bits/entry, retrieval-lossless
on the interface metrics; D53).

Drop-in for MemoryStore.query/ids/content_ids/texts/shadowed as consumed by
ChannelWalker — the walker does not change. Vectors live as uint8 codes
(60× smaller than fp32); scoring is ADC (asymmetric distance): the query
stays fp32, per-subvector dot-product LUTs are built once per query, and
entry scores are LUT gathers — O(N·S) byte-gathers, GPU- or numpy-backed.

Supersession semantics identical to MemoryStore (address inheritance via
code copy + id union; content_ids never unioned — D55).
"""

from __future__ import annotations

import numpy as np

from codec.memory_store import id_tokens


class PQStore:
    def __init__(self, codebooks: np.ndarray):
        """codebooks: [S, K, d_sub] float32 (from fit_codebooks)."""
        self.books = codebooks.astype(np.float32)
        self.S, self.K, self.dsub = codebooks.shape
        self.dim = self.S * self.dsub
        self.codes: np.ndarray | None = None          # [N, S] uint8
        self.ids: list[set] = []
        self.content_ids: list[set] = []
        self.texts: list[str] = []
        self.shadowed: list[bool] = []
        self._torch = None

    # ---- construction ----------------------------------------------------
    @classmethod
    def fit_codebooks(cls, X: np.ndarray, S: int = 128, K: int = 256,
                      seed: int = 0) -> np.ndarray:
        from sklearn.cluster import MiniBatchKMeans
        d = X.shape[1] // S
        books = np.empty((S, K, d), np.float32)
        for s in range(S):
            km = MiniBatchKMeans(n_clusters=K, random_state=seed,
                                 batch_size=1024, n_init=3, max_iter=100)
            km.fit(X[:, s * d:(s + 1) * d])
            books[s] = km.cluster_centers_
        return books

    def encode(self, Z: np.ndarray) -> np.ndarray:
        Z = np.asarray(Z, np.float32)
        if Z.ndim == 1:
            Z = Z[None]
        codes = np.empty((len(Z), self.S), np.uint8)
        for s in range(self.S):
            seg = Z[:, s * self.dsub:(s + 1) * self.dsub]
            d2 = ((seg[:, None, :] - self.books[s][None]) ** 2).sum(-1)
            codes[:, s] = d2.argmin(1).astype(np.uint8)
        return codes

    def add(self, z: np.ndarray, identities: list[str], text: str) -> int:
        z = np.asarray(z, np.float32)
        if z.shape != (self.dim,):
            raise ValueError(f"expected ({self.dim},), got {z.shape}")
        z = z / (np.linalg.norm(z) + 1e-12)
        c = self.encode(z)
        self.codes = c if self.codes is None else \
            np.concatenate([self.codes, c])
        toks = id_tokens(identities)
        self.ids.append(toks)
        self.content_ids.append(set(toks))
        self.texts.append(text)
        self.shadowed.append(False)
        return len(self.texts) - 1

    def add_batch(self, Z: np.ndarray, ids_list, texts) -> None:
        c = self.encode(Z)
        self.codes = c if self.codes is None else \
            np.concatenate([self.codes, c])
        for ids_, t in zip(ids_list, texts):
            toks = ids_ if isinstance(ids_, set) else id_tokens(ids_)
            self.ids.append(set(toks))
            self.content_ids.append(set(toks))
            self.texts.append(t)
            self.shadowed.append(False)

    @classmethod
    def from_store(cls, store, codebooks) -> "PQStore":
        pq = cls(codebooks)
        pq.add_batch(store.Z, [set(x) for x in store.ids], list(store.texts))
        pq.content_ids = [set(x) for x in store.content_ids]
        pq.shadowed = list(store.shadowed)
        return pq

    # ---- supersession (D33/D55 semantics) ---------------------------------
    def shadow(self, idx: int) -> None:
        self.shadowed[idx] = True

    def supersede(self, old_idx: int, new_idx: int) -> None:
        self.codes[new_idx] = self.codes[old_idx]     # address inheritance
        self.ids[new_idx] = self.ids[new_idx] | self.ids[old_idx]
        self.shadowed[old_idx] = True                 # content_ids untouched

    # ---- query (ADC) -------------------------------------------------------
    def _scores(self, z_q: np.ndarray) -> np.ndarray:
        z_q = np.asarray(z_q, np.float32)
        lut = np.einsum("skd,sd->sk", self.books,
                        z_q.reshape(self.S, self.dsub))     # [S, K]
        try:
            import torch
            if torch.cuda.is_available():
                if self._torch is None or \
                        self._torch[0].shape[0] != len(self.codes):
                    self._torch = (torch.tensor(self.codes,
                                                device="cuda").long(), None)
                lut_t = torch.tensor(lut, device="cuda")
                sc = lut_t.gather(  # [N, S] gather over K per subvector
                    1, self._torch[0].T).sum(0)
                return sc.float().cpu().numpy()
        except Exception:
            pass
        out = np.zeros(len(self.codes), np.float32)
        for s in range(self.S):
            out += lut[s][self.codes[:, s]]
        return out

    def query(self, z_q, query_ids=None, k: int = 5, id_weight: float = 0.5,
              demote_ids=None, exclude=None):
        if self.codes is None or not len(self.codes):
            return []
        sc = self._scores(z_q)
        if query_ids and id_weight:
            qi = set(query_ids)
            ov = np.fromiter((len(qi & e) / len(qi) for e in self.ids),
                             np.float32, len(self.ids))
            sc = sc + id_weight * ov
        if demote_ids and id_weight:
            di = set(demote_ids)
            ov = np.fromiter((len(di & e) / max(len(di), 1)
                              for e in self.ids), np.float32, len(self.ids))
            sc = sc - id_weight * ov
        sc = np.where(np.array(self.shadowed), -np.inf, sc)
        if exclude:
            sc[list(exclude)] = -np.inf
        top = np.argpartition(-sc, min(k, len(sc) - 1))[:k]
        top = top[np.argsort(-sc[top])]
        return [(int(i), float(sc[i]), self.texts[i]) for i in top]
