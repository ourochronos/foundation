"""Both halves at once: raise coverage, then attack judgement.

exp85 factored recall into two independent terms for the first time:

    recall = coverage x judgement = 0.749 x 0.297 = 0.223

Coverage is an enumeration parameter we control. Judgement is a model property.
Every earlier arm conflated them, which is why five experiments of "improve
recall" moved nothing.

**Coverage**: drop the 3-sentence proximity filter and enumerate ALL ordered
entity pairs. Pure parameter, should approach 100%. The cost is a longer prompt
and more chances to answer spuriously, so precision is the thing to watch.

**Judgement**: three prompts over the same enumerated set, so the comparison is
clean. The observed failure is under-answering - 26 answers offered against 136
pairs on one document - so two of the three variants attack conservatism from
different directions.

  j0  exp85's prompt, unchanged. The baseline.
  j1  + a gloss for every relation. Tests whether the model knows a relation
      holds but cannot name it from the bare label.
  j2  + a calibration hint ("documents like this assert 20-60 of these; a page
      of NONE is wrong"). Tests whether it is miscalibrated rather than unable.

Predictions:
 - **K1** coverage reaches >0.95 with the filter removed.
 - **K2** precision falls, because pairs whose entities never co-occur are now
   offered and some will attract a plausible answer.
 - **K3** j2 beats j0 on recall. If a calibration hint moves it, the 29.7% is
   conservatism rather than incapacity - which is the cheaper problem.
"""
from __future__ import annotations
import collections, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
CAP = 400
props = json.loads((ROOT/"data"/"wikidata_properties.json").read_text())
docs = json.loads((ROOT/"data"/"gold"/"docred_200.json").read_text())[:N]

def collapse(s):
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9 ]+"," ",str(s).lower())).strip()

LABEL2PID={}
for pid,d in props.items():
    for nm in [d.get("label")]+list(d.get("aliases",[])):
        if nm: LABEL2PID.setdefault(collapse(nm),pid)
used=collections.Counter(l["r"] for d in docs for l in d["labels"])
TOP=[p for p,_ in used.most_common(30) if p in props]
VOCAB=[props[p]["label"] for p in TOP]
GLOSS="\n".join(f"  {props[p]['label']}: {(props[p].get('aliases') or ['-'])[0]}"
                for p in TOP)

HEAD="""For each numbered ENTITY PAIR below, state the relation the document
asserts from the first entity to the second, or NONE.

RELATIONS - use ONLY these names, exactly as written:
{rels}
"""
RULES="""
Rules:
- Answer EVERY numbered pair. Do not skip any.
- Direction matters: the relation runs from the first entity to the second.
- If the document DENIES the relation, answer NONE.
- Only answer when the document asserts it; do not guess a plausible relation.
{calib}
Output one line per pair, nothing else:
{{"n":<number>,"r":"<relation or NONE>"}}

PAIRS:
{pairs}

DOCUMENT:
{text}
"""
CALIB=("- Calibration: a document like this typically asserts 20-60 of these\n"
       "  relations. Answering NONE to almost everything is a mistake; read the\n"
       "  document again for pairs you passed over.\n")
VARIANTS={"j0":(False,""), "j1":(True,""), "j2":(False,CALIB)}

def haiku(p):
    try:
        r=subprocess.run(["copilot","-p",p,"--no-ask-user","--model",
                          "claude-haiku-4.5","--no-auto-update"],
                         capture_output=True,text=True,timeout=900)
        return r.stdout
    except subprocess.TimeoutExpired: return ""

score={k:collections.Counter() for k in VARIANTS}
cover=collections.Counter()
for di,doc in enumerate(docs):
    vs=doc["vertexSet"]
    disp=[sorted(m["name"] for m in v)[0] for v in vs]
    gold={(l["h"],l["r"],l["t"]) for l in doc["labels"]}
    sents=[" ".join(s) for s in doc["sents"]]
    sents_of=[{m["sent_id"] for m in v} for v in vs]
    # ALL ordered pairs, proximity used only to order them under the cap
    cands=[(h,t) for h in range(len(vs)) for t in range(len(vs)) if h!=t]
    cands.sort(key=lambda ht: min(abs(a-b) for a in sents_of[ht[0]]
                                  for b in sents_of[ht[1]]))
    cands=cands[:CAP]
    cs=set(cands)
    cover["gold"]+=len(gold); cover["enum"]+=sum(1 for (h,_,t) in gold if (h,t) in cs)
    pl="\n".join(f"  {i+1}. {disp[h]}  ->  {disp[t]}" for i,(h,t) in enumerate(cands))
    for k,(gloss,calib) in VARIANTS.items():
        prompt=(HEAD.format(rels=GLOSS if gloss else "\n".join(f"  {x}" for x in VOCAB))
                +RULES.format(calib=calib,pairs=pl,text=" ".join(sents)[:6000]))
        txt=haiku(prompt); got=set(); mapped=0
        for m in re.finditer(r'\{[^{}]*"n"\s*:\s*(\d+)[^{}]*"r"\s*:\s*"([^"]*)"[^{}]*\}',txt):
            i,rel=int(m.group(1))-1,m.group(2)
            if not (0<=i<len(cands)) or rel.strip().upper()=="NONE": continue
            pid=LABEL2PID.get(collapse(rel))
            if not pid: continue
            mapped+=1; h,t=cands[i]
            if (h,pid,t) in gold: got.add((h,pid,t))
        s=score[k]; s["gold"]+=len(gold); s["mapped"]+=mapped; s["hit"]+=len(got)
    print(f"  {di+1}/{len(docs)} pairs={len(cands)}  "+
          "  ".join(f"{k}={score[k]['hit']}" for k in VARIANTS), flush=True)

covr=cover["enum"]/max(cover["gold"],1)
print(f"\n  COVERAGE: {cover['enum']}/{cover['gold']} gold pairs enumerable "
      f"({100*covr:.1f}%)   [exp85: 74.9%]")
print(f"\n{'arm':>5} {'answered':>9} {'correct':>8} {'precision':>10} {'recall':>8} "
      f"{'F1':>7} {'judgement':>10}")
res={}
for k in VARIANTS:
    s=score[k]; p=s["hit"]/max(s["mapped"],1); rc=s["hit"]/max(s["gold"],1)
    res[k]={"answered":s["mapped"],"hit":s["hit"],"precision":round(p,4),
            "recall":round(rc,4),"f1":round(2*p*rc/max(p+rc,1e-9),4),
            "judgement":round(rc/max(covr,1e-9),4)}
    print(f"  {k:>3} {s['mapped']:>9} {s['hit']:>8} {p:>10.3f} {rc:>8.3f} "
          f"{res[k]['f1']:>7.3f} {res[k]['judgement']:>10.3f}")

v=[]
v.append(f"K1 {'CONFIRMED' if covr>0.95 else 'REFUTED'}: coverage {covr:.3f} "
         f"with the proximity filter removed (exp85: 0.749).")
v.append(f"K2 {'CONFIRMED' if res['j0']['precision']<0.463 else 'REFUTED'}: j0 "
         f"precision {res['j0']['precision']:.3f} vs exp85's 0.463 at 74.9% coverage.")
v.append(f"K3 {'CONFIRMED' if res['j2']['recall']>res['j0']['recall']*1.1 else 'REFUTED'}: "
         f"calibration hint moves recall {res['j0']['recall']:.3f} -> "
         f"{res['j2']['recall']:.3f}, so the 29.7% is "
         f"{'CONSERVATISM, the cheaper problem' if res['j2']['recall']>res['j0']['recall']*1.1 else 'INCAPACITY, and prompting will not fix it'}.")
best=max(VARIANTS,key=lambda k:res[k]['f1'])
v.append(f"BEST: {best} at F1 {res[best]['f1']:.3f} (exp85 best 0.301).")
print("\n=== VERDICTS ===")
for x in v: print("  "+x)
(ROOT/"results"/"exp86_coverage.json").write_text(json.dumps(
    {"n_docs":len(docs),"coverage":round(covr,4),"arms":res,"verdicts":v,
     "scope":("All ordered entity pairs enumerated, proximity used only to order "
              "them under a 400 cap. Three prompts over the identical pair set, "
              "so judgement is compared cleanly. Same gold and scoring as "
              "exp76/81/82/84/85; judgement = recall / coverage.")},indent=1))
print("\n[done] results/exp86_coverage.json")
