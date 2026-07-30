"""Positive control for the `selfcheck` prompt (D163 revisit (c)).

D163 built a third adjudication prompt and it flagged four claims on its first
run. That is encouraging and it is not evidence the prompt works, because a
prompt asked "does this claim overreach?" has an obvious cheap strategy:
**flag whichever sentences sound least hedged.** Under that strategy it would
have produced a plausible-looking four without reading the scope at all.

So: give it both versions of the same four claims, mixed together and unlabelled.

  * the **pre-fix** sentences, which three raters flagged and which were then
    verified by hand against their own scopes — known overreaches;
  * the **post-fix** sentences, same claims, same scopes, same numbers, with
    only the overreaching phrase repaired — known consistent.

The scope condition, the evidence and the subject matter are **identical**
within each pair. The only thing that differs is the phrase the prompt is
supposed to be detecting. A prompt keying on topic, length or hedging style
scores the two halves alike; a prompt reading the claim against its scope
separates them.

This is the discipline D157 used on the fingerprint guard (tested by making it
fire) and D160 on the manipulation check (aborts if the arms did not
separate). A check whose positives have never been distinguished from its
false positives has not been tested, only used.

Usage: .venv/bin/python scripts/selfcheck_control.py [model]
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.6-sol"
PAIRED_ROWS = ["1b", "3", "7", "12"]
OUT = ROOT / "data" / "adjudication" / "selfcheck_control.json"


def _block(md: str) -> dict[str, dict]:
    m = re.search(r"## Machine-readable claims.*?```json\n(.*?)\n```", md, re.S)
    return {c["row"]: c for c in json.loads(m.group(1))}


post = _block((ROOT / "docs" / "18-writeup-outline.md").read_text())
pre = _block(subprocess.run(["git", "show", "HEAD~1:docs/18-writeup-outline.md"],
                            capture_output=True, text=True, cwd=str(ROOT),
                            check=True).stdout)

# Interleave so arm is not recoverable from position: pre, post, pre, post...
items = []
for r in PAIRED_ROWS:
    assert pre[r]["claim"] != post[r]["claim"], f"row {r} is unchanged"
    items.append({"row": r, "arm": "pre_fix", "claim": pre[r]["claim"],
                  "scope": pre[r]["scope"]})
    items.append({"row": r, "arm": "post_fix", "claim": post[r]["claim"],
                  "scope": post[r]["scope"]})

spec = importlib.util.spec_from_file_location("adj", ROOT / "scripts"
                                              / "adjudicate.py")
adj = importlib.util.module_from_spec(spec)
sys.argv = ["adjudicate.py", "__probe__"]
try:
    spec.loader.exec_module(adj)
except SystemExit:
    pass

blocks = [f"### ITEM {i}\nCLAIM SENTENCE: {it['claim']}\n"
          f"ITS OWN SCOPE CONDITION: {it['scope']}"
          for i, it in enumerate(items)]
header = (
    "For each item you are given a CLAIM SENTENCE and the SCOPE CONDITION its "
    "own authors attached to it. Ignore whether either is true — you are not "
    "being shown the evidence and should not guess at it.\n\n"
    "Answer one question: **does the claim sentence assert anything that its "
    "own scope condition contradicts, concedes, or declines to support?**\n\n"
    "Pay closest attention to words that EXCLUDE or make something absolute — "
    "'not X', 'rather than X', 'only', 'never', 'no', 'is caused by', "
    "'permanent'. An exclusion is a second claim stacked on top of the "
    "measurement, and a scope that quietly restores what the claim excluded "
    "is the specific failure being looked for.\n\n"
    "Verdict:\n"
    "  CONSISTENT - the claim sentence says no more than the scope permits.\n"
    "  OVERREACH  - the claim sentence asserts something the scope "
    "contradicts, concedes against, or does not cover.\n"
    "  UNDERREACH - the scope asserts something stronger than the claim.\n\n"
    "Do not use any tools. Output ONLY a JSON array of "
    f"{len(items)} objects, format "
    '{"idx": <n>, "verdict": "CONSISTENT"|"OVERREACH"|"UNDERREACH", '
    '"reason": "<short>"} — nothing else.\n\n')

print(f"{len(items)} items ({len(PAIRED_ROWS)} matched pairs), model={MODEL}",
      flush=True)
adj.MODEL = MODEL
got = adj.parse_verdicts(adj.copilot(header + "\n\n".join(blocks)),
                         {"CONSISTENT", "OVERREACH", "UNDERREACH"})

print(f"\n{'row':>5} {'arm':>10} {'verdict':>12}")
tally = {"pre_fix": 0, "post_fix": 0}
seen = {"pre_fix": 0, "post_fix": 0}
for i, it in enumerate(items):
    v = got.get(i, {}).get("verdict", "ABSENT")
    seen[it["arm"]] += v != "ABSENT"
    tally[it["arm"]] += v == "OVERREACH"
    print(f"{it['row']:>5} {it['arm']:>10} {v:>12}")

pre_rate = tally["pre_fix"] / max(seen["pre_fix"], 1)
post_rate = tally["post_fix"] / max(seen["post_fix"], 1)
print(f"\nOVERREACH on known-bad  (pre-fix):  {tally['pre_fix']}/"
      f"{seen['pre_fix']}  = {pre_rate:.2f}")
print(f"OVERREACH on known-good (post-fix): {tally['post_fix']}/"
      f"{seen['post_fix']}  = {post_rate:.2f}")
sep = pre_rate - post_rate
if sep >= 0.5:
    verdict = (f"DISCRIMINATES — separation {sep:+.2f}. The prompt is reading "
               f"the claim against its scope, not scoring how hedged the "
               f"sentence sounds.")
elif pre_rate >= 0.5 and post_rate >= 0.5:
    verdict = (f"FLAGS EVERYTHING — {pre_rate:.2f} vs {post_rate:.2f}. It "
               f"cannot tell a repaired claim from the one it replaced, so "
               f"D163's four flags are not evidence of a defect and the "
               f"prompt must not be trusted to find one.")
elif pre_rate < 0.5:
    verdict = (f"MISSES KNOWN DEFECTS — only {pre_rate:.2f} of the pre-fix "
               f"sentences, which three raters flagged and a human verified, "
               f"come back OVERREACH. One run is a sample, but this is the "
               f"wrong direction.")
else:
    verdict = f"WEAK — separation {sep:+.2f}; too small to rely on."
print(f"\n=== VERDICT ===\n  {verdict}")

OUT.write_text(json.dumps(
    {"model": MODEL, "n_pairs": len(PAIRED_ROWS),
     "items": [{**it, "verdict": got.get(i, {}).get("verdict", "ABSENT"),
                "reason": got.get(i, {}).get("reason", "")[:160]}
               for i, it in enumerate(items)],
     "overreach_rate_pre_fix": round(pre_rate, 4),
     "overreach_rate_post_fix": round(post_rate, 4),
     "separation": round(sep, 4), "verdict": verdict,
     "scope": ("Matched pairs: the same four claims before and after the "
               "overreaching phrase was repaired, with scope, evidence and "
               "subject identical within each pair and only the phrase "
               "differing. Interleaved so the arm is not recoverable from "
               "position. ONE run, one rater — a sample, not a verdict "
               "(D150). The pre-fix sentences are the ground truth only "
               "because three raters flagged them AND each was verified by "
               "hand against its own scope (D163); a prompt agreeing with a "
               "prompt would prove nothing.")},
    indent=1))
print(f"\n[done] {OUT.relative_to(ROOT)}")
