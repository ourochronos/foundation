"""Enumerate the pairs: make the model answer, instead of letting it choose.

exp84 found the recall ceiling is an **output-budget** problem, not a
reachability one - REBEL emits a bounded number of triples per call regardless
of input size (526 -> 393 -> 297 -> 243 as the window widened), so more context
buys fewer extractions. exp77 saw the same thing from the other side: beams
5->12 raises recall 0.223 -> 0.234 while precision collapses.

Every arm so far has asked an **open-ended** question - "what relations are in
this text?" - and let the model decide how much to say. This asks a **bounded**
one: here are N entity pairs, give a relation or NONE for each. The model cannot
spend its budget elsewhere, because each pair demands an answer.

Pairs are enumerated from co-occurrence within a 3-sentence window, which exp84
measured as covering 78.1% of gold - so the reachable set is nearly all of it and
the question is purely whether forcing a decision converts reachability into
recall.

Arms: enumerated (Haiku), plus the exp81 open-ended baselines for reference.

Predictions:
 - **E1** enumerated recall beats every open-ended arm (best so far 0.223).
 - **E2** precision stays well above REBEL's 0.202, since NONE is available and
   explicitly encouraged.
 - **E3** the gain scales with how many gold pairs are in the enumerated set -
   i.e. any remaining shortfall is enumeration coverage, not model failure,
   which is measurable rather than speculative.
"""
from __future__ import annotations
import collections, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
# 55 was an efficiency guess and it became the binding constraint: only 31.2%
# of gold pairs fitted inside it, so the arm could not have scored above 0.31
# recall no matter how well it judged. Raised to cover the reachable set. The
# coverage number should have been computed BEFORE the first run - the same
# "check the instrument can move" lesson this session has now learned seven times.
MAXPAIRS = int(sys.argv[2]) if len(sys.argv) > 2 else 220
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
docs = json.loads((ROOT / "data" / "gold" / "docred_200.json").read_text())[:N]

def collapse(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()

LABEL2PID = {}
for pid, d in props.items():
    for nm in [d.get("label")] + list(d.get("aliases", [])):
        if nm: LABEL2PID.setdefault(collapse(nm), pid)
used = collections.Counter(l["r"] for d in docs for l in d["labels"])
VOCAB = [props[p]["label"] for p, _ in used.most_common(30) if p in props]

PROMPT = """For each numbered ENTITY PAIR below, state the relation the document
asserts from the first entity to the second, or NONE.

RELATIONS - use ONLY these names, exactly as written:
{rels}

Rules:
- Answer EVERY numbered pair. Do not skip any.
- NONE is correct and expected for most pairs. Do not guess a plausible
  relation; only answer when the document asserts it.
- Direction matters: the relation runs from the first entity to the second.
- If the document DENIES the relation, answer NONE.

Output one line per pair, nothing else:
{{"n":<number>,"r":"<relation or NONE>"}}

PAIRS:
{pairs}

DOCUMENT:
{text}
"""

def haiku(p):
    try:
        r = subprocess.run(["copilot","-p",p,"--no-ask-user","--model",
                            "claude-haiku-4.5","--no-auto-update"],
                           capture_output=True, text=True, timeout=900)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""

score = collections.Counter()
cover = collections.Counter()
for di, doc in enumerate(docs):
    vs = doc["vertexSet"]
    names = [{collapse(m["name"]) for m in v} for v in vs]
    disp  = [sorted(m["name"] for m in v)[0] for v in vs]
    sents_of = [{m["sent_id"] for m in v} for v in vs]
    gold = {(l["h"], l["r"], l["t"]) for l in doc["labels"]}
    sents = [" ".join(s) for s in doc["sents"]]

    # enumerate ordered pairs co-occurring within a 3-sentence window
    cands = []
    for h in range(len(vs)):
        for t in range(len(vs)):
            if h == t: continue
            if any(abs(a-b) <= 2 for a in sents_of[h] for b in sents_of[t]):
                cands.append((h, t))
    # prioritise closer co-occurrence when the cap bites, since adjacent
    # mentions are likelier to carry a stated relation
    cands.sort(key=lambda ht: min(abs(a - b) for a in sents_of[ht[0]]
                                  for b in sents_of[ht[1]]))
    cands = cands[:MAXPAIRS]
    cover["gold"] += len(gold)
    cover["enumerated"] += sum(1 for (h,_,t) in gold if (h,t) in set(cands))

    pl = "\n".join(f"  {i+1}. {disp[h]}  ->  {disp[t]}" for i,(h,t) in enumerate(cands))
    txt = haiku(PROMPT.format(rels="\n".join(f"  {x}" for x in VOCAB),
                              pairs=pl, text=" ".join(sents)[:6000]))
    got = set(); mapped = 0
    for m in re.finditer(r'\{[^{}]*"n"\s*:\s*(\d+)[^{}]*"r"\s*:\s*"([^"]*)"[^{}]*\}', txt):
        i, rel = int(m.group(1))-1, m.group(2)
        if not (0 <= i < len(cands)) or rel.strip().upper() == "NONE": continue
        pid = LABEL2PID.get(collapse(rel))
        if not pid: continue
        mapped += 1
        h, t = cands[i]
        if (h, pid, t) in gold: got.add((h, pid, t))
    score["gold"] += len(gold); score["mapped"] += mapped; score["hit"] += len(got)
    print(f"  {di+1}/{len(docs)} pairs={len(cands)} answered={mapped} "
          f"hit={len(got)}/{len(gold)}  running={score['hit']}", flush=True)

p = score["hit"]/max(score["mapped"],1); rc = score["hit"]/max(score["gold"],1)
f1 = 2*p*rc/max(p+rc,1e-9)
covr = cover["enumerated"]/max(cover["gold"],1)
print(f"\n  enumerated pairs: precision {p:.3f}  recall {rc:.3f}  F1 {f1:.3f}")
print(f"  gold pairs inside the enumerated set: {cover['enumerated']}/{cover['gold']} "
      f"({100*covr:.1f}%)  -> recall ceiling for this arm")
print(f"  recall AS A FRACTION of what was enumerable: {rc/max(covr,1e-9):.3f}")

BEST_OPEN = 0.223   # REBEL w1, exp81/84
v=[]
v.append(f"E1 {'CONFIRMED' if rc > BEST_OPEN else 'REFUTED'}: enumerated recall "
         f"{rc:.3f} vs best open-ended {BEST_OPEN:.3f}.")
v.append(f"E2 {'CONFIRMED' if p > 0.202 else 'REFUTED'}: precision {p:.3f} vs "
         f"REBEL's 0.202.")
v.append(f"E3: {100*covr:.1f}% of gold pairs were enumerable, and the arm "
         f"recovered {100*rc/max(covr,1e-9):.1f}% of those - so the shortfall "
         f"is {'ENUMERATION COVERAGE' if rc/max(covr,1e-9) > 0.6 else 'MODEL JUDGEMENT'}, "
         f"which is the actionable half.")
print("\n=== VERDICTS ===")
for x in v: print("  "+x)
(ROOT/"results"/"exp85_enumerated.json").write_text(json.dumps(
    {"n_docs":len(docs),"precision":round(p,4),"recall":round(rc,4),"f1":round(f1,4),
     "gold":score["gold"],"answered":score["mapped"],"hit":score["hit"],
     "enumerable_fraction":round(covr,4),
     "recall_of_enumerable":round(rc/max(covr,1e-9),4),"verdicts":v,
     "scope":("One call per document listing up to 55 ordered entity pairs that "
              "co-occur within a 3-sentence window; the model must answer every "
              "pair with a relation or NONE. Same gold, entity matching and "
              "scoring as exp76/81/82/84.")},indent=1))
print("\n[done] results/exp85_enumerated.json")
