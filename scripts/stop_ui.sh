#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_DIR/.ui_server.pid"
LSOF_BIN="/usr/sbin/lsof"

find_running_ui_pid() {
  "$LSOF_BIN" -ti tcp:8000 | head -n 1 || true
}

pid=""

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
fi

if [ -z "${pid:-}" ]; then
  pid="$(find_running_ui_pid)"
fi

if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  rm -f "$PID_FILE"
  echo "Server fermato."
  exit 0
fi

rm -f "$PID_FILE"
echo "Il server non era attivo."
