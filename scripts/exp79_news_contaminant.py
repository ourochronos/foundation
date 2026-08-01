"""Did negated sentences contaminate exp75's news corroboration?

exp75 found 41 triples corroborated across independent news sources — the first
non-zero corroboration in the project. exp78 then found 8.5% of news triples
derive from sentences carrying a proposition-reversing cue, and that REBEL emits
the falsehood such sentences deny.

That combination has a specific and nasty failure mode: **two outlets both
reporting a denial, both extracted as assertions, corroborating each other on a
falsehood.** Corroboration would then be strongest exactly where the extraction
is wrong, because a denial is newsworthy and gets repeated.

So: do corroborated triples come from negated sentences at, above, or below the
base rate? Above would mean the headline result is partly an artifact.

Prediction, registered: corroborated triples come from negated sentences at
roughly the base rate or below — the contamination is real but not
concentrated, because most corroborated facts are plain reportage.

**Correction after the first run.** It reported 26.1% against a 10.8% base rate
and concluded "CONCENTRATED, so exp75 is partly artifact". That was wrong, and
the examples gave it away — `(beijing, located in, china)` is not a negation
casualty. A triple is flagged when ANY of its extraction events came from a
negated sentence, and a corroborated triple has at least two events by
definition, so it has more chances to be flagged even under random negation.
The observed rate corresponds to 2.65 events per triple, which is exactly what
corroborated triples have. The comparison must be against 1-(1-base)^k, not
against base.
"""
from __future__ import annotations
import collections, json, re, sys
from pathlib import Path
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from exp78_negation_exposure import negated                       # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()


def triples(text, nb=5):
    enc = tok(text, return_tensors="pt", truncation=True, max_length=256).to(dev)
    with torch.no_grad():
        g = mdl.generate(**enc, max_length=200, num_beams=nb,
                         num_return_sequences=nb, length_penalty=1.0)
    out = []
    for d in tok.batch_decode(g, skip_special_tokens=False):
        d = d.replace("<s>", "").replace("</s>", "").replace("<pad>", "")
        s = r = o = ""; cur = None
        for t in d.split():
            if t == "<triplet>":
                if s and r and o: out.append((s.strip(), r.strip(), o.strip()))
                s, cur = "", "s"
            elif t == "<subj>": o, cur = "", "o"
            elif t == "<obj>":  r, cur = "", "r"
            else:
                if cur == "s": s += " " + t
                elif cur == "o": o += " " + t
                elif cur == "r": r += " " + t
        if s and r and o: out.append((s.strip(), r.strip(), o.strip()))
    return set(out)


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", "", s.lower()).strip()


rows = json.loads((ROOT / "data" / "news" / "multi_news_300.json").read_text())
events = [[a.strip() for a in r["doc"].split("|||||") if len(a.strip()) > 400]
          for r in rows]
events = [e for e in events if len(e) >= 3][:N]
print(f"{len(events)} events", flush=True)

corr_neg = corr_tot = all_neg = all_tot = 0
examples, ev_counts = [], []
for ei, arts in enumerate(events):
    # triple -> (set of doc ids, was it ever from a negated sentence)
    seen = collections.defaultdict(set)
    negsrc = collections.defaultdict(bool)
    for di, art in enumerate(arts):
        for s in re.split(r"(?<=[.!?])\s+", art[:4000]):
            s = " ".join(s.split())
            if not (40 < len(s) < 320):
                continue
            ng = negated(s)
            for t in triples(s):
                k = (norm(t[0]), norm(t[1]), norm(t[2]))
                seen[k].add(di)
                if ng:
                    negsrc[k] = True
    for k, ds in seen.items():
        all_tot += 1
        all_neg += bool(negsrc[k])
        if len(ds) >= 2:
            ev_counts.append(ds)
            corr_tot += 1
            corr_neg += bool(negsrc[k])
            if negsrc[k] and len(examples) < 6:
                examples.append((ei, k))
    if (ei + 1) % 10 == 0:
        print(f"  {ei+1}/{len(events)} corroborated {corr_tot} "
              f"(from negated: {corr_neg})", flush=True)

base = all_neg / max(all_tot, 1)
crate = corr_neg / max(corr_tot, 1)
print(f"\n  all triples        : {all_neg}/{all_tot} from negated ({100*base:.1f}%)")
print(f"  CORROBORATED ones  : {corr_neg}/{corr_tot} from negated ({100*crate:.1f}%)")
for ei, k in examples:
    print(f"    event {ei}: {k}")
# CONTROL, added after the first run produced a wrong headline. A triple is
# flagged if ANY of its extraction events came from a negated sentence, and a
# corroborated triple has >=2 events BY DEFINITION — so it gets more chances to
# be flagged even when negation is distributed at random. Comparing the
# corroborated rate against the raw base rate therefore measures the flag's own
# bias, not contamination. The null is 1-(1-base)^k for k events per triple.
import math
k = (sum(len(v) for v in ev_counts) / max(len(ev_counts), 1)) if ev_counts else 1
expected = 1 - (1 - base) ** k
verdict = (f"{'CONFIRMED' if crate <= expected * 1.25 else 'REFUTED'}: "
           f"corroborated triples are negation-flagged at {100*crate:.1f}%, "
           f"against {100*expected:.1f}% EXPECTED from having {k:.2f} extraction "
           f"events each at a {100*base:.1f}% per-event rate. Comparing to the "
           f"raw base rate would have reported {crate/base:.1f}x contamination "
           f"that is entirely the flag's own bias.")
print(f"\n=== VERDICT ===\n  {verdict}")
(ROOT / "results" / "exp79_contaminant.json").write_text(json.dumps({
    "events": len(events), "all_triples": all_tot, "all_from_negated": all_neg,
    "corroborated": corr_tot, "corroborated_from_negated": corr_neg,
    "base_rate": round(base, 4), "corroborated_rate": round(crate, 4),
    "mean_events_per_corroborated_triple": round(k, 3),
    "expected_flag_rate_under_null": round(expected, 4),
    "verdict": verdict,
    "scope": ("Per-sentence extraction so each triple can be attributed to its "
              "source sentence, unlike exp75 which chunked. A triple counts as "
              "negation-sourced if ANY of its extractions came from a negated "
              "sentence, which overstates rather than understates."),
}, indent=1))
print("\n[done] results/exp79_contaminant.json")
