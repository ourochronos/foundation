#!/usr/bin/env bash
# Gemma 4 12B (Q6_K) on the RX 9070 via the PrismML llama.cpp fork.
#
# Replaces Bonsai-27B for extraction work. Bonsai is a 1-BIT quant, and
# attributed-claim extraction is exactly the task where that loses: telling
# "compatibilists hold X" from "critics of compatibilism hold X" is nuance, and
# nuance is the first thing a Q1 quant drops. A 12B at Q6_K is near-lossless
# and fits 16GB with ~6GB left for context; the 26B-A4B alternative only comes
# at Q4_K_S/16.5GB, which would reintroduce the very problem being avoided.
#
#   ./gemma.sh -p "..."     one-shot prompt
#   ./gemma.sh serve        OpenAI-compatible API on :8080
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$DIR/llama.cpp/build/bin"
MODEL="$DIR/models/gemma-4-12b-it-Q6_K.gguf"
ARGS=(-m "$MODEL" -ngl 99 --temp 0.1 --top-p 0.95 -c 8192)
if [[ "${1:-}" == "serve" ]]; then
  exec "$BIN/llama-server" "${ARGS[@]}" --host 127.0.0.1 --port 8080
fi
# -st / -no-cnv: single-turn, no conversation wrapper — required in scripts
exec "$BIN/llama-cli" "${ARGS[@]}" -st -no-cnv --no-display-prompt "$@"
