"""Closed-world synthetic facts for the Phase-2 memory gate (docs/04-memory.md).

Deterministic (seeded, no LLM): invented entities from a syllable combinator,
six relation types, every fact rendered as a statement (store side) and as
QUERY phrasings that share no template with the statements — so retrieval
precision measures addressing, not string overlap. Many facts share templates
and differ ONLY in entities, which makes identity discrimination the test.

Writes data/closed_world.json:
  entities:  {kind: [names]}
  facts:     [{subject, relation, object, text, entities, numbers}]
  queries:   [{fact_idx, relation, text, kind: paraphrase|relational}]
  edits:     [{fact_idx, new_object, text, ...}]  — supersession test cases

Usage: .venv/bin/python scripts/gen_closed_world.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "closed_world.json"

rng = random.Random(7)

ON = ["bar", "den", "kel", "mor", "tal", "ven", "zor", "lin", "gar", "sel",
      "tro", "fen", "hal", "rin", "cas", "dov", "mel", "par", "qua", "wes"]
END = {"country": ["ia", "land", "mark", "stan", "ovia"],
       "city": ["ton", "burg", "ford", "haven", "port", "dale"],
       "person": ["a", "en", "us", "ette", "or"],
       "company": [" Industries", " Systems", " Group", " Holdings", " Labs"]}


def name(kind: str, used: set) -> str:
    while True:
        n = "".join(rng.choice(ON) for _ in range(2)).capitalize() + rng.choice(END[kind])
        if kind == "person":
            n = n + " " + ("".join(rng.choice(ON) for _ in range(2)).capitalize())
        if n not in used:
            used.add(n)
            return n


def main() -> None:
    used: set = set()
    ents = {"country": [name("country", used) for _ in range(60)],
            "city": [name("city", used) for _ in range(120)],
            "person": [name("person", used) for _ in range(80)],
            "company": [name("company", used) for _ in range(60)]}

    facts, queries, edits = [], [], []

    def fact(subject, relation, obj, text, entities, numbers):
        facts.append({"subject": subject, "relation": relation, "object": obj,
                      "text": text, "entities": entities, "numbers": numbers})
        return len(facts) - 1

    def query(fi, relation, text, kind):
        queries.append({"fact_idx": fi, "relation": relation, "text": text,
                        "kind": kind})

    cities = ents["city"][:]
    rng.shuffle(cities)
    for i, c in enumerate(ents["country"]):
        cap, big = cities[2 * i], cities[2 * i + 1]
        fi = fact(c, "capital_of", cap,
                  f"The capital of {c} is {cap}.", [c, cap], [])
        query(fi, "capital_of", f"Which city serves as {c}'s seat of government?",
              "paraphrase")
        query(fi, "capital_of", f"Name the capital city of {c}.", "relational")
        fi = fact(c, "largest_city_of", big,
                  f"{big} is the largest city in {c}.", [c, big], [])
        query(fi, "largest_city_of",
              f"Which urban center in {c} has the most residents?", "paraphrase")
        query(fi, "largest_city_of", f"Name the biggest city of {c}.", "relational")

    people = ents["person"][:]
    rng.shuffle(people)
    for i, co in enumerate(ents["company"]):
        ceo = people[i]
        yr = str(rng.randint(1902, 2011))
        fi = fact(co, "ceo_of", ceo,
                  f"{ceo} is the chief executive of {co}.", [co, ceo], [])
        query(fi, "ceo_of", f"Who runs {co} day to day?", "paraphrase")
        query(fi, "ceo_of", f"Name the CEO of {co}.", "relational")
        fi = fact(co, "founded_in", yr,
                  f"{co} was founded in {yr}.", [co], [yr])
        query(fi, "founded_in", f"In which year did {co} first open its doors?",
              "paraphrase")
        query(fi, "founded_in", f"Name the founding year of {co}.", "relational")

    for city in ents["city"]:
        pop = f"{rng.randint(40, 4900) * 1000:,}"
        fi = fact(city, "population_of", pop,
                  f"The population of {city} is {pop}.", [city], [pop])
        query(fi, "population_of", f"How many people live in {city}?",
              "paraphrase")
        query(fi, "population_of", f"Name the population of {city}.",
              "relational")

    # supersession cases: 20 capitals change
    for i in rng.sample(range(60), 20):
        c = ents["country"][i]
        new_cap = cities[120 + 0] if False else rng.choice(
            [x for x in ents["city"] if x != facts[2 * i]["object"]])
        edits.append({"fact_idx": 2 * i, "new_object": new_cap,
                      "text": f"The capital of {c} was moved to {new_cap}.",
                      "entities": [c, new_cap], "numbers": []})

    OUT.write_text(json.dumps({"entities": ents, "facts": facts,
                               "queries": queries, "edits": edits}, indent=1))
    n_rel = {}
    for f_ in facts:
        n_rel[f_["relation"]] = n_rel.get(f_["relation"], 0) + 1
    print(f"[done] {OUT.name}: {len(facts)} facts {n_rel}, "
          f"{len(queries)} queries, {len(edits)} edits")
    print(f"  fact:  {facts[0]['text']}")
    print(f"  para:  {queries[0]['text']}")
    print(f"  rel :  {queries[1]['text']}")
    print(f"  edit:  {edits[0]['text']}")


if __name__ == "__main__":
    main()
