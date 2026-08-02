"""The calibrated prompt across the coverage dial - mapping the frontier.

exp86 found the recall shortfall was CONSERVATISM: one calibration sentence
moved recall 0.198 -> 0.266 at identical precision. exp85 found tighter
enumeration buys precision (0.463 at 74.9% coverage vs 0.287 at 92.8%).

The obvious combination is j2's prompt at exp85's coverage. But the two runs
also showed **coverage and judgement are NOT independent**, which weakens that
prediction and is worth stating before it is tested:

    exp85  coverage 0.749  judgement 0.297   (j0-style prompt)
    exp86  coverage 0.928  judgement 0.213   (j0, same prompt family)

Judgement FELL as coverage rose, because the pairs added by dropping the
proximity filter are exactly the hard ones - entities far apart, relations that
need the whole document. So recall is not simply coverage x a constant, and a
naive product would over-predict.

This maps the dial rather than betting on one point: the calibrated prompt at
three enumeration widths, so the precision/recall frontier is visible and the
operating point becomes a choice rather than an accident.

Predictions:
 - **F1** judgement is higher at narrow coverage than wide, for the same prompt
   - i.e. the non-independence above is real and reproduces.
 - **F2** the calibrated prompt at narrow coverage beats exp85's 0.301 F1.
 - **F3** no setting beats both exp85 on precision AND exp86-j2 on recall;
   there is a frontier, not a free lunch.
"""
from __future__ import annotations
import collections, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
props = json.loads((ROOT/"data"/"wikidata_properties.json").read_text())
docs = json.loads((ROOT/"data"/"gold"/"docred_200.json").read_text())[:N]

def collapse(s):
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9 ]+"," ",str(s).lower())).strip()

LABEL2PID={}
for pid,d in props.items():
    for nm in [d.get("label")]+list(d.get("aliases",[])):
        if nm: LABEL2PID.setdefault(collapse(nm),pid)
used=collections.Counter(l["r"] for d in docs for l in d["labels"])
VOCAB=[props[p]["label"] for p,_ in used.most_common(30) if p in props]

PROMPT="""For each numbered ENTITY PAIR below, state the relation the document
asserts from the first entity to the second, or NONE.

RELATIONS - use ONLY these names, exactly as written:
{rels}

Rules:
- Answer EVERY numbered pair. Do not skip any.
- Direction matters: the relation runs from the first entity to the second.
- If the document DENIES the relation, answer NONE.
- Only answer when the document asserts it; do not guess a plausible relation.
- Calibration: a document like this typically asserts 20-60 of these
  relations. Answering NONE to almost everything is a mistake; read the
  document again for pairs you passed over.

Output one line per pair, nothing else:
{{"n":<number>,"r":"<relation or NONE>"}}

PAIRS:
{pairs}

DOCUMENT:
{text}
"""
# (window, cap): narrow -> wide. window None = no proximity filter.
SETTINGS=[("narrow",2,150),("mid",4,260),("wide",None,400)]

def haiku(p):
    try:
        r=subprocess.run(["copilot","-p",p,"--no-ask-user","--model",
                          "claude-haiku-4.5","--no-auto-update"],
                         capture_output=True,text=True,timeout=900)
        return r.stdout
    except subprocess.TimeoutExpired: return ""

score={k:collections.Counter() for k,_,_ in SETTINGS}
cover={k:collections.Counter() for k,_,_ in SETTINGS}
for di,doc in enumerate(docs):
    vs=doc["vertexSet"]
    disp=[sorted(m["name"] for m in v)[0] for v in vs]
    gold={(l["h"],l["r"],l["t"]) for l in doc["labels"]}
    sents=[" ".join(s) for s in doc["sents"]]
    so=[{m["sent_id"] for m in v} for v in vs]
    def dist(h,t): return min(abs(a-b) for a in so[h] for b in so[t])
    for key,win,cap in SETTINGS:
        cands=[(h,t) for h in range(len(vs)) for t in range(len(vs))
               if h!=t and (win is None or dist(h,t)<=win)]
        cands.sort(key=lambda ht: dist(*ht)); cands=cands[:cap]
        cs=set(cands)
        cover[key]["gold"]+=len(gold)
        cover[key]["enum"]+=sum(1 for (h,_,t) in gold if (h,t) in cs)
        pl="\n".join(f"  {i+1}. {disp[h]}  ->  {disp[t]}"
                     for i,(h,t) in enumerate(cands))
        txt=haiku(PROMPT.format(rels="\n".join(f"  {x}" for x in VOCAB),
                                pairs=pl,text=" ".join(sents)[:6000]))
        got=set(); mapped=0
        for m in re.finditer(r'\{[^{}]*"n"\s*:\s*(\d+)[^{}]*"r"\s*:\s*"([^"]*)"[^{}]*\}',txt):
            i,rel=int(m.group(1))-1,m.group(2)
            if not (0<=i<len(cands)) or rel.strip().upper()=="NONE": continue
            pid=LABEL2PID.get(collapse(rel))
            if not pid: continue
            mapped+=1; h,t=cands[i]
            if (h,pid,t) in gold: got.add((h,pid,t))
        s=score[key]; s["gold"]+=len(gold); s["mapped"]+=mapped; s["hit"]+=len(got)
    print(f"  {di+1}/{len(docs)}  "+"  ".join(
        f"{k}={score[k]['hit']}" for k,_,_ in SETTINGS), flush=True)

print(f"\n{'setting':>8} {'coverage':>9} {'answered':>9} {'correct':>8} "
      f"{'precision':>10} {'recall':>8} {'F1':>7} {'judgement':>10}")
res={}
for key,_,_ in SETTINGS:
    s=score[key]; c=cover[key]["enum"]/max(cover[key]["gold"],1)
    p=s["hit"]/max(s["mapped"],1); rc=s["hit"]/max(s["gold"],1)
    res[key]={"coverage":round(c,4),"answered":s["mapped"],"hit":s["hit"],
              "precision":round(p,4),"recall":round(rc,4),
              "f1":round(2*p*rc/max(p+rc,1e-9),4),
              "judgement":round(rc/max(c,1e-9),4)}
    r=res[key]
    print(f"  {key:>6} {c:>9.3f} {s['mapped']:>9} {s['hit']:>8} {p:>10.3f} "
          f"{rc:>8.3f} {r['f1']:>7.3f} {r['judgement']:>10.3f}")

v=[]
v.append(f"F1 {'CONFIRMED' if res['narrow']['judgement']>res['wide']['judgement'] else 'REFUTED'}"
         f": judgement narrow {res['narrow']['judgement']:.3f} vs wide "
         f"{res['wide']['judgement']:.3f} — coverage and judgement "
         f"{'are NOT independent' if res['narrow']['judgement']>res['wide']['judgement'] else 'appear independent'}.")
best=max(res,key=lambda k:res[k]['f1'])
v.append(f"F2 {'CONFIRMED' if res[best]['f1']>0.301 else 'REFUTED'}: best F1 "
         f"{res[best]['f1']:.3f} ({best}) vs exp85's 0.301.")
dom=any(res[k]['precision']>0.463 and res[k]['recall']>0.266 for k in res)
v.append(f"F3 {'CONFIRMED' if not dom else 'REFUTED'}: "
         f"{'no setting dominates both prior bests - it is a frontier' if not dom else 'a setting DOMINATES both - free lunch found'}.")
print("\n=== VERDICTS ===")
for x in v: print("  "+x)
(ROOT/"results"/"exp87_frontier.json").write_text(json.dumps(
    {"n_docs":len(docs),"settings":res,"verdicts":v,
     "reference":{"exp85":{"precision":0.463,"recall":0.223,"f1":0.301},
                  "exp86_j2":{"precision":0.287,"recall":0.266,"f1":0.276}},
     "scope":("The exp86-j2 calibrated prompt held constant across three "
              "enumeration widths, so the only variable is coverage. Same gold "
              "and scoring as exp76/81/82/84/85/86.")},indent=1))
print("\n[done] results/exp87_frontier.json")
