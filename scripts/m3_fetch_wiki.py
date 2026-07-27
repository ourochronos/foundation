"""M3 — Wikipedia seed fetcher (Math + Epistemology + mathematician bios).

Fetches plaintext extract AND raw wikitext (infobox params + [[wikilinks]]
are the ground truth M3's targets are scored against). Branches one hop by
link frequency from the seed set to ~200 pages. Resumable; polite.

Usage: .venv/bin/python scripts/m3_fetch_wiki.py
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "wiki" / "pages"
OUT.mkdir(parents=True, exist_ok=True)
API = "https://en.wikipedia.org/w/api.php"
HDR = {"User-Agent": "foundation-research/0.1 (zonk1024@gmail.com)"}

MATH = ["Pythagorean theorem", "Group theory", "Topology", "Calculus",
        "Prime number", "Set theory", "Gödel's incompleteness theorems",
        "Probability theory", "Linear algebra", "Number theory",
        "Real analysis", "Graph theory", "Category theory",
        "Differential equation", "Euclidean geometry", "Non-Euclidean geometry",
        "Mathematical proof", "Axiom", "Riemann hypothesis",
        "Fundamental theorem of arithmetic", "Infinity", "Zero",
        "Complex number", "Fourier transform", "Game theory",
        "Information theory", "Chaos theory", "Fractal", "Knot theory",
        "Combinatorics", "Mathematical logic", "Model theory",
        "Fields Medal", "Hilbert's problems", "Millennium Prize Problems"]
EPIST = ["Epistemology", "Knowledge", "Justified true belief",
         "Gettier problem", "Bayesian epistemology", "Empiricism",
         "Rationalism", "Philosophical skepticism", "Coherentism",
         "Foundationalism", "Reliabilism", "A priori and a posteriori",
         "Belief", "Truth", "Justification (epistemology)",
         "Occam's razor", "Falsifiability", "Scientific method",
         "Induction (philosophy)", "Problem of induction", "Epistemic virtue",
         "Testimony (philosophy)", "Social epistemology", "Evidence",
         "Certainty", "Fallibilism", "Pragmatism", "Internalism and externalism"]
BIOS = ["Leonhard Euler", "Carl Friedrich Gauss", "Emmy Noether",
        "David Hilbert", "Srinivasa Ramanujan", "Georg Cantor",
        "Andrey Kolmogorov", "Paul Erdős", "Alexander Grothendieck",
        "Kurt Gödel", "Bertrand Russell", "Alfred North Whitehead",
        "Henri Poincaré", "Évariste Galois", "Niels Henrik Abel",
        "Sophie Germain", "Ada Lovelace", "Alan Turing", "John von Neumann",
        "Claude Shannon", "Norbert Wiener", "G. H. Hardy",
        "John Edensor Littlewood", "Terence Tao", "Grigori Perelman",
        "Andrew Wiles", "Pierre de Fermat", "Blaise Pascal",
        "René Descartes", "Gottfried Wilhelm Leibniz", "Isaac Newton",
        "Immanuel Kant", "David Hume", "John Locke", "George Berkeley",
        "Karl Popper", "Thomas Kuhn", "Willard Van Orman Quine",
        "Edmund Gettier", "Alvin Goldman", "Ludwig Wittgenstein",
        "Gottlob Frege", "Rudolf Carnap", "Hypatia", "Al-Khwarizmi",
        "Omar Khayyam", "Brahmagupta", "Aryabhata", "Euclid", "Archimedes",
        "Pythagoras", "Maryam Mirzakhani", "Katherine Johnson",
        "Mary Cartwright", "Julia Robinson", "Olga Ladyzhenskaya"]
SEEDS = MATH + EPIST + BIOS
import os
TARGET = int(os.environ.get("WIKI_TARGET", "200"))


def fetch(title: str) -> dict | None:
    try:
        r = requests.get(API, params={
            "action": "query", "format": "json", "redirects": 1,
            "prop": "extracts|revisions", "explaintext": 1,
            "rvprop": "content|ids|timestamp", "rvslots": "main",
            "titles": title}, headers=HDR, timeout=30)
        pages = r.json()["query"]["pages"]
        pg = next(iter(pages.values()))
        if "missing" in pg:
            return None
        rev = pg["revisions"][0] if "revisions" in pg else {}
        wikitext = rev.get("slots", {}).get("main", {}).get("*", "")
        # revid pins provenance: claims cite title@revid, not a moving page
        return {"title": pg["title"], "text": pg.get("extract", ""),
                "wikitext": wikitext, "revid": rev.get("revid"),
                "rev_timestamp": rev.get("timestamp")}
    except Exception as e:
        print(f"  ! {title}: {e}", flush=True)
        return None


def slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", t)[:80]


def links_of(wikitext: str) -> list[str]:
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]", wikitext):
        t = m.group(1).strip()
        if ":" not in t and len(t) > 2:
            out.append(t)
    return out


have = {json.loads(p.read_text())["title"] for p in OUT.glob("*.json")}
print(f"[fetch] {len(have)} already present", flush=True)
queue = [t for t in SEEDS]
link_votes: Counter = Counter()
n_seed = 0
for t in queue:
    if len(have) >= TARGET:
        break
    if t in have:
        continue
    d = fetch(t)
    time.sleep(0.3)
    if not d or len(d["text"]) < 500 or d["title"] in have:
        continue
    (OUT / f"{slug(d['title'])}.json").write_text(json.dumps(d))
    have.add(d["title"])
    n_seed += 1
    for ln in links_of(d["wikitext"]):
        if ln not in have:
            link_votes[ln] += 1
    if n_seed % 20 == 0:
        print(f"[fetch] seeds {n_seed}, total {len(have)}", flush=True)
print(f"[fetch] seeds done: {len(have)} pages", flush=True)

for rnd in range(3):
    if len(have) >= TARGET:
        break
    # harvest votes from the on-disk corpus: resuming runs (all seeds
    # cached) otherwise see an empty branch pool and stop at the seeds
    link_votes = Counter()
    for p in OUT.glob("*.json"):
        for ln in links_of(json.loads(p.read_text())["wikitext"]):
            if ln not in have:
                link_votes[ln] += 1
    print(f"[fetch] round {rnd}: {len(link_votes)} candidate links",
          flush=True)
    grew = False
    for t, votes in link_votes.most_common(4 * TARGET):
        if len(have) >= TARGET:
            break
        if votes < 3 or t in have:
            continue
        d = fetch(t)
        time.sleep(0.3)
        if not d or len(d["text"]) < 500 or d["title"] in have:
            continue
        (OUT / f"{slug(d['title'])}.json").write_text(json.dumps(d))
        have.add(d["title"])
        grew = True
        if len(have) % 20 == 0:
            print(f"[fetch] total {len(have)}", flush=True)
    if not grew:
        break

n_ib = sum(1 for p in OUT.glob("*.json")
           if "{{Infobox" in json.loads(p.read_text())["wikitext"]
           or "{{infobox" in json.loads(p.read_text())["wikitext"])
print(f"[done] {len(have)} pages, {n_ib} with infoboxes", flush=True)
