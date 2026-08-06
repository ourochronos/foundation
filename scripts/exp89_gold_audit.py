"""Is Re-DocRED's gold noisy, or is the verifier conservative?

exp83 measured recovered gold verifying STATED at 0.636 - triples REBEL got
RIGHT, that a verifier would not confirm. Flagged as a caveat and never chased.
It matters because the "recall wall at 0.2" is the empirical motivation for
pivoting, and if a third of the gold is not actually stated in its document
then part of that wall is an evaluation artifact rather than a representation
mismatch.

Two independent judges on the same items. If both say not-stated, the gold is
suspect. If they disagree, the verifier is the problem.
"""
import collections, json, re, subprocess, sys
from pathlib import Path
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path("/home/zonk1024/projects/foundation")
props = json.loads((ROOT/"data"/"wikidata_properties.json").read_text())
docs = json.loads((ROOT/"data"/"gold"/"docred_200.json").read_text())[:12]
def collapse(s): return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9 ]+"," ",str(s).lower())).strip()
L2P={}
for pid,d in props.items():
    for nm in [d.get("label")]+list(d.get("aliases",[])):
        if nm: L2P.setdefault(collapse(nm),pid)

tok=AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl=AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev="cuda" if torch.cuda.is_available() else "cpu"; mdl.to(dev).eval()
def rebel(t,nb=5):
    e=tok(t,return_tensors="pt",truncation=True,max_length=256).to(dev)
    with torch.no_grad():
        g=mdl.generate(**e,max_length=200,num_beams=nb,num_return_sequences=nb)
    out=[]
    for d in tok.batch_decode(g,skip_special_tokens=False):
        d=d.replace("<s>","").replace("</s>","").replace("<pad>","")
        s=r=o="";cur=None
        for x in d.split():
            if x=="<triplet>":
                if s and r and o: out.append((s.strip(),r.strip(),o.strip()))
                s,cur="","s"
            elif x=="<subj>": o,cur="","o"
            elif x=="<obj>": r,cur="","r"
            else:
                if cur=="s": s+=" "+x
                elif cur=="o": o+=" "+x
                elif cur=="r": r+=" "+x
        if s and r and o: out.append((s.strip(),r.strip(),o.strip()))
    return set(out)

V="""Does the document STATE this relation, in this direction?
Relation: {s} --[{r}]--> {o}
Answer ONE word: STATED (said explicitly or by direct paraphrase) /
INFERABLE (not said, follows from world knowledge) / NO (unsupported or reversed).
DOCUMENT:
{text}
"""
def haiku(p):
    try:
        return subprocess.run(["copilot","-p",p,"--no-ask-user","--model",
            "claude-haiku-4.5","--no-auto-update"],capture_output=True,
            text=True,timeout=300).stdout
    except Exception: return ""
def gemma(p):
    try:
        return subprocess.run([str(ROOT/"gemma.sh"),"-n","60","-p",p],
            capture_output=True,text=True,timeout=600).stdout
    except Exception: return ""
def vd(t):
    u=t.upper()
    for k in ("STATED","INFERABLE","NO"):
        if re.search(rf"\b{k}\b",u): return k
    return None

items=[]
for di,doc in enumerate(docs):
    vs=doc["vertexSet"]; names=[{collapse(m["name"]) for m in v} for v in vs]
    disp=[sorted(m["name"] for m in v)[0] for v in vs]
    sents=[" ".join(s) for s in doc["sents"]]; full=" ".join(sents)[:6000]
    gold={(l["h"],l["r"],l["t"]) for l in doc["labels"]}
    for s in sents:
        if len(s)<30: continue
        for a,r,b in rebel(s):
            pid=L2P.get(collapse(r))
            if not pid: continue
            for h in [i for i,ns in enumerate(names) if collapse(a) in ns]:
                for t in [i for i,ns in enumerate(names) if collapse(b) in ns]:
                    if (h,pid,t) in gold:
                        items.append((di,disp[h],props.get(pid,{}).get("label",pid),
                                      disp[t],full))
seen=set(); uniq=[]
for it in items:
    k=(it[0],it[1],it[2],it[3])
    if k not in seen: seen.add(k); uniq.append(it)
print(f"{len(uniq)} distinct RECOVERED-gold triples (REBEL got these right)",flush=True)
import random; random.Random(0).shuffle(uniq); sample=uniq[:26]

agree=collections.Counter(); rows=[]
for di,s,r,o,text in sample:
    p=V.format(s=s,r=r,o=o,text=text)
    a,b=vd(haiku(p)),vd(gemma(p))
    agree[(a,b)]+=1; rows.append((di,s,r,o,a,b))
    print(f"  doc{di:>2} {s[:24]:26}--[{r[:22]:24}]-->{o[:22]:24} haiku={a} gemma={b}",flush=True)

both_no=sum(n for (a,b),n in agree.items() if a in("NO","INFERABLE") and b in("NO","INFERABLE"))
both_yes=sum(n for (a,b),n in agree.items() if a=="STATED" and b=="STATED")
disag=sum(n for (a,b),n in agree.items() if (a=="STATED")!=(b=="STATED"))
n=len(sample)
print(f"\n  both STATED            : {both_yes}/{n} ({100*both_yes/n:.0f}%)")
print(f"  both NOT-stated        : {both_no}/{n} ({100*both_no/n:.0f}%)  <- gold suspect")
print(f"  judges DISAGREE        : {disag}/{n} ({100*disag/n:.0f}%)  <- verifier suspect")
verdict=("GOLD IS SUSPECT: two independent judges both decline to confirm a large "
         "share of triples the extractor got RIGHT, so part of the recall wall is "
         "an evaluation artifact."
         if both_no > disag else
         "VERIFIER IS SUSPECT: the judges disagree more than they jointly decline, "
         "so exp83's 0.636 reflects verifier conservatism and the gold survives.")
print(f"\n  VERDICT: {verdict}")
json.dump({"n":n,"both_stated":both_yes,"both_not_stated":both_no,
           "disagree":disag,"verdict":verdict,
           "rows":[{"doc":d,"s":s,"r":r,"o":o,"haiku":a,"gemma":b}
                   for d,s,r,o,a,b in rows]},
          open(ROOT/"results"/"exp89_gold_audit.json","w"),indent=1)
print("\n[done] results/exp89_gold_audit.json")
