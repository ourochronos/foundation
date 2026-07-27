#!/usr/bin/env bash
# PoC acceptance (docs/10-poc-plan.md): five acts against a FRESH database.
# Green run + test suite green = the demo contract holds.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export FOUNDATION_TABLE=demo
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
need() { echo "$2" | grep -q "$1" || { printf '  \033[31mFAIL\033[0m %s\n' "$3"; exit 1; }; pass "$3"; }

echo "== Act 1: ingest (fresh store) =="
OUT=$($PY -m foundation ingest data/wiki/shards_final --fresh 2>/dev/null)
need '"ingested": [0-9]\{4,\}' "$OUT" "claims ingested into fresh table (4+ digits)"

echo "== Act 2: ask (provenance + honest statuses) =="
OUT=$($PY -m foundation ask "Norbert Wiener" P69 2>/dev/null)
need '"status": "answered"' "$OUT" "answered with citations"
need 'out_' "$OUT" "per-claim citation present"
OUT=$($PY -m foundation ask "Nobody Anywhere" P69 2>/dev/null)
need '"status": "abstain"' "$OUT" "unknown entity abstains"

echo "== Act 3: multi-hop chain (symbolic hand-off) =="
OUT=$($PY -m foundation chain "Norbert Wiener" P69 P571 2>/dev/null)
need '"status": "answered"' "$OUT" "2-hop answered"
need '1734' "$OUT" "hand-off reached University of Göttingen founding"

echo "== Act 4: edit + ripple =="
OUT=$($PY -m foundation edit "Norbert Wiener" P19 "Columbia, Missouri" --source "demo:edit" 2>/dev/null)
need '"status": "edited"' "$OUT" "supersession accepted"
OUT=$($PY -m foundation ask "Norbert Wiener" P19 2>/dev/null)
need 'Columbia, Missouri' "$OUT" "edit visible at ask"
need 'demo:edit' "$OUT" "edit provenance carried"

echo "== Act 5: views + grounded brief =="
OUT=$($PY -m foundation views "Alan Turing" 2>/dev/null)
need '"status": "answered"' "$OUT" "per-source views"
OUT=$($PY -m foundation brief "Andrey Kolmogorov" 2>/dev/null)
need 'out_' "$OUT" "brief sentences carry citations"

echo "== Regression: test suite =="
$PY -m pytest tests/ -q 2>&1 | grep -E "[0-9]+ passed"

echo
echo "DEMO GREEN — five acts + suite."
