"""Fetch corpora chosen BECAUSE they should contain disagreement.

Two domains, deliberately different in how their disagreement is shaped.
**Economics** disputes are largely causal and empirical — what causes inflation,
whether a minimum wage costs jobs — so competing schools assign different
causes to the same effect. **Philosophy** disputes are definitional and
normative, and its positions are named and self-identifying (compatibilism,
physicalism, deontology), which makes attribution far cleaner in the text.
Having both means a finding that holds in one and not the other is visible as
such, rather than being read as a property of disagreement in general.

Every corpus so far was chosen for availability, and all of them turned out to
be structurally incapable of corroboration or contradiction: encyclopedia
articles state one settled view, and papers cite rather than repeat (exp70).
The agreement and conflict machinery has therefore never had anything to count.

Competing schools of thought are the opposite case by construction. They make
claims about the **same entities** — inflation, unemployment, the minimum wage,
quantitative easing — and reach **opposing conclusions**, and Wikipedia reports
those positions *with attribution* ("Keynesians hold that…", "Austrian
economists argue…"). That attribution is exactly an `under_assumption`
qualifier, which makes this the first corpus that can exercise:

- **agreement** — schools that concur on a proposition
- **scoped non-conflict** — two schools disagreeing, each claim carried under
  its own assumption, both true within scope and correctly NOT flagged
- **genuine conflict** — the same proposition asserted unscoped by sources that
  contradict each other

Two page sets, and both are needed. The *schools* supply the assumption labels;
the *topics* are where the schools collide, and a corpus of schools alone would
have the labels with nothing to attach them to.

Usage: .venv/bin/python scripts/econ_fetch.py [econ|phil]
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = __import__("sys").argv[1] if len(__import__("sys").argv) > 1 else "econ"
OUT = ROOT / "data" / DOMAIN / "pages"
OUT.mkdir(parents=True, exist_ok=True)
API = "https://en.wikipedia.org/w/api.php"
HDR = {"User-Agent": "foundation-research/0.1 (zonk1024@gmail.com)"}

SCHOOLS = [
    "Keynesian economics", "Austrian School", "Monetarism",
    "Modern Monetary Theory", "Marxian economics", "Neoclassical economics",
    "New Keynesian economics", "Chicago school of economics",
    "Post-Keynesian economics", "Supply-side economics",
    "Behavioral economics", "Institutional economics", "Classical economics",
    "New classical macroeconomics", "Georgism", "Ecological economics",
    "Heterodox economics", "Saltwater and freshwater economics",
]
TOPICS = [
    "Inflation", "Minimum wage", "Quantitative easing", "Fiscal policy",
    "Monetary policy", "Business cycle", "Great Depression", "Phillips curve",
    "Money supply", "Unemployment", "Free trade", "Tariff",
    "Government debt", "Austerity", "Universal basic income", "Rent control",
    "Economic bubble", "Stagflation", "Crowding out (economics)",
    "Laffer curve", "Efficient-market hypothesis", "Labor theory of value",
    "Say's law", "Liquidity trap", "Velocity of money",
    "Natural rate of unemployment", "Capital control", "Deflation",
    "Interest rate", "Great Recession", "Money creation", "Hyperinflation",
    "Trickle-down economics", "Comparative advantage", "Externality",
]

# Philosophy: positions are NAMED, which makes attribution far cleaner than in
# economics — "compatibilists hold" is unambiguous in a way that "some
# economists argue" is not. The topics are the classic loci where the named
# positions collide head-on.
PHIL_POSITIONS = [
    "Compatibilism", "Libertarianism (metaphysics)", "Hard determinism",
    "Physicalism", "Dualism (philosophy of mind)", "Functionalism (philosophy of mind)",
    "Property dualism", "Eliminative materialism", "Panpsychism",
    "Deontology", "Consequentialism", "Utilitarianism", "Virtue ethics",
    "Moral realism", "Moral relativism", "Error theory", "Emotivism",
    "Foundationalism", "Coherentism", "Reliabilism", "Internalism and externalism",
    "Philosophical skepticism", "Direct and indirect realism",
    "Philosophical realism", "Nominalism", "Platonism", "Conceptualism",
    "Empiricism", "Rationalism", "Logical positivism", "Falsifiability",
    "Scientific realism", "Instrumentalism", "Social constructionism",
]
PHIL_TOPICS = [
    "Free will", "Determinism", "Mind–body problem", "Consciousness",
    "Hard problem of consciousness", "Qualia", "Personal identity",
    "Ship of Theseus", "Problem of universals", "Trolley problem",
    "Is–ought problem", "Naturalistic fallacy", "Moral responsibility",
    "Gettier problem", "Problem of induction", "Münchhausen trilemma",
    "Problem of evil", "Philosophy of science", "Demarcation problem",
    "Theory of forms", "Abstract and concrete", "Truth", "Knowledge",
    "Justified true belief", "Causality", "Identity (philosophy)",
    "Intentionality", "Chinese room", "Philosophical zombie",
    "Experience machine", "Veil of ignorance", "Categorical imperative",
]


def fetch(titles):
    got = 0
    for t in titles:
        p = OUT / (t.replace("/", "_").replace(" ", "_") + ".json")
        if p.exists():
            got += 1
            continue
        r = requests.get(API, headers=HDR, timeout=60, params={
            "action": "query", "format": "json", "prop": "extracts|revisions",
            "rvprop": "ids|timestamp", "rvslots": "main", "explaintext": 1,
            "redirects": 1, "titles": t})
        pages = r.json().get("query", {}).get("pages", {})
        for _, d in pages.items():
            if "extract" not in d or len(d["extract"]) < 500:
                print(f"  MISS {t}", flush=True)
                continue
            rev = (d.get("revisions") or [{}])[0]
            p.write_text(json.dumps({
                "title": d["title"], "text": d["extract"],
                "revid": rev.get("revid"), "rev_timestamp": rev.get("timestamp"),
                "kind": "position" if t in POSITIONS else "topic",
                "domain": DOMAIN}))
            got += 1
            print(f"  ok   {d['title']} ({len(d['extract'])} chars)", flush=True)
        time.sleep(0.4)                       # polite
    return got


POSITIONS, SUBJECTS = ((SCHOOLS, TOPICS) if DOMAIN == "econ"
                       else (PHIL_POSITIONS, PHIL_TOPICS))
print(f"domain={DOMAIN}  positions: {len(POSITIONS)}   topics: {len(SUBJECTS)}",
      flush=True)
n = fetch(POSITIONS) + fetch(SUBJECTS)
sizes = [len(json.loads(p.read_text())["text"]) for p in OUT.glob("*.json")]
print(f"\n[done] {n} pages in data/{DOMAIN}/pages/, "
      f"{sum(sizes):,} chars total, median {sorted(sizes)[len(sizes) // 2]:,}")
