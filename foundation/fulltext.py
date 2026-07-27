"""Clean the retained arXiv fulltext extract into paper BODY text.

The source layer keeps whatever the HTML render gave us (docs/13), which
means the first few hundred characters are arXiv's own page furniture and
— for papers with no HTML render, where the fetch fell back to /abs/ —
the "fulltext" is an abstract page carrying bookmarking widgets rather
than a paper. Measured on the AI slice: "PDF" appears in 442/467
extracts and "CatalyzeX"/"DagsHub"/"BibTeX" in 94, all of it template,
none of it authored. Left in, that furniture dominates any frequency
count taken over the corpus.

Keep this separate from the source layer: the raw extract is immutable,
cleaning happens on read.
"""
from __future__ import annotations

import re

# arXiv HTML-render chrome, in the order it appears before the body
_CHROME = [
    r"Report GitHub Issue.*?Submit in GitHub",
    r"arXiv is now an independent nonprofit!\s*Learn more\s*&times;",
    r"Back to arXiv", r"Why HTML\?", r"Report Issue", r"Back to Abstract",
    r"Download PDF", r"Content selection saved\.",
    r"Describe the issue below:", r"Description:", r"Submit without GitHub",
    r"HTML \(experimental\)",
]
# /abs/ fallback pages: bookmarking + tooling widgets, never paper text
_ABS_WIDGETS = ("CatalyzeX", "DagsHub", "ScienceCast", "TXYZ", "GotitPub",
                "DataCite", "MathJax", "LaTeXML", "BibTeX", "Bibliographic",
                "alphaXiv", "Hugging Face", "Connected Papers", "Litmaps",
                "Semantic Scholar", "smartCite", "Bibliographic Explorer")


def is_abs_fallback(text: str) -> bool:
    """True when the extract is an arXiv /abs/ page, not a rendered paper.

    Those pages carry the abstract and a wall of third-party widget names
    and nothing else — resource mining over them yields tool brands.
    """
    hits = sum(1 for w in _ABS_WIDGETS if w in text[:20000])
    return hits >= 4


def clean(text: str, max_chars: int = 40000) -> str:
    """Strip arXiv chrome and return body text ('' for /abs/ fallbacks)."""
    if not text:
        return ""
    if is_abs_fallback(text):
        return ""
    out = text
    for pat in _CHROME:
        out = re.sub(pat, " ", out, flags=re.S | re.I)
    # the widget block can also trail a rendered page's footer
    for w in _ABS_WIDGETS:
        out = out.replace(w, " ")
    out = re.sub(r"\s+", " ", out).strip()
    return out[:max_chars]


def resource_window(text: str, head: int = 3500, exp: int = 5000) -> str:
    """Where shared resources are actually named.

    Two disjoint regions, because the two kinds of resource live apart:
    base models and prior methods get named in the intro/related work,
    while benchmarks and datasets appear in the experimental setup. A
    single leading window catches the first and misses the second.
    """
    body = body_after_intro(text, max_chars=10 ** 9)
    if not body:
        return ""
    m = None
    for m in re.finditer(r"(?i)\b(?:\d+\s+)?(?:experiment[s]?|evaluation|"
                         r"experimental\s+setup|results?\s+and\s+analysis|"
                         r"empirical\s+(?:evaluation|study))\b", body):
        if m.start() > len(body) * 0.25:
            break
    tail = body[m.start():m.start() + exp] if m else ""
    return (body[:head] + ("\n[...]\n" + tail if tail else ""))


def body_after_intro(text: str, max_chars: int = 30000) -> str:
    """Body from the first section heading onward.

    Resource mentions (benchmarks, base models, baselines) concentrate in
    method/experiment sections; the leading table of contents repeats
    section titles and inflates nothing useful.
    """
    t = clean(text, max_chars=10 ** 9)
    if not t:
        return ""
    m = re.search(r"\b1\s+Introduction\b", t)
    if m:
        nxt = re.search(r"\b1\s+Introduction\b", t[m.end():])
        t = t[m.end() + nxt.start():] if nxt else t[m.start():]
    return t[:max_chars]
