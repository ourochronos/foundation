"""Closed world v1 — ~10k facts + 2-hop chains (store scale test + reasoner
on-ramp; extends gen_closed_world.py's design, same determinism guarantees).

Additions over v0:
- scale: 1,000 countries / 2,000 cities / 1,500 people / 1,200 companies
  -> ~9.9k facts (identity rescoring's predicted activation regime, D25)
- two new relations: located_in (city -> country), born_in (person -> year)
- hops: 2-hop test cases "population of the capital of X" — every country's
  capital has a population fact, so the chain capital_of ∘ population_of is
  total. Each hop case records both fact indices and the gold answer.
- queries are SAMPLED (600 paraphrase + 600 relational) to bound encode cost;
  hop cases: 400.

Writes data/closed_world_v1.json.

Usage: .venv/bin/python scripts/gen_closed_world_v1.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gen_closed_world as G      # noqa: E402  (shares name generator/templates)

OUT = ROOT / "data" / "closed_world_v1.json"
rng = random.Random(11)
G.rng = rng                       # one seeded stream for everything


def main() -> None:
    used: set = set()
    ents = {"country": [G.name("country", used, 3) for _ in range(1000)],
            "city": [G.name("city", used, 3) for _ in range(2000)],
            "person": [G.name("person", used, 3) for _ in range(1500)],
            "company": [G.name("company", used, 3) for _ in range(1200)]}

    facts, queries, edits, hops = [], [], [], []

    def fact(subject, relation, obj, text, entities, numbers):
        facts.append({"subject": subject, "relation": relation, "object": obj,
                      "text": text, "entities": entities, "numbers": numbers})
        return len(facts) - 1

    cities = ents["city"][:]
    rng.shuffle(cities)
    cap_of, pop_fact_of_city = {}, {}
    for i, c in enumerate(ents["country"]):
        cap, big = cities[2 * i], cities[2 * i + 1]
        cap_of[c] = cap
        fi = fact(c, "capital_of", cap, f"The capital of {c} is {cap}.",
                  [c, cap], [])
        queries.append({"fact_idx": fi, "relation": "capital_of",
                        "text": f"Which city serves as {c}'s seat of government?",
                        "kind": "paraphrase"})
        queries.append({"fact_idx": fi, "relation": "capital_of",
                        "text": f"Name the capital city of {c}.",
                        "kind": "relational"})
        fi = fact(c, "largest_city_of", big,
                  f"{big} is the largest city in {c}.", [c, big], [])
        queries.append({"fact_idx": fi, "relation": "largest_city_of",
                        "text": f"Which urban center in {c} has the most residents?",
                        "kind": "paraphrase"})
        queries.append({"fact_idx": fi, "relation": "largest_city_of",
                        "text": f"Name the biggest city of {c}.",
                        "kind": "relational"})
        for city in (cap, big):
            fact(city, "located_in", c, f"{city} lies within {c}.",
                 [city, c], [])

    people = ents["person"][:]
    rng.shuffle(people)
    for i, co in enumerate(ents["company"]):
        ceo = people[i]
        yr = str(rng.randint(1902, 2011))
        fi = fact(co, "ceo_of", ceo, f"{ceo} is the chief executive of {co}.",
                  [co, ceo], [])
        queries.append({"fact_idx": fi, "relation": "ceo_of",
                        "text": f"Who runs {co} day to day?", "kind": "paraphrase"})
        queries.append({"fact_idx": fi, "relation": "ceo_of",
                        "text": f"Name the CEO of {co}.", "kind": "relational"})
        fi = fact(co, "founded_in", yr, f"{co} was founded in {yr}.", [co], [yr])
        queries.append({"fact_idx": fi, "relation": "founded_in",
                        "text": f"In which year did {co} first open its doors?",
                        "kind": "paraphrase"})
        queries.append({"fact_idx": fi, "relation": "founded_in",
                        "text": f"Name the founding year of {co}.",
                        "kind": "relational"})

    for p in ents["person"]:
        yr = str(rng.randint(1930, 2004))
        fact(p, "born_in", yr, f"{p} was born in {yr}.", [p], [yr])

    for city in ents["city"]:
        pop = f"{rng.randint(40, 4900) * 1000:,}"
        fi = fact(city, "population_of", pop,
                  f"The population of {city} is {pop}.", [city], [pop])
        pop_fact_of_city[city] = fi
        queries.append({"fact_idx": fi, "relation": "population_of",
                        "text": f"How many people live in {city}?",
                        "kind": "paraphrase"})
        queries.append({"fact_idx": fi, "relation": "population_of",
                        "text": f"Name the population of {city}.",
                        "kind": "relational"})

    # sample queries down (deterministic)
    by_kind = {"paraphrase": [], "relational": []}
    for q in queries:
        by_kind[q["kind"]].append(q)
    queries = (rng.sample(by_kind["paraphrase"], 600)
               + rng.sample(by_kind["relational"], 600))

    # 2-hop cases: population of the capital of X
    fact_idx_of = {(f["subject"], f["relation"]): i for i, f in enumerate(facts)}
    for c in rng.sample(ents["country"], 400):
        cap = cap_of[c]
        hops.append({"country": c, "capital": cap,
                     "hop1_fact": fact_idx_of[(c, "capital_of")],
                     "hop2_fact": pop_fact_of_city[cap],
                     "answer": facts[pop_fact_of_city[cap]]["object"],
                     "text": f"Name the population of the capital of {c}."})

    for i in rng.sample(range(1000), 50):
        c = ents["country"][i]
        old = facts[fact_idx_of[(c, "capital_of")]]["object"]
        new_cap = rng.choice([x for x in ents["city"] if x != old])
        edits.append({"fact_idx": fact_idx_of[(c, "capital_of")],
                      "new_object": new_cap,
                      "text": f"The capital of {c} was moved to {new_cap}.",
                      "entities": [c, new_cap], "numbers": []})

    OUT.write_text(json.dumps({"entities": {k: len(v) for k, v in ents.items()},
                               "facts": facts, "queries": queries,
                               "edits": edits, "hops": hops}))
    n_rel = {}
    for f_ in facts:
        n_rel[f_["relation"]] = n_rel.get(f_["relation"], 0) + 1
    print(f"[done] {OUT.name}: {len(facts)} facts {n_rel}")
    print(f"  {len(queries)} queries, {len(edits)} edits, {len(hops)} hop cases")
    print(f"  hop: {hops[0]['text']}  (via {hops[0]['capital']}, "
          f"answer {hops[0]['answer']})")


if __name__ == "__main__":
    main()
