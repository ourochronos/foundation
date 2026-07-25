#!/usr/bin/env bash
# Bonsai-27B (1-bit) on the RX 9070 via PrismML llama.cpp fork.
#   ./bonsai.sh              interactive chat (text)
#   ./bonsai.sh -v           interactive chat with vision (loads mmproj)
#   ./bonsai.sh serve        OpenAI-compatible API + web UI on :8080
#   ./bonsai.sh -p "..."     one-shot prompt, prints answer and exits
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$DIR/llama.cpp/build/bin"
MODEL="$DIR/models/Bonsai-27B-Q1_0.gguf"
MMPROJ="$DIR/models/Bonsai-27B-mmproj-Q8_0.gguf"
ARGS=(-m "$MODEL" -ngl 99 --temp 0.7 --top-p 0.95 --top-k 20)

case "${1:-chat}" in
  serve) shift; exec "$BIN/llama-server" "${ARGS[@]}" --mmproj "$MMPROJ" --host 127.0.0.1 --port 8080 "$@" ;;
  -v)    shift; exec "$BIN/llama-cli" "${ARGS[@]}" --mmproj "$MMPROJ" "$@" ;;
  -p)    exec "$BIN/llama-cli" "${ARGS[@]}" -st -no-cnv "$@" ;;
  *)     exec "$BIN/llama-cli" "${ARGS[@]}" "$@" ;;
esac
