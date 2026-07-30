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
MODELS=(gpt-5.6-sol gemini-3.1-pro-preview claude-fable-5 grok-4.5)

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
