#!/usr/bin/env bash
# Rebuild the poc store from SHARDS ONLY (docs/13 re-ingestion proof).
# The source layer (data/*/pages, data/*/papers*, data/hf/cards) plus the
# vetted shards are sufficient to reconstruct the store; nothing in the
# database is authoritative. Ingest order matters only for provenance
# tidiness — canonicalization is order-independent as of the page_title
# fix (a page's canonical form is its TITLE, not its identifier).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
TABLE=${FOUNDATION_TABLE:-poc}
export FOUNDATION_TABLE=$TABLE
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

DIRS=(
  data/wiki/shards_final          # G2 wiki tranche
  data/wiki/shards_1k             # 1k-page tranche
  data/arxiv/shards               # math.LO slice (D83)
  data/arxiv_ai/shards            # AI/ML slice (D92)
  data/arxiv_ai/shards_cites      # citation axis, mechanical (D92)
  data/hf/shards                  # HuggingFace parts inventory (D92)
)

first=1
for d in "${DIRS[@]}"; do
  [ -d "$d" ] || { echo "-- skip $d (absent)"; continue; }
  ls "$d"/out_*.jsonl >/dev/null 2>&1 || { echo "-- skip $d (no shards)"; continue; }
  echo "== ingest $d"
  if [ $first -eq 1 ]; then
    $PY -m foundation ingest "$d" --fresh 2>/dev/null | tail -5
    first=0
  else
    $PY -m foundation ingest "$d" 2>/dev/null | tail -5
  fi
done

echo "== status"
$PY -m foundation status 2>/dev/null
