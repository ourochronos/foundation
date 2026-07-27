"""D93/docs-14 step 3: mechanical instruments for arms 0 / A / B.

Scores everything that does not need judgement: entity structure, link
counts, decline rate, and the two false-merge controls. Statement
precision and link precision are frozen human-graded audits and are NOT
computed here — they are separate frozen-label artifacts, per docs/14.

Two scoring definitions, both TIGHTER than the pre-registered wording,
recorded here so the criteria cannot drift in the permissive direction:

  * cross-paper subject rate EXCLUDES self-page links. Held-out papers
    keep their citation claims, so a paper's own title entity exists in
    the store and linking to it would inflate the number for free.
  * an entity counts as shared only if the linked eid was first asserted
    on a DIFFERENT page than the linking claim.

Usage: .venv/bin/python scripts/exp14_score.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EXP = ROOT / "data" / "exp14"

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from foundation.kb import KB                                      # noqa: E402

held = set(json.loads((EXP / "heldout_pages.json").read_text()))
decoys = json.loads((EXP / "planted_decoys.json").read_text())
decoy_eids = {(d["page"], d["eid"]) for d in decoys}

kb = KB(backend="pg", table="linkexp")
page_of: dict[str, str] = {}
for c in kb.claims:
    page_of.setdefault(c["subj_eid"], c["page"])
    if c.get("obj_eid"):
        page_of.setdefault(c["obj_eid"], c["page"])
forms: dict[str, str] = {}
for f, eids in kb.reg.by_form.items():
    for e in eids:
        cur = forms.get(e)
        if cur is None or len(f) < len(cur):
            forms[e] = f


def load(rows_dir: Path, only_held: bool = True) -> list[dict]:
    rows = []
    for f in sorted(rows_dir.glob("out_*.jsonl")):
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if not d.get("pid"):
                continue
            if only_held and d.get("page") not in held:
                continue
            rows.append(d)
    return rows


def structure(rows: list[dict], name: str) -> dict:
    pages = {r["page"] for r in rows}
    subs = {(r["page"], r["subject"]) for r in rows}
    per_page = collections.Counter(r["page"] for r in rows)
    subj_per_page = collections.Counter()
    for p, s in subs:
        subj_per_page[p] += 1
    once = 0
    for p in pages:
        c = collections.Counter(r["subject"] for r in rows if r["page"] == p)
        once += sum(1 for v in c.values() if v == 1)
    return {"arm": name, "papers": len(pages), "claims": len(rows),
            "distinct_subjects": len(subs),
            "subjects_per_claim": round(len(subs) / max(len(rows), 1), 3),
            "claims_per_paper": round(len(rows) / max(len(pages), 1), 2),
            "subjects_per_paper": round(
                sum(subj_per_page.values()) / max(len(pages), 1), 2),
            "singleton_subjects": once,
            "singleton_rate": round(once / max(len(subs), 1), 3)}


out: dict = {"manifest": run_manifest(seed=14, config={
    "protocol": "docs/14-extraction-identity.md (D93, pre-registered)",
    "heldout_papers": len(held), "store": "linkexp"})}

# --- arm 0: the SAME held-out papers as extracted in D92 ------------------
arm0 = load(ROOT / "data" / "arxiv_ai" / "shards")
out["arm0"] = structure(arm0, "0-baseline")

for arm, d in (("A", EXP / "shards_a"), ("B", EXP / "shards_b")):
    if not any(d.glob("out_*.jsonl")):
        continue
    rows = load(d, only_held=False)
    st = structure(rows, arm)

    if arm == "B":
        linked = [r for r in rows if r.get("link")]
        entities = {(r["page"], r["subject"]) for r in rows}
        linked_ent = {(r["page"], r["subject"]) for r in linked}
        valid = [r for r in linked if r["link"] in forms]
        invented = [r for r in linked if r["link"] not in forms]
        # tighter definition: a link only counts as cross-paper when the
        # target entity was first asserted somewhere else
        cross = [r for r in valid
                 if page_of.get(r["link"], "?") != r["page"]]
        cross_ent = {(r["page"], r["subject"]) for r in cross}
        wiki = [r for r in valid
                if not page_of.get(r["link"], "").startswith(("arxiv:", "hf:"))]
        hit_decoy = [r for r in valid if (r["page"], r["link"]) in decoy_eids]
        st.update({
            "entities": len(entities),
            "entities_linked": len(linked_ent),
            "entities_declined": len(entities) - len(linked_ent),
            "decline_rate": round(
                1 - len(linked_ent) / max(len(entities), 1), 3),
            "links_total": len(linked),
            "links_invented_eid": len(invented),
            "cross_paper_links": len(cross),
            "cross_paper_subject_rate": round(
                len(cross_ent) / max(len(entities), 1), 3),
            "wikipedia_links": len(wiki),
            "wikipedia_link_examples": [
                {"subject": r["subject"], "target": forms.get(r["link"]),
                 "target_page": page_of.get(r["link"])} for r in wiki[:8]],
            "planted_decoys_offered": len(decoys),
            "planted_decoys_linked": len(hit_decoy),
            "planted_decoy_hits": [
                {"page": r["page"], "subject": r["subject"],
                 "target": forms.get(r["link"])} for r in hit_decoy],
            "link_targets_sample": [
                {"subject": r["subject"], "target": forms.get(r["link"]),
                 "target_page": page_of.get(r["link"]),
                 "reason": str(r.get("link_reason", ""))[:110]}
                for r in cross[:15]]})
    out[f"arm{arm}"] = st

# --- pre-registered criteria, scored ------------------------------------
a = out.get("armA")
b = out.get("armB")
crit = {}
if a:
    crit["A_subjects_per_claim_le_0.60"] = (a["subjects_per_claim"] <= 0.60,
                                            a["subjects_per_claim"])
if b:
    crit["B_cross_paper_subject_rate_gt_0.10"] = (
        b["cross_paper_subject_rate"] > 0.10, b["cross_paper_subject_rate"])
    crit["B_zero_wikipedia_false_merges"] = (b["wikipedia_links"] == 0,
                                             b["wikipedia_links"])
    crit["B_all_planted_decoys_declined"] = (b["planted_decoys_linked"] == 0,
                                             b["planted_decoys_linked"])
    crit["B_decline_rate_gt_0"] = (b["decline_rate"] > 0, b["decline_rate"])
    crit["B_no_invented_eids"] = (b["links_invented_eid"] == 0,
                                  b["links_invented_eid"])
out["criteria_mechanical"] = {
    k: {"pass": bool(v[0]), "value": v[1]} for k, v in crit.items()}
out["criteria_pending_audit"] = [
    "A: statement precision CI overlaps arm 0 (frozen 50-audit)",
    "A: no new defect family",
    "B: link precision >= 0.90 (frozen 50-link audit + Sol)"]

(ROOT / "results" / "exp14_structure.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "manifest"},
                 indent=1)[:4000])
