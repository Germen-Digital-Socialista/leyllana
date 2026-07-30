#!/bin/bash
# Quick CPU-only, 8GB-capped WSL2 benchmark. Not part of the app or tools/ suite
# proper -- ad hoc, to get real numbers for the no-GPU/8GB target before ADR 0024.
set -euo pipefail

BIN=/root/llama.cpp/build/bin/llama-server
MODEL="$1"       # path to .gguf, e.g. /mnt/c/Projects/leyllana/backend/models/Qwen3-1.7B-Q4_K_M.gguf
CTX="$2"         # e.g. 4096
CHARS="$3"       # characters of the doc to send as prompt
DOC=/mnt/c/Projects/leyllana/mediciones/ley21663.txt
PORT=8990
LOG="/tmp/bench-ctx${CTX}-$(basename "$MODEL").log"

echo "=== model=$(basename "$MODEL") ctx=$CTX chars=$CHARS ==="
echo "devices:"
"$BIN" --list-devices || true
echo "mem before:"; free -h | grep Mem

"$BIN" -m "$MODEL" --host 127.0.0.1 --port $PORT -c "$CTX" -ngl 0 --jinja \
  > "$LOG" 2>&1 &
PID=$!

# wait for health
for i in $(seq 1 120); do
  if curl -s "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"'; then
    break
  fi
  if ! kill -0 $PID 2>/dev/null; then
    echo "server died at startup"; tail -30 "$LOG"; exit 1
  fi
  sleep 1
done

echo "startup done, pid=$PID"
echo "RSS at idle (KB):"; grep VmRSS /proc/$PID/status
echo "mem after model load:"; free -h | grep Mem

head -c "$CHARS" "$DOC" > /tmp/prompt_chunk.txt
python3 -c "
import json
texto = open('/tmp/prompt_chunk.txt', encoding='utf-8').read()
payload = {
    'messages': [{'role': 'user', 'content': 'Resume en una frase:\n\n' + texto}],
    'max_tokens': 256,
    'temperature': 0.3,
}
open('/tmp/payload.json', 'w', encoding='utf-8').write(json.dumps(payload))
"

T0=$(date +%s.%N)
RESP=$(curl -s -m 3600 "http://127.0.0.1:$PORT/v1/chat/completions" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/payload.json)
T1=$(date +%s.%N)

echo "RSS after call (KB):"; grep VmRSS /proc/$PID/status 2>/dev/null || echo "process gone"
echo "mem after call:"; free -h | grep Mem
echo "wall time: $(echo "$T1 - $T0" | bc)s"
echo "$RESP" | python3 -c "
import json,sys
d = json.load(sys.stdin)
t = d.get('timings', {})
print('timings:', json.dumps(t, indent=2))
print('usage:', d.get('usage'))
" || echo "$RESP" | head -c 1000

kill $PID 2>/dev/null || true
wait $PID 2>/dev/null || true
echo "log: $LOG"
