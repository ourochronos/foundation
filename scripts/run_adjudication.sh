#!/usr/bin/env bash
# Re-adjudicate the current claim block under both prompts (D152).
#
# Verdict artifacts key on index, so every stored verdict was invalidated when
# the claims list changed length. This re-runs the whole table on the settled
# block: `claims` (verification) once per rater, `attack` (adversarial) three
# times per rater, because D150 measured one rater varying by 5 of 11 across
# identical runs — single-run adversarial is not a usable instrument.
#
# Raters run sequentially: concurrent `copilot -p` calls contend for the same
# rate limit and a throttled call returns prose instead of JSON, which parses
# as zero verdicts and looks like a silent rater rather than a failed one.
set -u
cd "$(dirname "$0")/.."
# THREE raters, deliberately odd (D154). A fourth moved 1 verdict of 14, and
# that one only because four raters turn a 2-of-4 majority into a tie on
# exactly the claims a quorum exists to resolve. The dropped rater is the
# author's own family, which D154 also showed is lenient under the
# verification prompt (14/14 supported, the only clean sheet) while behaving
# like the others under attack — so dropping it costs nothing measurable and
# removes the parity problem. 12 calls instead of 16.
MODELS=(gpt-5.6-sol gemini-3.1-pro-preview grok-4.5)

for m in "${MODELS[@]}"; do
  echo "=== claims / $m ==="
  .venv/bin/python scripts/adjudicate.py claims "$m" 2>&1 | tail -4
done

for r in 1 2 3; do
  for m in "${MODELS[@]}"; do
    echo "=== attack r$r / $m ==="
    .venv/bin/python scripts/adjudicate.py attack "$m" "$r" 2>&1 | tail -4
  done
done
echo "ALL DONE"
