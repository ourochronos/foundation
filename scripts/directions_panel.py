"""Blind multi-model panel on STRATEGIC DIRECTION, not on claims (D175 hopper).

The adjudication loop (D86 onward) judges whether a stated claim is supported
by its evidence. This asks a different question the user has been holding in
the hopper since D174: **where should the program go next.**

Three things are deliberately different from `adjudicate.py`:

- **Four raters, not three.** The odd-panel argument (D154) exists to break
  ties on binary verdicts. There are no verdicts here and nothing to tie, so
  the reason to drop the author's own family disappears; diversity of view is
  the whole point and `claude-fable-5` goes back in. D154's finding that it is
  lenient under the verification prompt does not transfer to idea generation,
  and if it turns out to agree with the author suspiciously often that is
  itself readable in the transcript.
- **Blind to each other, as always.** Each model sees only the brief. Nothing
  is shared between calls, so agreement between two raters is real agreement
  rather than anchoring.
- **The brief leads with the refutations.** `docs/20-directions-brief.md`
  spends more room on what failed than on what worked, states outright that
  nothing needs preserving, and asks each rater to name the premise the author
  has stopped questioning. A brief that sells the work would return four
  polite endorsements and be worth nothing.

Two preambles. `directions` asks where the program should go; `review` asks
the panel to attack a concrete design before anything is built on it. The
review preamble is deliberately harsher: a design document sent to four models
that are not explicitly told to break it comes back with four endorsements and
a handful of style notes.

Usage:
  .venv/bin/python scripts/directions_panel.py
  .venv/bin/python scripts/directions_panel.py --brief docs/22-model-v0.md \
      --out model_v0 --preamble review [model]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALL = ["gpt-5.6-sol", "gemini-3.1-pro-preview", "grok-4.5", "claude-fable-5"]


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


BRIEF = ROOT / arg("--brief", "docs/20-directions-brief.md")
OUT = ROOT / "data" / arg("--out", "directions")
MODE = arg("--preamble", "directions")
OUT.mkdir(parents=True, exist_ok=True)
free = [a for a in sys.argv[1:] if not a.startswith("--")
        and a not in {arg(f, None) for f in ("--brief", "--out", "--preamble")}]
MODELS = [free[0]] if free else ALL

DIRECTIONS = """You are one of four independent reviewers, each answering blind \
— you will not see the others' answers, and they will not see yours. Consensus \
between you is worth nothing to the person asking. A view that is specific, \
falsifiable and different from what the others are likely to say is worth a \
great deal.

The author has explicitly said the existing work can be discarded in full and \
that sunk cost is not a consideration. Do not soften a recommendation to \
abandon something. Do not produce a balanced survey of options. Commit to \
positions.

Read the brief and answer its five questions.

--- BRIEF BEGINS ---
"""

REVIEW = """You are one of four independent reviewers, each answering blind — \
you will not see the others' answers and they will not see yours. Consensus \
between you is worth nothing to the person asking.

Below is a data model at v0. **Nothing has been built on it yet, and that is \
the point of showing it to you now.** Your job is to break it, not to \
appraise it. A design document sent to four reviewers who were not told this \
comes back with four endorsements and some style notes, which is worthless.

Give each of these directly, with no preamble and no summary of the document \
back to its author:

1. **The fatal flaw**, if there is one. A claim shape it cannot express, a \
merge that corrupts data, a case where contradiction detection silently \
fails, an identity failure under federation. Be concrete: give the specific \
example that breaks it.
2. **What forces a change to the CLOSED layer** within a year. That layer is \
supposed to be authored once; name the thing that will break it, and say \
whether to fix it now or accept the future migration.
3. **Where it is over-built.** Which part should be deleted outright because \
it is solving a problem this system will not actually have.
4. **The seven open questions in the final section**, answered directly and \
committally. Say "wrong" where you think it is wrong.
5. **What breaks first at scale** — 10^6 assertions on one Postgres instance, \
and separately, merging two stores of that size.

Where you would design it differently, show the alternative concretely — a \
schema fragment or a worked example, not a principle.

--- DOCUMENT BEGINS ---
"""


def ask(model: str, prompt: str) -> tuple[str, float]:
    t0 = time.time()
    r = subprocess.run(
        ["copilot", "-p", prompt, "--no-ask-user", "--model", model,
         "--no-auto-update"],
        capture_output=True, text=True, timeout=1800, cwd=str(ROOT))
    return (r.stdout + ("\n[stderr] " + r.stderr if r.stderr.strip() else ""),
            time.time() - t0)


brief = BRIEF.read_text()
pre = {"directions": DIRECTIONS, "review": REVIEW}[MODE]
prompt = pre + brief + "\n--- ENDS ---\n"
print(f"{MODE}: {BRIEF.name} {len(brief)} chars, prompt {len(prompt)} chars, "
      f"-> data/{OUT.name}/, models={MODELS}", flush=True)

index = {}
for m in MODELS:
    print(f"\n=== {m} ===", flush=True)
    try:
        text, dt = ask(m, prompt)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after 1800s", flush=True)
        index[m] = {"ok": False, "error": "timeout"}
        continue
    p = OUT / f"{m}.md"
    p.write_text(text)
    top = [ln for ln in text.splitlines() if ln.strip().startswith("TOP-PICK")]
    ok = len(text) > 1500
    index[m] = {"ok": ok, "chars": len(text), "seconds": round(dt, 1),
                "top_pick": top[-1].strip() if top else None,
                "path": str(p.relative_to(ROOT))}
    print(f"  {len(text)} chars in {dt:.0f}s -> {p.name}"
          f"{'' if ok else '   *** SHORT — likely throttled, not a real answer'}",
          flush=True)
    if top:
        print(f"  {top[-1].strip()}", flush=True)

(OUT / "index.json").write_text(json.dumps(index, indent=1))
print(f"\n[done] {sum(1 for v in index.values() if v.get('ok'))}"
      f"/{len(MODELS)} usable -> data/directions/", flush=True)
