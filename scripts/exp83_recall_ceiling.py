"""Why does recall never exceed 0.25? Read what nothing recovered.

Three experiments, seven arms, four combinations: recall has sat between 0.087
and 0.253 in every one. REBEL alone, prompted generation, document-level
context, filtering, adding, naive union — nothing moves it. That is no longer a
property of an extractor.

Two explanations, and they have opposite consequences:

**(a) The benchmark annotates relations no reader would extract** — inferred
from world knowledge or entity types rather than stated in the text. Then 0.25
is an artifact of Re-DocRED and our own corpora are unaffected; we should stop
optimising against this yardstick.

**(b) The relations are plainly there and everything tried misses them.** Then
every corroboration and conflict number in this project is a **fivefold
undercount**, and recall is the ceiling on the whole design.

Two independent probes, one mechanical and one model-based, because a single
method would leave the diagnosis resting on its own assumptions.

**Probe 1 — co-occurrence, no model involved.** For each gold triple, do its two
entities ever appear in the same sentence? A relation whose arguments never
co-occur cannot be extracted per-sentence at all, and is hard even at document
level. If missed triples are disproportionately non-co-occurring, that is
mechanical evidence for the structural reading.

**Probe 2 — verification with calibration.** Ask Haiku, for a triple shown
explicitly, whether the document *states* it. This is legitimate despite Haiku
having failed to extract these: **verification is a strictly easier task than
extraction** — the search is over one candidate rather than all pairs.

The calibration is what makes it trustworthy, and without it the probe would be
worthless:

  recovered gold  triples some arm DID extract  -> expect HIGH "stated"
  missed gold     the population in question    -> the measurement
  fabricated      real entities, wrong relation -> expect LOW "stated"

If the verifier says "stated" for fabricated triples, it is agreeable rather
than discriminating and the whole probe is discarded.

Predictions, registered before running:

- **C1** missed triples co-occur in a sentence far less often than recovered
  ones — a large part of the gap is structural.
- **C2** the verifier discriminates: recovered ≫ fabricated.
- **C3** missed gold verifies as "stated" at a rate **between** the two,
  nearer fabricated than recovered — i.e. mostly explanation (a), with a real
  extraction gap underneath.

Usage: .venv/bin/python scripts/exp83_recall_ceiling.py [n_docs]
"""
from __future__ import annotations

import collections
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
SEED = 0
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
docs = json.loads((ROOT / "data" / "gold" / "docred_200.json").read_text())[:N]


def collapse(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()


LABEL2PID = {}
for pid, d in props.items():
    for nm in [d.get("label")] + list(d.get("aliases", [])):
        if nm:
            LABEL2PID.setdefault(collapse(nm), pid)
used = collections.Counter(l["r"] for d in docs for l in d["labels"])
VOCAB = [props[p]["label"] for p, _ in used.most_common(30) if p in props]

tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()


def rebel(text, nb=5):
    enc = tok(text, return_tensors="pt", truncation=True, max_length=256).to(dev)
    with torch.no_grad():
        g = mdl.generate(**enc, max_length=200, num_beams=nb,
                         num_return_sequences=nb, length_penalty=1.0)
    out = []
    for d in tok.batch_decode(g, skip_special_tokens=False):
        d = d.replace("<s>", "").replace("</s>", "").replace("<pad>", "")
        s = r = o = ""
        cur = None
        for t in d.split():
            if t == "<triplet>":
                if s and r and o:
                    out.append((s.strip(), r.strip(), o.strip()))
                s, cur = "", "s"
            elif t == "<subj>":
                o, cur = "", "o"
            elif t == "<obj>":
                r, cur = "", "r"
            else:
                if cur == "s":
                    s += " " + t
                elif cur == "o":
                    o += " " + t
                elif cur == "r":
                    r += " " + t
        if s and r and o:
            out.append((s.strip(), r.strip(), o.strip()))
    return set(out)


VERIFY = """Does the document below STATE this relation, in this direction?

Relation: {s} --[{r}]--> {o}

Answer with ONE word:
  STATED     - the document says this, explicitly or by direct paraphrase
  INFERABLE  - not said, but follows from world knowledge or the entity types
  NO         - the document does not support it, or states the reverse

DOCUMENT:
{text}
"""


def haiku(p):
    try:
        r = subprocess.run(["copilot", "-p", p, "--no-ask-user",
                            "--model", "claude-haiku-4.5", "--no-auto-update"],
                           capture_output=True, text=True, timeout=300)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def verdict(txt):
    t = txt.upper()
    for k in ("STATED", "INFERABLE", "NO"):
        m = re.search(rf"\b{k}\b", t)
        if m:
            return k, m.start()
    return None, 0


rng = random.Random(SEED)
cooc = {"recovered": [0, 0], "missed": [0, 0]}
buckets = collections.defaultdict(list)

for di, doc in enumerate(docs):
    vs = doc["vertexSet"]
    names = [{collapse(m["name"]) for m in v} for v in vs]
    disp = [sorted(m["name"] for m in v)[0] for v in vs]
    sents = [" ".join(s) for s in doc["sents"]]
    full = " ".join(sents)[:6000]
    gold = {(l["h"], l["r"], l["t"]) for l in doc["labels"]}

    got = set()
    for s in sents:
        if len(s) >= 30:
            for a, r, b in rebel(s):
                pid = LABEL2PID.get(collapse(r))
                if not pid:
                    continue
                for h in [i for i, ns in enumerate(names) if collapse(a) in ns]:
                    for t in [i for i, ns in enumerate(names) if collapse(b) in ns]:
                        if (h, pid, t) in gold:
                            got.add((h, pid, t))

    for (h, pid, t) in gold:
        kind = "recovered" if (h, pid, t) in got else "missed"
        together = any(any(n in collapse(s) for n in names[h])
                       and any(n in collapse(s) for n in names[t]) for s in sents)
        cooc[kind][0] += int(together)
        cooc[kind][1] += 1
        buckets[kind].append((di, disp[h], props.get(pid, {}).get("label", pid),
                              disp[t], full))
    # fabricated control: real entities, a relation the gold does not assert
    for _ in range(max(1, len(gold) // 6)):
        h, t = rng.randrange(len(vs)), rng.randrange(len(vs))
        pid = rng.choice([p for p, _ in used.most_common(30)])
        if h != t and (h, pid, t) not in gold:
            buckets["fabricated"].append((di, disp[h],
                                          props.get(pid, {}).get("label", pid),
                                          disp[t], full))
    print(f"  {di+1}/{len(docs)} gold={len(gold)} recovered={len(got)}", flush=True)

print(f"\n=== probe 1: do the arguments ever share a sentence? ===")
for k in ("recovered", "missed"):
    hit, tot = cooc[k]
    print(f"  {k:>10}: {hit}/{tot} co-occur in some sentence "
          f"({100*hit/max(tot,1):.1f}%)")

print(f"\n=== probe 2: verification, with calibration ===")
SAMPLE = 22
counts = {}
for kind in ("recovered", "missed", "fabricated"):
    items = buckets[kind]
    rng.shuffle(items)
    c = collections.Counter()
    for di, s, r, o, text in items[:SAMPLE]:
        v, _ = verdict(haiku(VERIFY.format(s=s, r=r, o=o, text=text)))
        c[v or "unparsed"] += 1
    n = max(sum(c[x] for x in ("STATED", "INFERABLE", "NO")), 1)
    counts[kind] = {"n": n, **{x: c[x] for x in ("STATED", "INFERABLE", "NO")},
                    "stated_rate": round(c["STATED"] / n, 3),
                    "unparsed": c["unparsed"]}
    print(f"  {kind:>11}: STATED {c['STATED']:>3}  INFERABLE {c['INFERABLE']:>3}  "
          f"NO {c['NO']:>3}   -> stated rate {counts[kind]['stated_rate']:.3f}")

rec, mis, fab = (counts[k]["stated_rate"] for k in ("recovered", "missed", "fabricated"))
mr, mt = cooc["missed"]
rr, rt = cooc["recovered"]
v = []
v.append(f"C1 {'CONFIRMED' if (mr/max(mt,1)) < (rr/max(rt,1)) * 0.8 else 'REFUTED'}: "
         f"missed triples co-occur in a sentence {100*mr/max(mt,1):.1f}% of the "
         f"time vs {100*rr/max(rt,1):.1f}% for recovered.")
v.append(f"C2 {'CONFIRMED' if rec > fab * 1.5 else 'REFUTED'}: verifier "
         f"discriminates — recovered {rec:.3f} vs fabricated {fab:.3f}"
         f"{'' if rec > fab * 1.5 else ' — probe 2 is DISCARDED as uncalibrated'}.")
if rec > fab * 1.5:
    nearer = "fabricated" if abs(mis - fab) < abs(mis - rec) else "recovered"
    v.append(f"C3 {'CONFIRMED' if nearer == 'fabricated' else 'REFUTED'}: missed "
             f"gold verifies STATED at {mis:.3f}, nearer {nearer} — "
             f"{'mostly explanation (a): the benchmark annotates what the text does not state, so 0.25 is its artifact' if nearer == 'fabricated' else 'explanation (b): the relations ARE stated and extraction misses them, so every count in this project is an undercount'}.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp83_ceiling.json").write_text(json.dumps({
    "n_docs": len(docs),
    "cooccurrence": {k: {"together": cooc[k][0], "total": cooc[k][1]}
                     for k in cooc},
    "verification": counts, "verdicts": v,
    "scope": ("Probe 1 is mechanical and model-free. Probe 2 asks a verifier a "
              "strictly easier question than extraction - judge one named "
              "candidate rather than search all pairs - and is calibrated "
              "against recovered gold and fabricated triples, so an agreeable "
              "verifier is detected rather than believed. Recovery is measured "
              "with REBEL at beams=5, the best-recall arm in exp81."),
}, indent=1))
print("\n[done] results/exp83_ceiling.json")
