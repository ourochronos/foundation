"""v4b — Track F (compute questions) + Track I (attributed conflicts/views)
layered ON the v4 world. Fully programmatic; no new entities.

Track I design (D40 operational, zero new mechanism): a VIEW is identity-
channel content. Conflicting entries carry a source token ("src:meridian")
in their id set; a source-qualified query simply includes that token in its
query ids, and the ordinary overlap rescoring selects the view. Unqualified
queries on conflicted subjects should surface a CONFLICT (top-2 same
(subject, relation), different sources — a margin readout, not a guess).

Track F: answer-time arithmetic over stored facts — the numbers stay
symbolic (D3), the ALU is the executor's, not the decoder's.

Usage: .venv/bin/python scripts/gen_world_v4b.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rng = random.Random(4141)

w = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
facts = w["facts"]

pop = [(i, f) for i, f in enumerate(facts)
       if f["relation"] == "population_of"]
founded = [(i, f) for i, f in enumerate(facts)
           if f["relation"] == "founded_in"]


def num(s):
    return int(s.replace(",", ""))


compute = []
for _ in range(300):
    (ia, fa), (ib, fb) = rng.sample(pop, 2)
    compute.append({"kind": "diff", "rel": "population_of",
                    "a": fa["subject"], "b": fb["subject"],
                    "fa": ia, "fb": ib,
                    "gold": abs(num(fa["object"]) - num(fb["object"])),
                    "text": f"How many more people live in {fa['subject']} "
                            f"than in {fb['subject']}?"})
for _ in range(300):
    (ia, fa), (ib, fb) = rng.sample(pop, 2)
    bigger = fa["subject"] if num(fa["object"]) > num(fb["object"]) \
        else fb["subject"]
    compute.append({"kind": "cmp", "rel": "population_of",
                    "a": fa["subject"], "b": fb["subject"],
                    "fa": ia, "fb": ib, "gold": bigger,
                    "text": f"Which has more people, {fa['subject']} or "
                            f"{fb['subject']}?"})
for _ in range(100):
    (ia, fa), (ib, fb) = rng.sample(founded, 2)
    compute.append({"kind": "diff", "rel": "founded_in",
                    "a": fa["subject"], "b": fb["subject"],
                    "fa": ia, "fb": ib,
                    "gold": abs(num(fa["object"]) - num(fb["object"])),
                    "text": f"How many years apart were {fa['subject']} "
                            f"and {fb['subject']} founded?"})

caps = [(i, f) for i, f in enumerate(facts) if f["relation"] == "capital_of"]
cities = sorted({f["object"] for _, f in caps})
conflicted = rng.sample(caps, 400)
conf_facts, conf_queries = [], []
conf_subjects = set()
for i, f in conflicted:
    alt = rng.choice([c for c in cities if c != f["object"]])
    conf_subjects.add(f["subject"])
    conf_facts.append({"subject": f["subject"], "relation": "capital_of",
                       "object": alt, "source": "meridian",
                       "canonical_idx": i,
                       "entities": [f["subject"], alt], "numbers": [],
                       "text": f"According to the Meridian Atlas, the "
                               f"capital of {f['subject']} is {alt}."})
    conf_queries.append({"subject": f["subject"], "gold_obj": alt,
                         "view": "meridian", "kind": "qualified",
                         "text": f"According to the Meridian Atlas, what "
                                 f"is the capital of {f['subject']}?"})
    conf_queries.append({"subject": f["subject"], "gold_obj": f["object"],
                         "view": None, "kind": "unqualified_conflicted",
                         "text": f"What is the capital of "
                                 f"{f['subject']}?"})
clean = rng.sample([x for x in caps if x[1]["subject"] not in
                    conf_subjects], 200)
for i, f in clean:
    conf_queries.append({"subject": f["subject"], "gold_obj": f["object"],
                         "view": None, "kind": "unqualified_clean",
                         "text": f"What is the capital of "
                                 f"{f['subject']}?"})

out = {"compute": compute, "conflict_facts": conf_facts,
       "conflict_queries": conf_queries}
(ROOT / "data" / "closed_world_v4b.json").write_text(json.dumps(out))
print(f"[v4b] {len(compute)} compute (300 diff-pop, 300 cmp, 100 "
      f"diff-year), {len(conf_facts)} conflict facts, "
      f"{len(conf_queries)} conflict queries")
