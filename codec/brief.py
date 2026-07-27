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


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


def subject_brief(subject: str, pool: list[dict],
                  aspect: str | None = None) -> dict:
    """Render a grounded brief. Each entry: {subject, pid, object,
    statement, page, sid}. Returns {sentences: [{text, kind, citations}],
    abstain: bool, reason}."""
    own = [e for e in pool if _norm(e.get("subject", "")) == _norm(subject)
           and e.get("pid") and e.get("object")]
    if aspect is not None:
        own = [e for e in own if e["pid"] == aspect]
    if not own:
        return {"sentences": [], "abstain": True,
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
            tpl = TEMPLATES.get(pid, GENERIC)
            sentences.append({
                "text": tpl.format(s=subject, o=e["object"], p=pid),
                "kind": "fact", "pid": pid, "citations": [e["sid"]]})
    return {"sentences": sentences, "abstain": False, "reason": ""}
