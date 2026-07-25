"""Closed world v3 — the DE-TEMPLATED world (A1, 07-phase3-plan.md).

Removes every crutch the adversarial review enumerated (threats #1/#2/#9/#10):
  collisions   ~20% of cities share a base-town token ("North Halmelton" /
               "South Halmelton"); ~25% of people share one of 40 surnames —
               identity-overlap is no longer an oracle lookup
  templates    5 store-side statement templates per relation, sampled
  phrasings    12 query phrasings per relation from a DIFFERENT generator
               (data/query_phrasings_v3.json); 4 of 12 held out entirely
               from any operator fitting (template holdout at last)
  compositions 4 hop types + a 3-hop chain + a REVISIT pattern
               (largest city of the country containing {city} — the answer
               is sometimes the source city itself, so hard `exclude`
               breaks by design if it is a heuristic)
  temporal     ~10% of capitals have two dated facts (old + current) —
               multiple facts per (subject, relation)
  no-answer    ~5% of single-hop queries ask about subjects with no such
               fact (kind-mismatched) — recorded for abstention testing

Writes data/closed_world_v3.json.
Usage: .venv/bin/python scripts/gen_closed_world_v3.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gen_closed_world as G      # noqa: E402

OUT = ROOT / "data" / "closed_world_v3.json"
rng = random.Random(23)
G.rng = rng

FACT_T = {
    "capital_of": ["The capital of {s} is {o}.", "{o} serves as {s}'s capital.",
                   "{s}'s capital city is {o}.", "{o} is where {s}'s government sits.",
                   "The seat of government in {s} is {o}."],
    "largest_city_of": ["{o} is the largest city in {s}.",
                        "The most populous city of {s} is {o}.",
                        "{s}'s biggest urban center is {o}.",
                        "No city in {s} is larger than {o}.",
                        "{o} ranks first among {s}'s cities by population."],
    "ceo_of": ["{o} is the chief executive of {s}.", "{s} is led by CEO {o}.",
               "{o} runs {s}.", "At the helm of {s} is {o}.",
               "{s}'s top executive is {o}."],
    "founded_in": ["{s} was founded in {o}.", "{s} opened its doors in {o}.",
                   "{s} has operated since {o}.", "Established in {o}, {s} endures.",
                   "{o} marks the founding year of {s}."],
    "born_in": ["{s} was born in {o}.", "{s}'s birth year is {o}.",
                "Born in {o}, {s} grew up abroad.", "{o} is when {s} was born.",
                "{s} came into the world in {o}."],
    "population_of": ["The population of {s} is {o}.", "{s} is home to {o} people.",
                      "{o} residents live in {s}.", "{s} counts {o} inhabitants.",
                      "{s} has a population of {o}."],
    "located_in": ["{s} lies within {o}.", "{s} is a city in {o}.",
                   "{o} contains the city of {s}.", "{s} belongs to {o}.",
                   "You will find {s} in {o}."],
}

SURNAMES = ["".join(rng.choice(G.ON) for _ in range(2)).capitalize()
            for _ in range(40)]
TOWN_PREFIX = ["North", "South", "East", "West", "New", "Old", "Upper", "Lower"]


def city_name(used):
    if rng.random() < 0.20:                     # colliding base-town names
        base = "".join(rng.choice(G.ON) for _ in range(2)).capitalize() + "ton"
        for _ in range(10):
            n = f"{rng.choice(TOWN_PREFIX)} {base}"
            if n not in used:
                used.add(n)
                return n
    return G.name("city", used, 3)


def person_name(used):
    if rng.random() < 0.25:                     # shared surnames
        for _ in range(10):
            first = "".join(rng.choice(G.ON) for _ in range(2)).capitalize()
            n = f"{first} {rng.choice(SURNAMES)}"
            if n not in used:
                used.add(n)
                return n
    return G.name("person", used, 3)


def main() -> None:
    used: set = set()
    ents = {"country": [G.name("country", used, 3) for _ in range(600)],
            "city": [city_name(used) for _ in range(1200)],
            "person": [person_name(used) for _ in range(900)],
            "company": [G.name("company", used, 3) for _ in range(700)]}
    phr = json.loads((ROOT / "data" / "query_phrasings_v3.json").read_text())

    facts, queries, hops = [], [], []

    def fact(s, rel, o, entities, numbers, year=None):
        t = rng.choice(FACT_T[rel]).format(s=s, o=o)
        if year:
            t = f"In {year}, " + t[0].lower() + t[1:]
        facts.append({"subject": s, "relation": rel, "object": o, "text": t,
                      "entities": entities, "numbers": numbers + ([str(year)] if year else []),
                      "year": year})
        return len(facts) - 1

    def query(fi, rel, subj, kind, phrasing_idx=None):
        pi = phrasing_idx if phrasing_idx is not None else rng.randrange(12)
        queries.append({"fact_idx": fi, "relation": rel, "kind": kind,
                        "phrasing_idx": pi,
                        "text": phr[rel][pi].format(X=subj)})

    cities = ents["city"][:]
    rng.shuffle(cities)
    cap_of, big_of, country_of, pop_fact = {}, {}, {}, {}
    for i, c in enumerate(ents["country"]):
        cap, big = cities[2 * i], cities[2 * i + 1]
        cap_of[c], big_of[c] = cap, big
        country_of[cap] = country_of[big] = c
        if rng.random() < 0.10:                 # temporal pair: old + current
            old = rng.choice([x for x in ents["city"] if x not in (cap, big)])
            fact(c, "capital_of", old, [c, old], [], year=rng.randint(1950, 1999))
            fi = fact(c, "capital_of", cap, [c, cap], [], year=rng.randint(2000, 2024))
        else:
            fi = fact(c, "capital_of", cap, [c, cap], [])
        query(fi, "capital_of", c, "single")
        fi = fact(c, "largest_city_of", big, [c, big], [])
        query(fi, "largest_city_of", c, "single")
        for city in (cap, big):
            fi = fact(city, "located_in", c, [city, c], [])
            if rng.random() < 0.3:
                query(fi, "located_in", city, "single")

    people = ents["person"][:]
    rng.shuffle(people)
    ceo_of, born_fact = {}, {}
    for i, co in enumerate(ents["company"]):
        ceo = people[i]
        ceo_of[co] = ceo
        yr = str(rng.randint(1902, 2011))
        fi = fact(co, "ceo_of", ceo, [co, ceo], [])
        query(fi, "ceo_of", co, "single")
        fi = fact(co, "founded_in", yr, [co], [yr])
        query(fi, "founded_in", co, "single")
    for p in ents["person"]:
        yr = str(rng.randint(1930, 2004))
        born_fact[p] = fact(p, "born_in", yr, [p], [yr])
        if rng.random() < 0.4:
            query(born_fact[p], "born_in", p, "single")
    for city in ents["city"]:
        pop = f"{rng.randint(40, 4900) * 1000:,}"
        pop_fact[city] = fact(city, "population_of", pop, [city], [pop])
        if rng.random() < 0.5:
            query(pop_fact[city], "population_of", city, "single")

    # no-answer queries (~5%): kind-mismatched subjects
    n_na = len(queries) // 20
    for _ in range(n_na):
        rel, subj = rng.choice([("founded_in", rng.choice(ents["country"])),
                                ("born_in", rng.choice(ents["city"])),
                                ("capital_of", rng.choice(ents["company"]))])
        queries.append({"fact_idx": -1, "relation": rel, "kind": "no_answer",
                        "phrasing_idx": (pi := rng.randrange(12)),
                        "text": phr[rel][pi].format(X=subj)})

    # hop cases, 4 compositions + 3-hop + revisit
    HOP_T = {
        "cap_pop": ["Name the population of the capital of {X}.",
                    "How many people live in {X}'s capital?",
                    "What is the headcount of the seat of government of {X}?"],
        "big_pop": ["How many residents does the largest city of {X} have?",
                    "Name the population of {X}'s biggest city.",
                    "What is the population of the most populous city in {X}?"],
        "ceo_born": ["In what year was the CEO of {X} born?",
                     "Name the birth year of {X}'s chief executive.",
                     "When was the person who runs {X} born?"],
        "loc_cap": ["What is the capital of the country containing {X}?",
                    "Name the capital of the nation {X} belongs to.",
                    "{X} sits in some country — what is that country's capital?"],
        "loc_big": ["What is the largest city of the country containing {X}?",
                    "Name the biggest city of the nation {X} belongs to."],
        "loc_cap_pop": ["What is the population of the capital of the country "
                        "containing {X}?",
                        "How many people live in the capital of the nation "
                        "where {X} lies?"],
    }
    def hop(kind, subj, chain, answer_fi):
        hops.append({"kind": kind, "subject": subj, "chain": chain,
                     "answer_fact": answer_fi,
                     "text": rng.choice(HOP_T[kind]).format(X=subj)})

    for c in rng.sample(ents["country"], 250):
        hop("cap_pop", c, ["capital_of", "population_of"], pop_fact[cap_of[c]])
    for c in rng.sample(ents["country"], 150):
        hop("big_pop", c, ["largest_city_of", "population_of"], pop_fact[big_of[c]])
    for co in rng.sample(ents["company"], 200):
        hop("ceo_born", co, ["ceo_of", "born_in"], born_fact[ceo_of[co]])
    src_cities = [x for x in cities[:1200] if x in country_of]
    for city in rng.sample(src_cities, 200):
        c = country_of[city]
        cap_fi = next(i for i, f in enumerate(facts)
                      if f["relation"] == "capital_of" and f["subject"] == c
                      and (f["year"] is None or f["year"] >= 2000))
        hop("loc_cap", city, ["located_in", "capital_of"], cap_fi)
    for city in rng.sample(src_cities, 150):    # REVISIT pattern: answer may
        c = country_of[city]                    # be the source city itself
        big_fi = next(i for i, f in enumerate(facts)
                      if f["relation"] == "largest_city_of" and f["subject"] == c)
        hop("loc_big", city, ["located_in", "largest_city_of"], big_fi)
    for city in rng.sample(src_cities, 120):    # 3-hop
        c = country_of[city]
        hop("loc_cap_pop", city, ["located_in", "capital_of", "population_of"],
            pop_fact[cap_of[c]])

    OUT.write_text(json.dumps({"entities": {k: len(v) for k, v in ents.items()},
                               "facts": facts, "queries": queries, "hops": hops,
                               "held_out_phrasings": [8, 9, 10, 11]}))
    n_rel = {}
    for f_ in facts:
        n_rel[f_["relation"]] = n_rel.get(f_["relation"], 0) + 1
    n_hop = {}
    for h in hops:
        n_hop[h["kind"]] = n_hop.get(h["kind"], 0) + 1
    print(f"[done] {OUT.name}: {len(facts)} facts {n_rel}")
    print(f"  {len(queries)} queries ({sum(q['kind']=='no_answer' for q in queries)} "
          f"no-answer), hops {n_hop}")
    print(f"  collisions: {sum(1 for x in ents['city'] if ' ' in x)} prefixed cities, "
          f"{sum(1 for p in ents['person'] if p.split()[-1] in SURNAMES)} shared surnames")
    print(f"  sample fact: {facts[0]['text']}")
    print(f"  sample query: {queries[0]['text']}")
    print(f"  sample revisit hop: {next(h for h in hops if h['kind']=='loc_big')['text']}")


if __name__ == "__main__":
    main()
