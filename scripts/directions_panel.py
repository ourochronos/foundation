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

Usage:
  .venv/bin/python scripts/directions_panel.py            # all four
  .venv/bin/python scripts/directions_panel.py grok-4.5   # one
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEF = ROOT / "docs" / "20-directions-brief.md"
OUT = ROOT / "data" / "directions"
OUT.mkdir(parents=True, exist_ok=True)

MODELS = ["gpt-5.6-sol", "gemini-3.1-pro-preview", "grok-4.5", "claude-fable-5"]
if len(sys.argv) > 1:
    MODELS = [sys.argv[1]]

PREAMBLE = """You are one of four independent reviewers, each answering blind \
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


def ask(model: str, prompt: str) -> tuple[str, float]:
    t0 = time.time()
    r = subprocess.run(
        ["copilot", "-p", prompt, "--no-ask-user", "--model", model,
         "--no-auto-update"],
        capture_output=True, text=True, timeout=1800, cwd=str(ROOT))
    return (r.stdout + ("\n[stderr] " + r.stderr if r.stderr.strip() else ""),
            time.time() - t0)


brief = BRIEF.read_text()
prompt = PREAMBLE + brief + "\n--- BRIEF ENDS ---\n"
print(f"brief {len(brief)} chars, prompt {len(prompt)} chars", flush=True)

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
