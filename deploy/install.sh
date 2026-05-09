#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8787}"
HOST="${HOST:-0.0.0.0}"
VENV="$ROOT/.venv"
DATA_DIR="${HEALTH_DATA_DIR:-$ROOT/data}"
STORE="${HEALTH_STORE:-$DATA_DIR/events.jsonl}"

cd "$ROOT"
mkdir -p "$DATA_DIR"

"$PYTHON_BIN" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$ROOT/server/requirements.txt"

cat > "$ROOT/.env.example" <<EOF
HEALTH_STORE=$STORE
HEALTH_ASSESSMENT_URL=http://127.0.0.1:$PORT
HOST=$HOST
PORT=$PORT
EOF

echo "Installed health-assessment server at $ROOT"
echo
echo "Start API server:"
echo "  HEALTH_STORE=\"$STORE\" \"$VENV/bin/uvicorn\" server.app:app --host $HOST --port $PORT"
echo
echo "Health check:"
echo "  curl -sS http://127.0.0.1:$PORT/healthz"
echo
echo "Register the MCP adapter in OpenClaw:"
if command -v openclaw >/dev/null 2>&1; then
  MCP_JSON="$(python - "$ROOT" "$VENV/bin/python" "$PORT" <<'PY'
import json
import sys

root, python_bin, port = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({
    "command": python_bin,
    "args": ["server/openclaw_mcp_server.py"],
    "cwd": root,
    "env": {"HEALTH_ASSESSMENT_URL": f"http://127.0.0.1:{port}"}
}, ensure_ascii=False))
PY
)"
  openclaw mcp set health-assessment "$MCP_JSON"
  echo "  openclaw mcp show health-assessment --json"
else
  echo "  openclaw mcp set health-assessment '{\"command\":\"$VENV/bin/python\",\"args\":[\"server/openclaw_mcp_server.py\"],\"cwd\":\"$ROOT\",\"env\":{\"HEALTH_ASSESSMENT_URL\":\"http://127.0.0.1:$PORT\"}}'"
fi
