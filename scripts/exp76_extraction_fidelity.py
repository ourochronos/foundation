"""Extraction fidelity against human labels — the last unmeasured quantity.

Eight experiments and 176 tests cover the model. **Zero cover whether the
extractor's triples are correct**, while the extractor discards half of every
corpus it reads. Every downstream number — corroboration, conflict counts,
agreement — rests on extraction being roughly right, and that has been assumed
throughout.

Re-DocRED supplies human-annotated entities (`vertexSet`) and relations
(`labels`, as Wikidata PIDs), so this is a real gold standard rather than one
this project authored for itself. That distinction matters here more than
usual: the status panel's central finding was that almost every prior result
was "validated against our own artifacts".

**Two arms, same documents, same gold, same scoring:**

- **REBEL** — purpose-built, emits Wikidata-property relations natively.
- **Gemma 4 12B** — the generative extractor used for exp71–73, given the same
  closed relation vocabulary in its prompt so the comparison is fair.

Scoring is deliberately generous to both. A predicted triple counts as correct
if its subject string matches *any* mention of the gold head entity, its object
matches *any* mention of the gold tail, and its relation maps to the gold PID.
Surface-form and mention-choice differences are therefore forgiven; only the
relation and the entity pair must be right.

Predictions, registered before running:

- **F1** REBEL precision is materially above chance but recall is low — it was
  trained sentence-level on this relation family, and DocRED's labels include
  cross-sentence relations it cannot see.
- **F2** Gemma's precision is *lower* than REBEL's despite the closed
  vocabulary, because a generative model asked for triples will produce
  plausible ones rather than declining — the behaviour already observed when it
  looped and when it invented position labels.
- **F3** whichever wins, absolute recall is low enough that every corroboration
  and conflict count in this project should be read as a lower bound.

Usage: .venv/bin/python scripts/exp76_extraction_fidelity.py [n_docs] [arms]
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
ARMS = (sys.argv[2].split(",") if len(sys.argv) > 2 else ["rebel", "gemma"])

props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
docs = json.loads((ROOT / "data" / "gold" / "docred_200.json").read_text())[:N]


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", str(s).lower()).strip()


def collapse(s):
    return re.sub(r"\s+", " ", norm(s))


# relation label/alias -> PID, for mapping REBEL's names back to gold ids
LABEL2PID = {}
for pid, d in props.items():
    for nm in [d.get("label")] + list(d.get("aliases", [])):
        if nm:
            LABEL2PID.setdefault(collapse(nm), pid)

tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()


def rebel(text, nb=3):
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


GPROMPT = """Extract relations from the sentence. Use ONLY these relation names:
{rels}

Entities present: {ents}

Output one JSON object per relation, nothing else:
{{"s": "<entity>", "r": "<relation name from the list>", "o": "<entity>"}}
If no listed relation holds, output nothing at all.

Sentence: {sent}
"""


def gemma(sent, ents, rels):
    p = GPROMPT.format(rels="\n".join(f"  {r}" for r in rels),
                       ents=", ".join(sorted(ents)[:24]), sent=sent)
    try:
        r = subprocess.run([str(ROOT / "gemma.sh"), "-n", "400", "-p", p],
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return set()
    out = set()
    for m in re.finditer(r'\{[^{}]*"s"\s*:[^{}]*\}', r.stdout):
        try:
            d = json.loads(m.group(0))
            if d.get("s") and d.get("r") and d.get("o"):
                out.add((str(d["s"]), str(d["r"]), str(d["o"])))
        except Exception:                                        # noqa: BLE001
            pass
    return out


# vocabulary shown to Gemma: the relation labels actually used in this sample
used = collections.Counter(l["r"] for d in docs for l in d["labels"])
VOCAB = [props[p]["label"] for p, _ in used.most_common(30) if p in props]

score = {a: collections.Counter() for a in ARMS}
for di, doc in enumerate(docs):
    vs = doc["vertexSet"]
    names = [{collapse(m["name"]) for m in v} for v in vs]
    gold = {(h, l["r"], t) for l in doc["labels"]
            for h in [l["h"]] for t in [l["t"]]}
    allnames = {n for s in names for n in s}
    preds = {a: set() for a in ARMS}
    for sent in doc["sents"]:
        text = " ".join(sent)
        if len(text) < 30:
            continue
        if "rebel" in ARMS:
            preds["rebel"] |= rebel(text)
        if "gemma" in ARMS:
            preds["gemma"] |= gemma(text, allnames, VOCAB)

    for arm in ARMS:
        matched, mapped = set(), 0
        for s, r, o in preds[arm]:
            pid = LABEL2PID.get(collapse(r))
            if not pid:
                continue
            mapped += 1
            hs = [i for i, ns in enumerate(names) if collapse(s) in ns]
            ts = [i for i, ns in enumerate(names) if collapse(o) in ns]
            for h in hs:
                for t in ts:
                    if (h, pid, t) in gold:
                        matched.add((h, pid, t))
        score[arm]["gold"] += len(gold)
        score[arm]["pred"] += len(preds[arm])
        score[arm]["mapped"] += mapped
        score[arm]["hit"] += len(matched)
    if (di + 1) % 5 == 0:
        print(f"  {di + 1}/{len(docs)}  " +
              "  ".join(f"{a}: {score[a]['hit']}/{score[a]['mapped']}"
                        for a in ARMS), flush=True)

print(f"\n{'arm':>8} {'predicted':>10} {'in-vocab':>9} {'correct':>8} "
      f"{'precision':>10} {'recall':>8}")
res = {}
for a in ARMS:
    s = score[a]
    p = s["hit"] / max(s["mapped"], 1)
    rc = s["hit"] / max(s["gold"], 1)
    res[a] = {"predicted": s["pred"], "mapped": s["mapped"], "hit": s["hit"],
              "gold": s["gold"], "precision": round(p, 4), "recall": round(rc, 4),
              "f1": round(2 * p * rc / max(p + rc, 1e-9), 4)}
    print(f"  {a:>6} {s['pred']:>10} {s['mapped']:>9} {s['hit']:>8} "
          f"{p:>10.3f} {rc:>8.3f}")

v = []
if "rebel" in res:
    v.append(f"F1 {'CONFIRMED' if res['rebel']['precision'] > 0.1 and res['rebel']['recall'] < 0.5 else 'REFUTED'}"
             f": REBEL precision {res['rebel']['precision']:.3f}, recall "
             f"{res['rebel']['recall']:.3f}.")
if "gemma" in res and "rebel" in res:
    v.append(f"F2 {'CONFIRMED' if res['gemma']['precision'] < res['rebel']['precision'] else 'REFUTED'}"
             f": Gemma precision {res['gemma']['precision']:.3f} vs REBEL "
             f"{res['rebel']['precision']:.3f} on identical documents and "
             f"vocabulary.")
best = max(res.values(), key=lambda x: x["recall"])["recall"] if res else 0
v.append(f"F3 {'CONFIRMED' if best < 0.5 else 'REFUTED'}: best recall "
         f"{best:.3f} — every corroboration and conflict count in this project "
         f"should be read as a LOWER BOUND, not a measurement of what is there.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp76_fidelity.json").write_text(json.dumps({
    "n_docs": len(docs), "arms": res, "vocab_size": len(VOCAB), "verdicts": v,
    "scope": ("Gold is Re-DocRED's human annotation - not authored by this "
              "project, which is the point. Scoring forgives surface form and "
              "mention choice: a prediction is correct if its subject matches "
              "ANY mention of the gold head, its object ANY mention of the "
              "gold tail, and its relation maps to the gold PID. Precision is "
              "over in-vocabulary predictions only, so out-of-vocabulary "
              "output is neither rewarded nor penalised."),
}, indent=1))
print("\n[done] results/exp76_fidelity.json")
