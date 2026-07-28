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
        # ADJACENCY INDEX. The claims log is the truth; this is a derived
        # view of it, rebuilt on open and maintained on append. Without it
        # every hop linearly scans every claim, so subgraph queries scale
        # with CORPUS size instead of NEIGHBOURHOOD size — measured at 15 ms
        # for a 3-hop over 20k claims, which is 750 ms at 1M and 7.5 s at
        # 10M. Nothing about retrieval was slow; the graph layer was.
        self._by_subj: dict[str, list] = defaultdict(list)
        self._by_obj: dict[str, list] = defaultdict(list)
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
                    self._index(self.claims[-1])
            self._replay_registry()
        else:
            self.store = MemoryStore()
            self._conn = None

    # ---- registry replay (claims log is the truth: stored eids are
    # authoritative — rebuild state, never re-resolve) -----------------------
    def _entity_with_eid(self, eid: str, form: str, batch: str):
        from codec.individuation import Entity
        e = self.reg.entities.get(eid)
        if e is None:
            e = Entity(eid=eid, batch=batch, forms={form},
                       form_tokens=id_tokens([form]))
            self.reg.entities[eid] = e
            n = int(eid[1:]) if eid[1:].isdigit() else 0
            self.reg._n = max(self.reg._n, n + 1)
        e.forms.add(form)
        e.form_tokens |= id_tokens([form])
        self.reg.by_form.setdefault(form, set()).add(eid)
        return e

    def _replay_registry(self) -> None:
        for c in self.claims:
            fn = c["pid"] in FUNCTIONAL_PIDS
            e = self._entity_with_eid(c["subj_eid"], c["subject"],
                                      c["page"])
            e.slots[(c["pid"], "s")] = e.slots.get((c["pid"], "s"), 0) + 1
            if c["subject"] == c["page"]:
                self._canonical.setdefault(c["subject"], c["subj_eid"])
            if c["obj_eid"]:
                o = self._entity_with_eid(c["obj_eid"], c["object"],
                                          c["page"])
                o.slots[(c["pid"], "o")] = \
                    o.slots.get((c["pid"], "o"), 0) + 1
                o.neighbors.add(c["subj_eid"])
                e.neighbors.add(c["obj_eid"])
                if fn:
                    e.functional.setdefault((c["pid"], "s"), c["obj_eid"])
                if c["object"] == c["page"]:
                    self._canonical.setdefault(c["object"], c["obj_eid"])
            else:
                e.neighbors.add("v:" + str(c["object"]).replace(",", ""))

    def _index(self, c: dict) -> None:
        self._by_subj[c["subj_eid"]].append(c)
        if c.get("obj_eid"):
            self._by_obj[c["obj_eid"]].append(c)

    def _declare(self, form: str, batch: str) -> None:
        """Register `form` as ONE canonical entity — adopting before minting.

        All three declarations (page_title / object_page / object_global)
        need this and only one of them had it. Ingest is multi-process and
        a canonical is not restored on replay, so an unconditional mint
        gives a second eid to anything that already arrived by another
        route. Measured twice: GRPO split as resource-vs-subject, and a
        paper title split as citation-axis-vs-bridge, which silently left
        the citation graph and the resource graph in disconnected
        components with zero paths between them.
        """
        if form in self._canonical:
            return
        prior = sorted(self.reg.by_form.get(form, ()))
        if len(prior) == 1:
            self._canonical[form] = self.reg._get(prior[0]).eid
        else:
            self._canonical[form] = self.reg._mint(form, batch).eid


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
                page: str, z, canon_form: str | None = None) -> str:
        """Resolve a mention with TITLE-ENTITY CANONICALIZATION (D82):
        the entity first seen on its own page (form == page title) is
        canonical for that form; later same-form mentions absorb into it
        regardless of functional disagreement — for attributed corpora,
        disagreement is a Track I CONFLICT surface, not individual
        fission (the D49 gate's closed-world prior inverts here).
        Distinct same-name individuals still separate via Wikipedia's
        disambiguated titles (different forms). `canon_form` is the
        page's title when it differs from its identifier (arXiv)."""
        canon = self._canonical.get(form)
        if canon is not None:
            self._record(canon, form, pid, role, other, z)
            eid = self.reg._get(canon).eid
        else:
            eid = self.reg.resolve_write(form, pid, role, other, z,
                                         functional=False, batch=page)
        if form == (canon_form or page):
            self._canonical.setdefault(form, eid)
        return eid

    def _resolve(self, subject: str, pid: str, obj: str, page: str,
                 z: np.ndarray | None = None, record: bool = True,
                 canon_form: str | None = None):
        """Individuate one claim (write-time). Returns (subj_eid, obj_eid,
        id-token set for the store row)."""
        fn = pid in FUNCTIONAL_PIDS
        if is_value(obj):
            se = self._entity(subject, pid, "s",
                              "v:" + obj.replace(",", ""), page, z,
                              canon_form)
            return se, None, {se} | id_tokens([obj]) | {f"p:{pid}"}
        se = self._entity(subject, pid, "s", None, page, z, canon_form)
        oe = self._entity(obj, pid, "o", se, page, z, canon_form)
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
                                 "page_title": (str(d["page_title"])
                                                if d.get("page_title")
                                                else None),
                                 "object_page": (str(d["object_page"])
                                                 if d.get("object_page")
                                                 else None),
                                 "object_global": bool(d.get("object_global")),
                                 "revid": d.get("revid"),
                                 "sid": f"{f.name}:{ln}"})
        # A page's canonical form is its TITLE. Wikipedia pages ARE their
        # title, so page==title there; arXiv pages are IDs, so the title
        # arrives out-of-band as page_title. Without it, D82's
        # canonicalization never fires for papers and every citing paper
        # mints its own eid for the same cited work (measured: one work
        # cited by 33 papers -> 33 eids, so views/cited_by see nothing).
        for r in rows:
            r["canon_form"] = r["page_title"] or r["page"]
        # canonical-page claims first: the title entity must exist before
        # off-page mentions of the same form try to absorb into it (D82)
        rows.sort(key=lambda r: r["subject"] != r["canon_form"])
        # canonical PRE-PASS: an OBJECT mention of a person can precede
        # that person's own page rows even after the sort (it rides some
        # OTHER page's subject==page row) and would mint a stray eid —
        # pre-mint every title entity before resolving anything
        for r in rows:
            if r["subject"] == r["canon_form"]:
                self._declare(r["subject"], r["page"])
        # A link target is canonical for the page it names, even when that
        # page contributes no rows of its own. Citation edges exposed this:
        # a cited work whose own source had no bibliography never appeared
        # as a subject, so every citing paper minted a fresh eid for it and
        # the evidence count read zero. `object_page` is the extractor
        # saying "this object IS that page's title" — a wikilink, declared.
        for r in rows:
            if r["object_page"]:
                self._declare(r["object"], r["object_page"])
        # A GLOBAL entity has no page at all and is still one thing: GSM8K,
        # Qwen2.5, GRPO. Canonicalising the NAME is not enough — the
        # batch-locality resolver (D52) exists to keep same-form mentions
        # apart across documents, which is right for people in a closed
        # world and exactly wrong for a benchmark fifty papers share. Left
        # alone, GSM8K became 16 eids and every cross-paper count read 0.
        # `object_global` is the extractor declaring "this is community
        # vocabulary, one entity by name, corpus-wide".
        for r in rows:
            if r["object_global"]:
                self._declare(r["object"], "global:resource")

        Z = (self._embed([r["statement"] for r in rows])
             if embed and rows else
             np.zeros((len(rows), getattr(self.store, "dim", 1024)),
                      np.float32))
        new = []
        for r, z in zip(rows, Z):
            se, oe, toks = self._resolve(r["subject"], r["pid"],
                                         r["object"], r["page"], z,
                                         canon_form=r["canon_form"])
            idx = self.store.add(np.asarray(z, np.float32), [],
                                 r["statement"])
            self.store.ids[idx] = set(toks)
            if hasattr(self.store, "content_ids"):
                self.store.content_ids[idx] = set(toks)
            c = {"idx": idx, "subject": r["subject"], "subj_eid": se,
                 "pid": r["pid"], "object": r["object"], "obj_eid": oe,
                 "page": r["page"], "sid": r["sid"]}
            self.claims.append(c)
            self._index(c)
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
            revids = {r["sid"]: r.get("revid") for r in rows}
            for c in new:      # persist the token sets set post-add
                src = c["page"] + (f"@{revids[c['sid']]}"
                                   if revids.get(c["sid"]) else "")
                with self._conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE {self.store.table} SET ids=%s, "
                        f"content_ids=%s, source_ref=%s WHERE idx=%s",
                        (sorted(self.store.ids[c["idx"]]),
                         sorted(self.store.ids[c["idx"]]),
                         src, c["idx"]))
        return {"ingested": len(new),
                "eids": len(self.reg.entities),
                "pages": len({c["page"] for c in new})}

    # ---- shared lookups ------------------------------------------------------
    def _live(self, c: dict) -> bool:
        return not self.store.shadowed[c["idx"]]

    def _claims_for(self, eid: str, pid: str | None = None) -> list[dict]:
        out = [c for c in self._by_subj.get(eid, ()) if self._live(c)]
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
        self._index(c)
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
        if not by_page:
            # known entity, nothing said ABOUT it — an entity can exist
            # purely as an object (a cited work that cites nothing), and
            # "answered" with an empty body is the dishonest status
            return {"status": "abstain", "eid": eids[0],
                    "reason": "entity known but no live claims about it",
                    "views": {}}
        return {"status": "answered", "eid": eids[0],
                "views": dict(sorted(by_page.items()))}

    def cited_by(self, subject: str, pid: str = "P_CITES") -> dict:
        """Object-side view: who points AT this entity. `views` answers
        'what does page X say', which needs the entity to be a subject;
        a cited work is only ever an object, so its evidence count lives
        on the other side of the claim. Sources are the citing pages —
        the count is an evidence signal, not a quality judgement."""
        eids = self.resolve_subject(subject)
        if len(eids) != 1:
            return {"status": "ambiguous" if eids else "abstain",
                    "n": 0, "sources": []}
        pages = sorted({c["page"] for c in self._by_obj.get(eids[0], ())
                        if self._live(c)
                        and (pid is None or c["pid"] == pid)})
        return {"status": "answered" if pages else "abstain",
                "eid": eids[0], "n": len(pages), "sources": pages}

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
