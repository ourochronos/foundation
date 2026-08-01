"""Annotation pilot: can two independent passes encode the same sentence the same way?

Three panel rounds each found a fatal-class flaw, and the flaws that remain are
**agreement failures** — encoding non-determinism, polarity/marker ordering,
whether modality's three values are separable. Review cannot measure agreement;
one reviewer found the encoding problem by *imagining* two annotators diverging.
So this measures it.

**What this is and is not.** Two independent passes by two different models
(Haiku via API, Gemma 4 12B locally), given the identical schema spec. That is
inter-MODEL agreement, not inter-annotator agreement, and it will be optimistic
in ways human annotators would not be — both are instruction-followers reading
the same rules, and they share failure modes humans do not. It still finds
encoding ambiguity, which is the question the schema cannot answer about itself:
if two readers of the same spec produce incomparable shapes for one sentence,
the spec is underdetermined regardless of who the readers are.

**Sampling is stratified toward the constructs under test, not random.** Random
sentences are mostly simple declaratives where agreement is trivially high and
says nothing. The strata are the four things three rounds of review argued about:

  negated     does polarity/marker ordering decide the same way?
  attributed  does the canonical-form rule stop one pass reifying and the other flattening?
  hedged      is modality separable from stance, or does the hedge migrate?
  plain       control - agreement here should be high, and if it is not the
              instrument is broken rather than the schema

Predictions, registered before running:

- **A1** plain-sentence agreement is high (>0.8 on the triple), confirming the
  instrument works at all.
- **A2** the **reification choice** is the worst-agreeing field — it is the one
  reification created and the canonical-form rule is the newest, least-tested
  part of the schema.
- **A3** polarity agrees better than modality, because negation has an explicit
  lexical cue and hedging shades continuously.

Usage: .venv/bin/python scripts/exp80_annotation_pilot.py [n_per_stratum]
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
K = int(sys.argv[1]) if len(sys.argv) > 1 else 12
OUT = ROOT / "results" / "exp80_pilot.jsonl"

NEG = re.compile(r"\b(?:is|are|was|were|has|have|does|do|did|can|could|will|would)\s+not\b"
                 r"|\bcannot\b|\bnever\b|\bn't\b|\b(?:denies|denied|rejects|rejected|"
                 r"refutes|refuted|fails\s+to|lacks)\b", re.I)
ATTR = re.compile(r"\b(?:argued?|argues|contends?|holds?|claims?|maintains?|asserts?|"
                  r"reported?|reports|according to|denied|denies|suggests?|writes?|"
                  r"said|says)\b", re.I)
HEDGE = re.compile(r"\b(?:may|might|could|possibly|perhaps|likely|suggests?|appears?|"
                   r"seems?|is consistent with|tends? to|if\b|unless\b)\b", re.I)

SPEC = """You are annotating sentences into a claim schema. Follow the rules EXACTLY.

Output ONLY a JSON object:
{"assertions":[{"id":"a1","subject":"<text>","predicate":"<text>","object":"<text>",
                "polarity":"+"|"-","modality":"asserted"|"hedged"|"hypothetical",
                "object_marker":null|"NONE"|"SOME",
                "scope":[{"dimension":"temporal"|"assumption"|"spatial","text":"..."}],
                "reified_from":null|"<id of the assertion this one is ABOUT>",
                "stance":null|"SAY"|"ARGUE"|"DENY"|"DOUBT"}]}

RULES, in priority order:
1. REIFY ONLY WHEN THE SOURCE ATTRIBUTES. A stance verb with a holder
   ("Smith denied X", "the Times reported X") produces TWO assertions: the inner
   claim, and an outer one whose subject is the holder, whose stance is set, and
   whose reified_from points at the inner id. Nothing else reifies.
2. CONDITIONALS ARE SCOPE, never reified. "If the ban passes, prices rise" is ONE
   assertion (prices, rise) with scope dimension "assumption".
3. HEDGES ATTACH TO THE CLAIM THEY HEDGE, never to the stance. "Smith suggests X
   may cause Y" is stance SAY on the outer, modality "hedged" on the inner.
4. POLARITY/MARKER ORDER: if the object is quantified to nothing, use
   object_marker NONE and polarity "+". Otherwise polarity "-" only if a negation
   cue scopes the relation. Lexical negation resolves to the predicate first:
   "childless" and "lacked children" are (x, has_child, -, marker NONE, polarity +).
5. scope records ONLY what the text states. Absent means unstated, not unrestricted.

Sentence: {sent}
"""


def sentences():
    pool = []
    for dom in ("phil", "econ", "pol"):
        for f in sorted((ROOT / "data" / dom / "pages").glob("*.json")):
            pg = json.loads(f.read_text())
            for s in re.split(r"(?<=[.!?])\s+", pg["text"]):
                s = " ".join(s.split())
                if 50 < len(s) < 240:
                    pool.append((dom, s))
    rows = json.loads((ROOT / "data" / "news" / "multi_news_300.json").read_text())
    for r in rows[:60]:
        for art in r["doc"].split("|||||")[:2]:
            for s in re.split(r"(?<=[.!?])\s+", art):
                s = " ".join(s.split())
                if 50 < len(s) < 240:
                    pool.append(("news", s))
    strata = {"negated": [], "attributed": [], "hedged": [], "plain": []}
    for dom, s in pool:
        if NEG.search(s):
            strata["negated"].append((dom, s))
        elif ATTR.search(s):
            strata["attributed"].append((dom, s))
        elif HEDGE.search(s):
            strata["hedged"].append((dom, s))
        else:
            strata["plain"].append((dom, s))
    out = []
    for name, items in strata.items():
        step = max(len(items) // K, 1)
        out += [(name, d, s) for d, s in items[::step][:K]]
    return out


def haiku(prompt):
    try:
        r = subprocess.run(["copilot", "-p", prompt, "--no-ask-user",
                            "--model", "claude-haiku-4.5", "--no-auto-update"],
                           capture_output=True, text=True, timeout=300)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def gemma(prompt):
    try:
        r = subprocess.run([str(ROOT / "gemma.sh"), "-n", "700", "-p", prompt],
                           capture_output=True, text=True, timeout=600)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def parse(txt):
    best = None
    for m in re.finditer(r'\{(?:[^{}]|\{[^{}]*\})*"assertions"(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}',
                         txt, re.S):
        try:
            d = json.loads(m.group(0))
            if isinstance(d.get("assertions"), list):
                best = d
        except Exception:                                        # noqa: BLE001
            continue
    if best is None:                       # fall back: collect bare assertion objects
        objs = []
        for m in re.finditer(r'\{[^{}]*"polarity"[^{}]*\}', txt):
            try:
                objs.append(json.loads(m.group(0)))
            except Exception:                                    # noqa: BLE001
                pass
        best = {"assertions": objs} if objs else None
    return best


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", str(s or "").lower()).strip()


sample = sentences()
print(f"{len(sample)} sentences: "
      f"{dict(collections.Counter(x[0] for x in sample))}", flush=True)
OUT.write_text("")
recs = []
for i, (stratum, dom, sent) in enumerate(sample):
    p = SPEC.replace("{sent}", sent)
    a, b = parse(haiku(p)), parse(gemma(p))
    rec = {"i": i, "stratum": stratum, "domain": dom, "sent": sent,
           "A": a, "B": b}
    recs.append(rec)
    with OUT.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    if (i + 1) % 10 == 0:
        ok = sum(1 for r in recs if r["A"] and r["B"])
        print(f"  {i+1}/{len(sample)}  both parsed: {ok}", flush=True)

# ---------------------------------------------------------------- scoring --
def align(A, B):
    """Pair assertions across passes by subject+object overlap, greedily."""
    pairs, usedB = [], set()
    for x in A:
        best, bs = None, 0.0
        for j, y in enumerate(B):
            if j in usedB:
                continue
            sx, ox = set(norm(x.get("subject")).split()), set(norm(x.get("object")).split())
            sy, oy = set(norm(y.get("subject")).split()), set(norm(y.get("object")).split())
            s = (len(sx & sy) / max(len(sx | sy), 1) + len(ox & oy) / max(len(ox | oy), 1)) / 2
            if s > bs:
                best, bs = j, s
        if best is not None and bs >= 0.34:
            usedB.add(best)
            pairs.append((x, B[best]))
    return pairs


stats = collections.defaultdict(lambda: collections.Counter())
for r in recs:
    if not (r["A"] and r["B"]):
        stats[r["stratum"]]["unparsed"] += 1
        continue
    A, B = r["A"]["assertions"], r["B"]["assertions"]
    st = stats[r["stratum"]]
    st["sentences"] += 1
    # reification choice: did BOTH decide to reify, or neither?
    ra = any(x.get("reified_from") or x.get("stance") for x in A)
    rb = any(x.get("reified_from") or x.get("stance") for x in B)
    st["reify_agree"] += int(ra == rb)
    st["count_agree"] += int(len(A) == len(B))
    for x, y in align(A, B):
        st["aligned"] += 1
        # Predicate is free text, so exact match is too strict: "causes" vs
        # "cause", "is compatible with" vs "compatible with" would score 0 while
        # plainly agreeing. Token overlap measures agreement; exact match
        # measures whether the vocabulary is converging, and both are reported
        # because they answer different questions.
        px, py = set(norm(x.get("predicate")).split()), set(norm(y.get("predicate")).split())
        st["pred_exact"] += int(px == py)
        st["triple_agree"] += int(len(px & py) / max(len(px | py), 1) >= 0.5)
        st["polarity_agree"] += int(x.get("polarity") == y.get("polarity"))
        st["modality_agree"] += int(x.get("modality") == y.get("modality"))
        st["marker_agree"] += int((x.get("object_marker") or None)
                                  == (y.get("object_marker") or None))
        st["scope_agree"] += int(bool(x.get("scope")) == bool(y.get("scope")))

print(f"\n{'stratum':>11} {'sents':>6} {'align':>6} {'reify':>7} {'polarity':>9} "
      f"{'modality':>9} {'marker':>7} {'scope':>7} {'pred':>6}")
res = {}
for k in ("plain", "negated", "attributed", "hedged"):
    s = stats[k]
    n, al = max(s["sentences"], 1), max(s["aligned"], 1)
    res[k] = {"sentences": s["sentences"], "unparsed": s["unparsed"],
              "aligned": s["aligned"],
              "reify": round(s["reify_agree"] / n, 3),
              "polarity": round(s["polarity_agree"] / al, 3),
              "modality": round(s["modality_agree"] / al, 3),
              "marker": round(s["marker_agree"] / al, 3),
              "scope": round(s["scope_agree"] / al, 3),
              "predicate_overlap": round(s["triple_agree"] / al, 3),
              "predicate_exact": round(s["pred_exact"] / al, 3)}
    r_ = res[k]
    print(f"  {k:>9} {s['sentences']:>6} {s['aligned']:>6} {r_['reify']:>7.3f} "
          f"{r_['polarity']:>9.3f} {r_['modality']:>9.3f} {r_['marker']:>7.3f} "
          f"{r_['scope']:>7.3f} {r_['predicate_overlap']:>6.3f}")

allal = sum(stats[k]["aligned"] for k in res)
def overall(f):
    return sum(stats[k][f] for k in res) / max(allal, 1)
v = []
v.append(f"A1 {'CONFIRMED' if res['plain']['predicate_overlap'] > 0.8 else 'REFUTED'}: "
         f"plain-sentence predicate agreement {res['plain']['predicate_overlap']:.3f} "
         f"(exact {res['plain']['predicate_exact']:.3f}) — the instrument "
         f"{'works' if res['plain']['predicate_overlap'] > 0.8 else 'may be broken, so lower numbers below are not evidence about the schema'}.")
worst = min(("reify", sum(res[k]['reify'] for k in res) / 4),
            ("polarity", overall("polarity_agree")),
            ("modality", overall("modality_agree")),
            ("marker", overall("marker_agree")),
            ("scope", overall("scope_agree")), key=lambda x: x[1])
v.append(f"A2 {'CONFIRMED' if worst[0] == 'reify' else 'REFUTED'}: worst-agreeing "
         f"field is {worst[0]} at {worst[1]:.3f}.")
v.append(f"A3 {'CONFIRMED' if overall('polarity_agree') > overall('modality_agree') else 'REFUTED'}"
         f": polarity {overall('polarity_agree'):.3f} vs modality "
         f"{overall('modality_agree'):.3f}.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp80_pilot.json").write_text(json.dumps({
    "n": len(sample), "strata": res, "verdicts": v,
    "scope": ("Two independent passes by DIFFERENT MODELS (Haiku 4.5 via API, "
              "Gemma 4 12B local) given an identical schema spec. This is "
              "inter-MODEL agreement and is optimistic relative to human "
              "annotators, who do not share instruction-following failure "
              "modes. Sampling is stratified toward the constructs three panel "
              "rounds argued about, because agreement on plain declaratives is "
              "trivially high and uninformative. Alignment pairs assertions by "
              "subject+object token overlap before comparing fields, so field "
              "agreement is conditional on the two passes finding the same "
              "claim at all."),
}, indent=1))
print(f"\n[done] results/exp80_pilot.json  (+ per-sentence in {OUT.name})")
