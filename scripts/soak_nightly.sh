#!/usr/bin/env bash
# M7 nightly soak (G5, D76): grow the raw corpus a little, run the frozen
# KB battery, append one JSONL row. Durable system-cron entry:
#   41 2 * * * /home/zonk1024/projects/foundation/scripts/soak_nightly.sh
# (WSL2 caveat: fires only while the WSL VM is up.)
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

CUR=$(ls data/wiki/pages/*.json 2>/dev/null | wc -l)
WIKI_TARGET=$((CUR + 10)) $PY scripts/m3_fetch_wiki.py \
    >> results/soak_fetch.out 2>&1 || true

$PY scripts/soak_battery.py >> results/soak_log.jsonl \
    2>> results/soak_cron.err
tail -1 results/soak_log.jsonl
