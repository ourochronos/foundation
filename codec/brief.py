"""Grounded subject briefs — templates + citations (D76: decoder out of
the loop; provenance beats prose).

subject_brief(subject, pool, aspect=None) renders store entries about
`subject` into template sentences, one citation per sentence. The pool may
be ADVERSARIAL (retrieval noise, other subjects' entries): the renderer
must never emit a sentence whose citation is another subject's entry —
that invariant is gate-tested (M5 distractor control), not assumed.

Functional pids (the D78 infobox-complete set) with >1 distinct object
render as a DISPUTE view citing every claimant — Track I surfacing at the
answer layer.
"""
from __future__ import annotations

import re

FUNCTIONAL_PIDS = {"P569", "P570", "P19", "P20", "P26", "P27"}

TEMPLATES = {
    "P569": "{s} was born on {o}.",
    "P570": "{s} died on {o}.",
    "P19": "{s} was born in {o}.",
    "P20": "{s} died in {o}.",
    "P26": "{s} was married to {o}.",
    "P27": "{s} was a citizen of {o}.",
    "P69": "{s} was educated at {o}.",
    "P108": "{s} worked at {o}.",
    "P106": "{s} worked as a {o}.",
    "P166": "{s} received the {o}.",
    "P800": "{s} is known for {o}.",
    "P50": "{s} authored {o}.",
    "P31": "{s} is a {o}.",
    "P937": "{s} worked in {o}.",
    "P39": "{s} held the position of {o}.",
    "P463": "{s} was a member of {o}.",
    "P184": "{s} was advised by {o}.",
    "P185": "{s} advised {o}.",
    "P551": "{s} lived in {o}.",
    "P571": "{s} was established in {o}.",
    "P112": "{s} was founded by {o}.",
    "P127": "{s} is owned by {o}.",
    "P123": "{s} was published by {o}.",
    "P138": "{s} is named after {o}.",
    "P159": "{s} is headquartered in {o}.",
    "P276": "{s} is located in {o}.",
    "P170": "{s} was created by {o}.",
    "P36": "{s} has capital {o}.",
    "P17": "{s} is in {o}.",
    "P131": "{s} is located in {o}.",
}
GENERIC = "{s}: {p} — {o}."

# Verb-echo rendering (G4 round-1 finding, D81): when the cited statement
# contains a recognizable predicate BEFORE the object, echo that verb —
# the sentence is rendered at the strength of its evidence instead of the
# pid template's semantics ("wrote X" must not become "is known for X").
_ECHO_VERBS = [
    "was educated by", "was educated at", "educated by", "educated at",
    "was awarded", "worked on", "worked at", "worked in", "served as",
    "moved to", "settled in", "wrote", "authored", "published", "proved",
    "developed", "introduced", "founded", "discovered", "formulated",
    "established", "created", "tutored", "visited", "studied", "taught",
    "translated", "edited", "composed", "invented", "pioneered",
    "attended", "joined", "led", "directed", "won", "received", "married",
]
_ECHO_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _ECHO_VERBS) + r")\b", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


def _echo(subject: str, obj: str, statement: str) -> str | None:
    """Echo the statement's own predicate: last _ECHO_VERBS match that
    precedes the object's occurrence in the statement. None if the object
    isn't literally in the statement (paraphrase — pid template applies)."""
    lo = statement.lower().find(obj.lower())
    if lo < 0:
        return None
    hits = [m for m in _ECHO_RE.finditer(statement) if m.end() <= lo]
    if not hits:
        return None
    v = hits[-1].group(1)
    v = v if v.lower().startswith("was ") else v.lower()
    return f"{subject} {v} {obj}."


def _renderable(subject: str, e: dict) -> bool:
    """Per-entry render guards (each targets an observed G4-round-1
    defect family): quote-like objects are not entities; a statement
    that never names its subject is not evidence about the subject."""
    obj, st = str(e["object"]), str(e.get("statement", ""))
    if len(obj) > 60 or f" {obj.lower()} ".count(" i ") \
            or obj.count(",") >= 3:
        return False
    toks = [t for t in re.split(r"\s+", subject) if len(t) > 2]
    return any(t.lower() in st.lower() for t in toks) if toks else True


def subject_brief(subject: str, pool: list[dict],
                  aspect: str | None = None) -> dict:
    """Render a grounded brief. Each entry: {subject, pid, object,
    statement, page, sid}. Returns {sentences: [{text, kind, citations}],
    abstain: bool, reason}."""
    own = [e for e in pool if _norm(e.get("subject", "")) == _norm(subject)
           and e.get("pid") and e.get("object")]
    if aspect is not None:
        own = [e for e in own if e["pid"] == aspect]
    withheld = [e["sid"] for e in own if not _renderable(subject, e)]
    own = [e for e in own if _renderable(subject, e)]
    if not own:
        return {"sentences": [], "abstain": True, "withheld": withheld,
                "reason": (f"no stored claims about {subject!r}"
                           + (f" for {aspect}" if aspect else "")
                           + " — refusing rather than borrowing")}
    by_pid: dict[str, list[dict]] = {}
    for e in own:
        by_pid.setdefault(e["pid"], []).append(e)
    sentences = []
    for pid in sorted(by_pid, key=lambda p: (p not in FUNCTIONAL_PIDS, p)):
        entries = by_pid[pid]
        distinct: dict[str, list[dict]] = {}
        for e in entries:
            distinct.setdefault(_norm(e["object"]), []).append(e)
        if pid in FUNCTIONAL_PIDS and len(distinct) > 1:
            claims = "; ".join(
                f"{es[0]['object']!r} (per {', '.join(sorted({str(x['page']) for x in es}))})"
                for _, es in sorted(distinct.items()))
            sentences.append({
                "text": f"Sources disagree on {pid} for {subject}: {claims}.",
                "kind": "dispute", "pid": pid,
                "citations": [x["sid"] for es in distinct.values()
                              for x in es]})
            continue
        for _, es in sorted(distinct.items()):
            e = es[0]
            text = _echo(subject, str(e["object"]),
                         str(e.get("statement", "")))
            if text is None:
                text = TEMPLATES.get(pid, GENERIC).format(
                    s=subject, o=e["object"], p=pid)
            sentences.append({
                "text": text, "kind": "fact", "pid": pid,
                "citations": [e["sid"]]})
    return {"sentences": sentences, "abstain": False, "reason": "",
            "withheld": withheld}
