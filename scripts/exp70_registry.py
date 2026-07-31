"""Would a shared entity registry create corroboration? The decisive counterfactual.

The chain so far, all measured:

  exp67  1.6% of wiki triples have more than one source
  exp68  a two-source refusal policy refuses 98.1% of answerable questions
  exp69  three corpora in one store share ZERO triples, and zero under an
         oracle entity aligner, because their predicate vocabularies are
         disjoint
  here   within ONE same-domain corpus (558 AI papers), zero of 504 world-fact
         subjects is mentioned by more than one paper

That last number is the surprising one and it moves the diagnosis. The problem
is not that the corpora are about different things — it is that **per-document
extraction produces document-local entities**. Each paper's claims are about
*its own* subject, so two papers discussing the same model never produce the
same subject string.

That extends D93/D94. Naming entities at the source is a free win for precision
*within* a document; corroboration needs entities named consistently *across*
documents, which is a different and harder requirement — and it is precisely
what a canonical seed registry is for.

Before building one, the counterfactual is worth measuring. **Subjects are
document-local, but objects may not be**: a paper's `P_COMPARES_TO` object is
someone else's model, and benchmarks like MMLU are referenced by everyone. If
the graph already connects through object position, a registry has something to
work with; if not, the corpus is a disconnected dust of per-paper stars and no
registry will help.

Predictions, registered before running:

- **R1** objects repeat across papers far more than subjects do — the graph
  connects through object position, not subject position.
- **R2** unifying subject and object namespaces (an oracle registry keyed on
  name) creates cross-paper structure: entities that are a subject in one paper
  and an object in another.
- **R3** even so, TRIPLE corroboration stays low, because two papers referencing
  one model usually say different things about it. Corroboration needs shared
  entities *and* shared assertions, and a registry only buys the first.

Usage: .venv/bin/python scripts/exp70_registry.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundation.kb import KB                                      # noqa: E402
from foundation.model.canonical import norm_text                   # noqa: E402

WORLD = {"P_EVALUATES_ON", "P_BUILDS_ON", "P_INTRODUCES", "P_COMPARES_TO"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm_text(s).lower()).strip("-")[:80] or "x"


kb = KB(backend="pg", table="poc")
ax = [c for c in kb.claims if c["page"].startswith("arxiv:")]
w = [c for c in ax if c["pid"] in WORLD]
papers = {c["page"] for c in w}
print(f"{len(w)} world-fact claims from {len(papers)} papers", flush=True)

subj_pages = collections.defaultdict(set)
obj_pages = collections.defaultdict(set)
for c in w:
    subj_pages[slug(c["subject"])].add(c["page"])
    obj_pages[slug(c["object"])].add(c["page"])

s_rep = {k: v for k, v in subj_pages.items() if len(v) > 1}
o_rep = {k: v for k, v in obj_pages.items() if len(v) > 1}
print(f"\n=== R1: subject position vs object position ===")
print(f"  subjects: {len(subj_pages):5} distinct, {len(s_rep):4} in >1 paper "
      f"({100 * len(s_rep) / max(len(subj_pages), 1):.1f}%)")
print(f"  objects:  {len(obj_pages):5} distinct, {len(o_rep):4} in >1 paper "
      f"({100 * len(o_rep) / max(len(obj_pages), 1):.1f}%)")
if o_rep:
    top = sorted(o_rep, key=lambda k: -len(o_rep[k]))[:8]
    print(f"  most-referenced objects: {top}")

# --------------------------------------------------------------- R2 --------
# Oracle registry: one namespace for subjects and objects, keyed on name.
print(f"\n=== R2: does a shared registry connect the graph? ===")
allnames = collections.defaultdict(set)
for c in w:
    allnames[slug(c["subject"])].add(c["page"])
    allnames[slug(c["object"])].add(c["page"])
bridged = {k for k in subj_pages if k in obj_pages}
multi = {k: v for k, v in allnames.items() if len(v) > 1}
print(f"  entities appearing as BOTH subject and object: {len(bridged)}")
print(f"  entities touched by >1 paper under a unified namespace: "
      f"{len(multi)}/{len(allnames)} "
      f"({100 * len(multi) / max(len(allnames), 1):.1f}%)")
if bridged:
    print(f"  e.g. {sorted(bridged)[:8]}")

# connected components over the paper graph induced by shared entities
adj = collections.defaultdict(set)
for e, pgs in allnames.items():
    pl = sorted(pgs)
    for i, a in enumerate(pl):
        for b in pl[i + 1:]:
            adj[a].add(b)
            adj[b].add(a)
seen, comps = set(), []
for p in sorted(papers):
    if p in seen:
        continue
    stack, comp = [p], []
    seen.add(p)
    while stack:
        x = stack.pop()
        comp.append(x)
        for y in adj[x]:
            if y not in seen:
                seen.add(y)
                stack.append(y)
    comps.append(len(comp))
comps.sort(reverse=True)
print(f"  paper-graph components under the registry: {len(comps)} "
      f"(largest {comps[0] if comps else 0} of {len(papers)})")

# --------------------------------------------------------------- R3 --------
print(f"\n=== R3: does connection become CORROBORATION? ===")
trip = collections.defaultdict(set)
for c in w:
    trip[(slug(c["subject"]), c["pid"], slug(c["object"]))].add(c["page"])
corr = sum(1 for v in trip.values() if len(v) > 1)
# and with subject/object treated as one namespace (direction-insensitive)
und = collections.defaultdict(set)
for c in w:
    a, b = sorted((slug(c["subject"]), slug(c["object"])))
    und[(a, c["pid"], b)].add(c["page"])
corr_und = sum(1 for v in und.values() if len(v) > 1)
print(f"  directed triples:   {len(trip):5}  multi-source: {corr}")
print(f"  undirected triples: {len(und):5}  multi-source: {corr_und}")

v = []
v.append(f"R1 {'CONFIRMED' if len(o_rep) > len(s_rep) else 'REFUTED'}: objects "
         f"repeat across papers {len(o_rep)} times vs {len(s_rep)} for "
         f"subjects — the graph connects through object position.")
v.append(f"R2 {'CONFIRMED' if len(multi) > len(s_rep) and comps and comps[0] > 1 else 'REFUTED'}"
         f": a unified namespace puts {len(multi)} entities in more than one "
         f"paper and links {comps[0] if comps else 0} of {len(papers)} papers "
         f"into one component.")
v.append(f"R3 {'CONFIRMED' if corr_und < 0.05 * len(und) else 'REFUTED'}: "
         f"corroboration stays at {corr_und}/{len(und)} even undirected — a "
         f"registry buys shared entities, not shared assertions.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp70_registry.json").write_text(json.dumps({
    "world_claims": len(w), "papers": len(papers),
    "subjects": len(subj_pages), "subjects_multi_paper": len(s_rep),
    "objects": len(obj_pages), "objects_multi_paper": len(o_rep),
    "bridged_entities": len(bridged),
    "entities_multi_paper_unified": len(multi), "entities_total": len(allnames),
    "paper_components": comps[:10], "n_components": len(comps),
    "triples": len(trip), "corroborated": corr,
    "undirected_triples": len(und), "corroborated_undirected": corr_und,
    "verdicts": v,
    "scope": ("World-facts only (P_EVALUATES_ON, P_BUILDS_ON, P_INTRODUCES, "
              "P_COMPARES_TO) — P_CITES is a bibliography fact and cannot "
              "corroborate by construction, and P_ASSERTS has free-text "
              "objects that never repeat. The oracle registry keys on slugged "
              "name across both argument positions, which is the ceiling for "
              "any name-based entity resolver."),
}, indent=1))
print("\n[done] results/exp70_registry.json")
