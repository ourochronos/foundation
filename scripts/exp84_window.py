"""Windowing, not coref: the cheapest fix for the recall ceiling.

exp83 split the recall problem in two and named coref as the fix for the
cross-sentence half. A model-free upper-bound check said otherwise:

  share a sentence by canonical name          43.7%
  + gold coref (ANY mention counts)           51.2%   <- coref headroom is +7.4
  + a 2-sentence window                       78.1%

Coref was the top-ranked item from the Covalence read and it is a **minor lever
here**; over half the triples whose arguments never share a sentence have them
in *adjacent* sentences. That costs nothing to fix - no model, just different
chunking - so it is tested before anything is installed.

Predictions:
 - **W1** recall rises materially from window 1 to 2.
 - **W2** precision falls, since a wider window offers more spurious pairs.
 - **W3** returns flatten by window 4, because the 78.1% ceiling is approached
   and beyond that the arguments really are far apart.
"""
from __future__ import annotations
import collections, json, re, sys
from pathlib import Path
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
docs = json.loads((ROOT / "data" / "gold" / "docred_200.json").read_text())[:N]

def collapse(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()

LABEL2PID = {}
for pid, d in props.items():
    for nm in [d.get("label")] + list(d.get("aliases", [])):
        if nm: LABEL2PID.setdefault(collapse(nm), pid)

tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()
print(f"REBEL on {dev}; {len(docs)} docs", flush=True)

def rebel(text, nb=5):
    enc = tok(text, return_tensors="pt", truncation=True, max_length=384).to(dev)
    with torch.no_grad():
        g = mdl.generate(**enc, max_length=256, num_beams=nb,
                         num_return_sequences=nb, length_penalty=1.0)
    out=[]
    for d in tok.batch_decode(g, skip_special_tokens=False):
        d=d.replace("<s>","").replace("</s>","").replace("<pad>","")
        s=r=o=""; cur=None
        for t in d.split():
            if t=="<triplet>":
                if s and r and o: out.append((s.strip(),r.strip(),o.strip()))
                s,cur="","s"
            elif t=="<subj>": o,cur="","o"
            elif t=="<obj>":  r,cur="","r"
            else:
                if cur=="s": s+=" "+t
                elif cur=="o": o+=" "+t
                elif cur=="r": r+=" "+t
        if s and r and o: out.append((s.strip(),r.strip(),o.strip()))
    return set(out)

WINDOWS=[1,2,3,4]
score={w: collections.Counter() for w in WINDOWS}
for di,doc in enumerate(docs):
    vs=doc["vertexSet"]
    names=[{collapse(m["name"]) for m in v} for v in vs]
    gold={(l["h"],l["r"],l["t"]) for l in doc["labels"]}
    sents=[" ".join(s) for s in doc["sents"]]
    for w in WINDOWS:
        preds=set()
        # stride 1 so every adjacent pair is seen; overlap is intentional
        for i in range(0, max(len(sents)-w+1, 1)):
            chunk=" ".join(sents[i:i+w])
            if len(chunk)>=30: preds |= rebel(chunk)
        matched,mapped=set(),0
        for s,r,o in preds:
            pid=LABEL2PID.get(collapse(r))
            if not pid: continue
            mapped+=1
            hs=[i for i,ns in enumerate(names) if collapse(s) in ns]
            ts=[i for i,ns in enumerate(names) if collapse(o) in ns]
            for h in hs:
                for t in ts:
                    if (h,pid,t) in gold: matched.add((h,pid,t))
        score[w]["gold"]+=len(gold); score[w]["pred"]+=len(preds)
        score[w]["mapped"]+=mapped; score[w]["hit"]+=len(matched)
    print(f"  {di+1}/{len(docs)}  "+"  ".join(f"w{w}={score[w]['hit']}" for w in WINDOWS), flush=True)

print(f"\n{'window':>7} {'pred':>7} {'correct':>8} {'precision':>10} {'recall':>8} {'F1':>7}")
res={}
for w in WINDOWS:
    s=score[w]; p=s["hit"]/max(s["mapped"],1); rc=s["hit"]/max(s["gold"],1)
    res[w]={"pred":s["pred"],"hit":s["hit"],"precision":round(p,4),
            "recall":round(rc,4),"f1":round(2*p*rc/max(p+rc,1e-9),4)}
    print(f"  {w:>5} {s['pred']:>7} {s['hit']:>8} {p:>10.3f} {rc:>8.3f} {res[w]['f1']:>7.3f}")

v=[]
v.append(f"W1 {'CONFIRMED' if res[2]['recall']>res[1]['recall']*1.15 else 'REFUTED'}: "
         f"recall {res[1]['recall']:.3f} (w1) -> {res[2]['recall']:.3f} (w2), "
         f"{100*(res[2]['recall']/max(res[1]['recall'],1e-9)-1):+.0f}%.")
v.append(f"W2 {'CONFIRMED' if res[2]['precision']<res[1]['precision'] else 'REFUTED'}: "
         f"precision {res[1]['precision']:.3f} -> {res[2]['precision']:.3f}.")
gain34=res[4]['recall']-res[3]['recall']; gain12=res[2]['recall']-res[1]['recall']
v.append(f"W3 {'CONFIRMED' if gain34 < gain12*0.5 else 'REFUTED'}: recall gain "
         f"w1->w2 {gain12:+.3f} vs w3->w4 {gain34:+.3f}.")
best=max(WINDOWS,key=lambda w:res[w]['f1'])
v.append(f"BEST: window {best} at F1 {res[best]['f1']:.3f} / recall "
         f"{res[best]['recall']:.3f}, against the exp81 baseline of 0.212 / 0.223.")
print("\n=== VERDICTS ===")
for x in v: print("  "+x)
(ROOT/"results"/"exp84_window.json").write_text(json.dumps(
    {"n_docs":len(docs),"windows":res,"verdicts":v,
     "scope":("REBEL at beams=5, stride 1 so every adjacent pair is seen; "
              "overlapping windows are intentional and duplicates collapse in "
              "the prediction set. Same gold and scoring as exp76/81/82.")},indent=1))
print("\n[done] results/exp84_window.json")
