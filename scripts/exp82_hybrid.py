"""REBEL proposes, Haiku disposes — do the two axes compose?

exp81 left the two extractors strong on opposite things:

    REBEL      P 0.202  R 0.223   emits 526 triples to land 105
    haiku:p2   P 0.723  R 0.183   emits 119 to land 86

REBEL's 526 predictions *contain* 105 correct ones. If a precise reader can
isolate them, the combination should reach REBEL's recall at something near
Haiku's precision — better than either alone. If it cannot, that is worth
knowing too, because it would mean REBEL's extra recall is not recoverable and
the recall ceiling is real rather than a filtering problem.

Three arms, so the contribution of each half is separable:

- **filter** — Haiku sees the document and REBEL's candidates, and only keeps or
  drops. Recall cannot exceed REBEL's; precision should rise sharply.
- **filter+add** — the same, plus permission to add relations REBEL missed.
  Isolates whether the adding step is what buys recall.
- **union** — the naive baseline, both sets merged with no judgement. Included
  because a hybrid that cannot beat set-union is not a hybrid, it is overhead.

Predictions, registered before running:

- **H1** filtering raises precision well above REBEL's 0.202 — the correct
  triples are identifiable from the text.
- **H2** filter-only recall lands close to REBEL's 0.223 rather than far below;
  a filter that discards most true positives would mean the candidates are not
  separable.
- **H3** filter+add beats **both** standalone arms on F1 (0.212 and 0.291). This
  is the real question: if it does not, the axes do not compose and the right
  move is to pick one extractor rather than build a pipeline.

Usage: .venv/bin/python scripts/exp82_hybrid.py [n_docs]
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
ARMS = ["rebel", "filter", "filter_add", "union"]

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
print(f"REBEL on {dev}; {len(docs)} docs", flush=True)


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


FILTER = """You are checking candidate relations against a document.

Below are CANDIDATES produced by an automatic extractor. Many are wrong: the
extractor ignores negation, invents relations, and reverses arguments. Your job
is to keep only those the document actually supports.

RELATIONS - a candidate is valid only if its relation is one of these:
{rels}

ENTITIES in this document:
{ents}

Rules:
- KEEP a candidate only if the document states that relation between those two
  entities, in that direction.
- DROP it if the document denies it, if the direction is reversed, if either
  argument is not an entity above, or if it is merely plausible.
- Dropping most candidates is expected and correct.
{addclause}
Output one JSON object per KEPT relation, nothing else:
{{"s":"<entity>","r":"<relation>","o":"<entity>"}}

CANDIDATES:
{cands}

DOCUMENT:
{text}
"""
ADD = ("- After checking, you MAY add relations the document supports that are\n"
       "  missing from the candidate list.\n")
NOADD = ("- Do NOT add anything. Only keep or drop the candidates given.\n")


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

    cand = set()
    for s in sents:
        if len(s) >= 30:
            cand |= rebel(s)
    # only candidates whose relation maps into the vocabulary are worth judging
    cl = sorted({(a, r, b) for a, r, b in cand if LABEL2PID.get(collapse(r))})
    cands_txt = "\n".join(f'  {{"s":"{a}","r":"{r}","o":"{b}"}}' for a, r, b in cl[:80])
    base = {"rels": "\n".join(f"  {x}" for x in VOCAB),
            "ents": ", ".join(ents[:40]), "cands": cands_txt, "text": full}

    preds = {"rebel": cand,
             "filter": parse(haiku(FILTER.format(addclause=NOADD, **base))),
             "filter_add": parse(haiku(FILTER.format(addclause=ADD, **base)))}
    preds["union"] = cand | preds["filter_add"]

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
    print(f"  {di+1}/{len(docs)}  " +
          "  ".join(f"{a}={score[a]['hit']}" for a in ARMS), flush=True)

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

REBEL_F1, HAIKU_F1 = 0.212, 0.291      # exp81, same docs and scoring
v = []
v.append(f"H1 {'CONFIRMED' if res['filter']['precision'] > res['rebel']['precision'] * 1.5 else 'REFUTED'}"
         f": filtering moves precision {res['rebel']['precision']:.3f} -> "
         f"{res['filter']['precision']:.3f}.")
v.append(f"H2 {'CONFIRMED' if res['filter']['recall'] > res['rebel']['recall'] * 0.6 else 'REFUTED'}"
         f": filter keeps recall {res['filter']['recall']:.3f} against REBEL's "
         f"{res['rebel']['recall']:.3f} — the correct candidates "
         f"{'are' if res['filter']['recall'] > res['rebel']['recall']*0.6 else 'are NOT'} separable.")
best_single = max(REBEL_F1, HAIKU_F1)
v.append(f"H3 {'CONFIRMED' if res['filter_add']['f1'] > best_single else 'REFUTED'}: "
         f"filter+add F1 {res['filter_add']['f1']:.3f} vs best standalone "
         f"{best_single:.3f} (haiku:p2, exp81). The axes "
         f"{'compose' if res['filter_add']['f1'] > best_single else 'do NOT compose - pick one extractor rather than build a pipeline'}.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp82_hybrid.json").write_text(json.dumps({
    "n_docs": len(docs), "arms": res, "verdicts": v,
    "exp81_reference": {"rebel_f1": REBEL_F1, "haiku_p2_f1": HAIKU_F1},
    "scope": ("Same 12 documents, same scoring and entity matching as exp76/81, "
              "so all numbers are directly comparable. Candidates shown to the "
              "filter are capped at 80 per document and restricted to those "
              "whose relation maps into the vocabulary, since judging "
              "unmappable candidates cannot affect the score."),
}, indent=1))
print("\n[done] results/exp82_hybrid.json")
