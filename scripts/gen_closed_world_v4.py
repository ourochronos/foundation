"""Closed world v4 — COMPOSITION-DENSE (D35's v0.1 mandate).

v3 crutch-removal retained (collisions, 5 templates/relation, phrasing
diversity, temporal pairs, no-answer). Added: 2 relations (headquartered_in:
company->city, mayor_of: city->person) and ~11 hop compositions with SHARED
hops (mayor_born shares hop2 with ceo_born; hq_pop with cap_pop; ...), so
composition-space is dense enough for transfer to be learnable. Holdouts
(never in policy training): big_pop, cap_mayor, and the 3-hop hq_loc_cap —
all built from individually-trained relations.

Usage: .venv/bin/python scripts/gen_closed_world_v4.py
"""
from __future__ import annotations
import json, random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gen_closed_world as G
from gen_closed_world_v3 import FACT_T, SURNAMES, TOWN_PREFIX, city_name, person_name

import os
SEED = int(os.environ.get("WORLD_SEED", "41"))
OUT = ROOT / "data" / (f"closed_world_v4.json" if SEED == 41
                       else f"closed_world_v4_s{SEED}.json")
rng = random.Random(SEED)
G.rng = rng

FACT_T = dict(FACT_T)
FACT_T["headquartered_in"] = ["{s} is headquartered in {o}.",
    "{o} hosts the head office of {s}.", "{s} operates from {o}.",
    "The headquarters of {s} sit in {o}.", "{s} keeps its main office in {o}."]
FACT_T["mayor_of"] = ["{o} is the mayor of {s}.", "{s}'s mayor is {o}.",
    "{o} serves as mayor of {s}.", "City hall in {s} is led by {o}.",
    "{o} runs the city government of {s}."]

PHR = json.loads((ROOT / "data" / "query_phrasings_v3.json").read_text())
PHR["headquartered_in"] = ["Where is {X} headquartered?", "In which city is {X} based?",
    "Name the home city of {X}.", "What city hosts {X}'s head office?",
    "Which city does {X} operate from?", "Tell me where {X} keeps its headquarters.",
    "{X}'s main office sits in which city?", "Identify the city where {X} is based.",
    "Which city is home to {X}?", "Where does {X} have its base of operations?",
    "So where's {X} based these days?", "Do you know which city {X} calls home?"]
PHR["mayor_of"] = ["Who is the mayor of {X}?", "Name {X}'s mayor.",
    "Who leads the city government of {X}?", "Who runs city hall in {X}?",
    "Identify the mayor of {X}.", "Which person serves as {X}'s mayor?",
    "Who currently holds the mayoralty of {X}?", "Tell me who governs {X}.",
    "The mayor of {X} — who is that?", "Who's in charge over in {X}?",
    "Who occupies the mayor's office in {X}?", "Do you know who {X}'s mayor is?"]

HOP_T = {
 "cap_pop": (["capital_of","population_of"],
   ["Name the population of the capital of {X}.", "How many people live in {X}'s capital?",
    "What is the headcount of the seat of government of {X}?"]),
 "big_pop": (["largest_city_of","population_of"],
   ["How many residents does the largest city of {X} have?",
    "Name the population of {X}'s biggest city.",
    "What is the population of the most populous city in {X}?"]),
 "ceo_born": (["ceo_of","born_in"],
   ["In what year was the CEO of {X} born?", "Name the birth year of {X}'s chief executive.",
    "When was the person who runs {X} born?"]),
 "mayor_born": (["mayor_of","born_in"],
   ["In what year was the mayor of {X} born?", "Name the birth year of {X}'s mayor.",
    "When was the person who runs city hall in {X} born?"]),
 "hq_pop": (["headquartered_in","population_of"],
   ["How many people live in the city where {X} is headquartered?",
    "Name the population of {X}'s home city.",
    "What is the population of the city hosting {X}'s head office?"]),
 "hq_loc": (["headquartered_in","located_in"],
   ["In which country is {X} headquartered?", "Name the country where {X} is based.",
    "Which nation hosts {X}'s head office?"]),
 "hq_mayor": (["headquartered_in","mayor_of"],
   ["Who is the mayor of the city where {X} is based?",
    "Name the mayor of {X}'s headquarters city."]),
 "loc_cap": (["located_in","capital_of"],
   ["What is the capital of the country containing {X}?",
    "Name the capital of the nation {X} belongs to."]),
 "loc_big": (["located_in","largest_city_of"],
   ["What is the largest city of the country containing {X}?",
    "Name the biggest city of the nation {X} belongs to."]),
 "cap_mayor": (["capital_of","mayor_of"],
   ["Who is the mayor of {X}'s capital?", "Name the mayor of the capital of {X}.",
    "Who runs city hall in the seat of government of {X}?"]),
 "loc_cap_pop": (["located_in","capital_of","population_of"],
   ["What is the population of the capital of the country containing {X}?",
    "How many people live in the capital of the nation where {X} lies?"]),
 "hq_loc_cap": (["headquartered_in","located_in","capital_of"],
   ["What is the capital of the country where {X} is headquartered?",
    "Name the capital of the nation hosting {X}'s head office?"]),
}
HOLDOUTS = ["big_pop", "cap_mayor", "hq_loc_cap"]

def main():
    used = set()
    ents = {"country": [G.name("country", used, 3) for _ in range(600)],
            "city": [city_name(used) for _ in range(1200)],
            "person": [person_name(used) for _ in range(2200)],
            "company": [G.name("company", used, 3) for _ in range(700)]}
    facts, queries, hops = [], [], []
    def fact(s, rel, o, entities, numbers, year=None):
        t = rng.choice(FACT_T[rel]).format(s=s, o=o)
        if year: t = f"In {year}, " + t[0].lower() + t[1:]
        facts.append({"subject": s, "relation": rel, "object": o, "text": t,
                      "entities": entities,
                      "numbers": numbers + ([str(year)] if year else []),
                      "year": year})
        return len(facts) - 1
    def query(fi, rel, subj, kind):
        pi = rng.randrange(12)
        queries.append({"fact_idx": fi, "relation": rel, "kind": kind,
                        "phrasing_idx": pi, "text": PHR[rel][pi].format(X=subj)})

    cities = ents["city"][:]; rng.shuffle(cities)
    idx = {}          # (subject, relation) -> fact idx (current)
    cap_of, big_of, country_of = {}, {}, {}
    for i, c in enumerate(ents["country"]):
        cap, big = cities[2*i], cities[2*i+1]
        cap_of[c], big_of[c] = cap, big
        country_of[cap] = country_of[big] = c
        if rng.random() < 0.10:
            old = rng.choice([x for x in ents["city"] if x not in (cap, big)])
            fact(c, "capital_of", old, [c, old], [], year=rng.randint(1950, 1999))
            fi = fact(c, "capital_of", cap, [c, cap], [], year=rng.randint(2000, 2024))
        else:
            fi = fact(c, "capital_of", cap, [c, cap], [])
        idx[(c, "capital_of")] = fi; query(fi, "capital_of", c, "single")
        fi = fact(c, "largest_city_of", big, [c, big], [])
        idx[(c, "largest_city_of")] = fi; query(fi, "largest_city_of", c, "single")
        for city in (cap, big):
            fi = fact(city, "located_in", c, [city, c], [])
            idx[(city, "located_in")] = fi
            if rng.random() < 0.3: query(fi, "located_in", city, "single")
    people = ents["person"][:]; rng.shuffle(people)
    ceo_of, hq_of = {}, {}
    for i, co in enumerate(ents["company"]):
        ceo = people[i]; ceo_of[co] = ceo
        fi = fact(co, "ceo_of", ceo, [co, ceo], [])
        idx[(co, "ceo_of")] = fi; query(fi, "ceo_of", co, "single")
        yr = str(rng.randint(1902, 2011))
        fi = fact(co, "founded_in", yr, [co], [yr])
        idx[(co, "founded_in")] = fi; query(fi, "founded_in", co, "single")
        hq = rng.choice(cities[:1200])
        hq_of[co] = hq
        fi = fact(co, "headquartered_in", hq, [co, hq], [])
        idx[(co, "headquartered_in")] = fi; query(fi, "headquartered_in", co, "single")
    mayor_of_c = {}
    for j, city in enumerate(ents["city"]):
        m = people[700 + j]
        mayor_of_c[city] = m
        fi = fact(city, "mayor_of", m, [city, m], [])
        idx[(city, "mayor_of")] = fi
        if rng.random() < 0.3: query(fi, "mayor_of", city, "single")
    for p in people[:1900]:
        yr = str(rng.randint(1930, 2004))
        fi = fact(p, "born_in", yr, [p], [yr])
        idx[(p, "born_in")] = fi
        if rng.random() < 0.25: query(fi, "born_in", p, "single")
    for city in ents["city"]:
        pop = f"{rng.randint(40, 4900) * 1000:,}"
        fi = fact(city, "population_of", pop, [city], [pop])
        idx[(city, "population_of")] = fi
        if rng.random() < 0.4: query(fi, "population_of", city, "single")
    n_na = len(queries) // 20
    for _ in range(n_na):
        rel, subj = rng.choice([("founded_in", rng.choice(ents["country"])),
                                ("born_in", rng.choice(ents["city"])),
                                ("capital_of", rng.choice(ents["company"])),
                                ("mayor_of", rng.choice(ents["country"]))])
        pi = rng.randrange(12)
        queries.append({"fact_idx": -1, "relation": rel, "kind": "no_answer",
                        "phrasing_idx": pi, "text": PHR[rel][pi].format(X=subj)})

    def resolve(subj, chain):
        cur = subj
        for rel in chain:
            fi = idx.get((cur, rel))
            if fi is None: return None, None
            cur = facts[fi]["object"]
        return fi, cur
    N_PER = {"cap_pop": 220, "big_pop": 150, "ceo_born": 180, "mayor_born": 180,
             "hq_pop": 180, "hq_loc": 150, "hq_mayor": 150, "loc_cap": 180,
             "loc_big": 150, "cap_mayor": 150, "loc_cap_pop": 120, "hq_loc_cap": 120}
    subj_pool = {"capital_of": ents["country"], "largest_city_of": ents["country"],
                 "ceo_of": ents["company"], "mayor_of": ents["city"],
                 "headquartered_in": ents["company"], "located_in": cities[:1200]}
    for kind, (chain, templates) in HOP_T.items():
        pool = [s for s in subj_pool[chain[0]]]
        rng.shuffle(pool)
        made = 0
        for s in pool:
            if made >= N_PER[kind]: break
            fi, _ = resolve(s, chain)
            if fi is None: continue
            hops.append({"kind": kind, "subject": s, "chain": chain,
                         "answer_fact": fi,
                         "text": rng.choice(templates).format(X=s)})
            made += 1
    OUT.write_text(json.dumps({"facts": facts, "queries": queries, "hops": hops,
                               "held_out_phrasings": [8, 9, 10, 11],
                               "holdout_compositions": HOLDOUTS}))
    n_rel = {}
    for f in facts: n_rel[f["relation"]] = n_rel.get(f["relation"], 0) + 1
    n_hop = {}
    for h in hops: n_hop[h["kind"]] = n_hop.get(h["kind"], 0) + 1
    print(f"[done] {OUT.name}: {len(facts)} facts {n_rel}")
    print(f"  {len(queries)} queries, hops {n_hop}, holdouts {HOLDOUTS}")

if __name__ == "__main__":
    main()
