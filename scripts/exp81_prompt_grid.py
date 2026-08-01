"""The benchmark grid: what is achievable WITHOUT training?

Queued since exp76 and repeatedly deferred. It answers the question a fine-tune
decision rests on — **what does prompting get you** — and it removes a confound
this project has been carrying: exp76 concluded "purpose-built beats generative"
(REBEL P 0.222 vs Gemma P 0.185) using a **first-draft prompt written for a
different task and never iterated**. That is not a fair comparison and it has
been cited as though it were.

**Arms.** REBEL at beams=5 (exp77's tuned setting), plus Gemma 4 12B and
Haiku 4.5 under three prompts each.

**Each model is run the way it is strongest**, which is the only fair
comparison: REBEL per-sentence, because that is what it was trained for and it
has no document mode; the generative models per-document, because they can see
cross-sentence relations. exp76 noted that running everything per-sentence
capped recall structurally, since DocRED annotates relations spanning
sentences — so this also tests whether generative models recover what REBEL
cannot reach in principle.

**Prompt variants**, each isolating one hypothesis:

- **p0** minimal — the exp76-style first draft. The baseline that makes the
  confound visible.
- **p1** schema-first — relation glosses, the gold entity list supplied, and an
  explicit instruction that emitting nothing is correct. Tests whether the
  exp76 gap was prompt quality rather than model class.
- **p2** p1 plus few-shot with **hard negatives**, including a negated sentence
  whose relation must NOT be emitted. Tests whether prompting can close the
  negation hole that REBEL cannot express at any beam width (exp78: 25.1% of
  philosophical triples come from negated sentences).

Scoring is exp76's, unchanged, so numbers are directly comparable to its
0.222/0.155 and exp77's 0.202/0.223.

Predictions, registered before running:

- **B1** p1 beats p0 for both generative models by a wide margin — the exp76
  comparison was confounded and its conclusion does not survive.
- **B2** the best generative arm **beats REBEL on recall**, because
  document-level prompting reaches cross-sentence relations REBEL cannot.
- **B3** REBEL retains the precision edge, since a closed decoder cannot invent
  a relation outside its vocabulary.

Usage: .venv/bin/python scripts/exp81_prompt_grid.py [n_docs] [arms]
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
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
ARMS = (sys.argv[2].split(",") if len(sys.argv) > 2
        else ["rebel", "gemma:p0", "gemma:p1", "gemma:p2",
              "haiku:p0", "haiku:p1", "haiku:p2"])

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
VOCAB = [(p, props[p]["label"]) for p, _ in used.most_common(30) if p in props]

P0 = """Extract relations. Use ONLY these relation names:
{rels}
Output one JSON object per relation: {{"s":"...","r":"...","o":"..."}}
Text: {text}
"""

P1 = """You extract Wikidata-style relations from a document.

RELATIONS - use ONLY these names, exactly as written:
{rels}

ENTITIES present in this document:
{ents}

Rules:
- Both s and o MUST be copied from the entity list above.
- r MUST be from the relation list above.
- Relations may span sentences; use the whole document.
- If no listed relation holds between two listed entities, output NOTHING.
  Emitting nothing is a correct answer and is expected for many documents.

Output one JSON object per relation, nothing else:
{{"s":"<entity>","r":"<relation>","o":"<entity>"}}

Document:
{text}
"""

P2 = """You extract Wikidata-style relations from a document.

RELATIONS - use ONLY these names, exactly as written:
{rels}

ENTITIES present in this document:
{ents}

Rules:
- Both s and o MUST be copied from the entity list above.
- r MUST be from the relation list above.
- Relations may span sentences; use the whole document.
- If no listed relation holds, output NOTHING. That is a correct answer.
- NEGATION: if the text DENIES a relation, do not emit it.

Examples:
  "Marie Curie was born in Warsaw, then part of the Russian Empire."
    {{"s":"Marie Curie","r":"place of birth","o":"Warsaw"}}
    {{"s":"Warsaw","r":"country","o":"Russian Empire"}}
  "Lyon has never been the capital of France."
    (nothing - the text denies it)
  "Smith joined the firm in 1998 and left in 2004. He later founded Acme."
    {{"s":"Smith","r":"employer","o":"the firm"}}
    {{"s":"Acme","r":"founded by","o":"Smith"}}
  "The report was inconclusive."
    (nothing - no listed relation holds)

Output one JSON object per relation, nothing else:
{{"s":"<entity>","r":"<relation>","o":"<entity>"}}

Document:
{text}
"""
PROMPTS = {"p0": P0, "p1": P1, "p2": P2}

tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()
print(f"REBEL on {dev}; {len(docs)} docs; arms={ARMS}", flush=True)


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


def gemma(p):
    try:
        r = subprocess.run([str(ROOT / "gemma.sh"), "-n", "1200", "-p", p],
                           capture_output=True, text=True, timeout=900)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def haiku(p):
    try:
        r = subprocess.run(["copilot", "-p", p, "--no-ask-user",
                            "--model", "claude-haiku-4.5", "--no-auto-update"],
                           capture_output=True, text=True, timeout=600)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def parse(txt):
    out = set()
    for m in re.finditer(r'\{[^{}]*"s"\s*:[^{}]*\}', txt):
        try:
            d = json.loads(m.group(0))
            if d.get("s") and d.get("r") and d.get("o"):
                out.add((str(d["s"]), str(d["r"]), str(d["o"])))
        except Exception:                                        # noqa: BLE001
            pass
    return out


score = {a: collections.Counter() for a in ARMS}
for di, doc in enumerate(docs):
    vs = doc["vertexSet"]
    names = [{collapse(m["name"]) for m in v} for v in vs]
    gold = {(l["h"], l["r"], l["t"]) for l in doc["labels"]}
    sents = [" ".join(s) for s in doc["sents"]]
    full = " ".join(sents)[:6000]
    ents = sorted({m["name"] for v in vs for m in v})
    rels = "\n".join(f"  {lbl}" for _, lbl in VOCAB)

    preds = {}
    if "rebel" in ARMS:
        p = set()
        for s in sents:
            if len(s) >= 30:
                p |= rebel(s)
        preds["rebel"] = p
    for arm in ARMS:
        if ":" not in arm:
            continue
        model, pk = arm.split(":")
        prompt = PROMPTS[pk].format(rels=rels, ents=", ".join(ents[:40]),
                                    text=full)
        preds[arm] = parse((gemma if model == "gemma" else haiku)(prompt))

    for arm in ARMS:
        matched, mapped = set(), 0
        for s, r, o in preds.get(arm, ()):
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
        score[arm]["pred"] += len(preds.get(arm, ()))
        score[arm]["mapped"] += mapped
        score[arm]["hit"] += len(matched)
    print(f"  {di+1}/{len(docs)}  " +
          "  ".join(f"{a.split(':')[-1] if ':' in a else a}"
                    f"={score[a]['hit']}" for a in ARMS), flush=True)

print(f"\n{'arm':>12} {'pred':>7} {'in-vocab':>9} {'correct':>8} "
      f"{'precision':>10} {'recall':>8} {'F1':>7}")
res = {}
for a in ARMS:
    s = score[a]
    p = s["hit"] / max(s["mapped"], 1)
    rc = s["hit"] / max(s["gold"], 1)
    res[a] = {"pred": s["pred"], "mapped": s["mapped"], "hit": s["hit"],
              "precision": round(p, 4), "recall": round(rc, 4),
              "f1": round(2 * p * rc / max(p + rc, 1e-9), 4)}
    print(f"  {a:>10} {s['pred']:>7} {s['mapped']:>9} {s['hit']:>8} "
          f"{p:>10.3f} {rc:>8.3f} {res[a]['f1']:>7.3f}")

gen = [a for a in ARMS if ":" in a]
v = []
if gen:
    for m in ("gemma", "haiku"):
        p0, p1 = res.get(f"{m}:p0"), res.get(f"{m}:p1")
        if p0 and p1:
            v.append(f"B1/{m} {'CONFIRMED' if p1['f1'] > p0['f1'] * 1.25 else 'REFUTED'}: "
                     f"F1 {p0['f1']:.3f} (p0) -> {p1['f1']:.3f} (p1); exp76's "
                     f"comparison used a p0-grade prompt.")
    best = max((res[a] for a in gen), key=lambda x: x["recall"])
    if "rebel" in res:
        v.append(f"B2 {'CONFIRMED' if best['recall'] > res['rebel']['recall'] else 'REFUTED'}"
                 f": best generative recall {best['recall']:.3f} vs REBEL "
                 f"{res['rebel']['recall']:.3f}.")
        bp = max((res[a] for a in gen), key=lambda x: x["precision"])
        v.append(f"B3 {'CONFIRMED' if res['rebel']['precision'] >= bp['precision'] else 'REFUTED'}"
                 f": REBEL precision {res['rebel']['precision']:.3f} vs best "
                 f"generative {bp['precision']:.3f}.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp81_grid.json").write_text(json.dumps({
    "n_docs": len(docs), "arms": res, "vocab": len(VOCAB), "verdicts": v,
    "scope": ("Scoring is exp76's, unchanged, so numbers compare directly to "
              "its 0.222/0.155 and exp77's 0.202/0.223. Each model runs the way "
              "it is strongest - REBEL per sentence since it has no document "
              "mode, generative models per document since they can reach "
              "cross-sentence relations - which is a fair comparison of "
              "capability rather than a matched-input one."),
}, indent=1))
print("\n[done] results/exp81_grid.json")
