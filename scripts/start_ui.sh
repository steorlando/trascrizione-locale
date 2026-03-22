#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="$PROJECT_DIR/.venv/bin/python"
UI_SCRIPT="$PROJECT_DIR/ui_app.py"
PID_FILE="$PROJECT_DIR/.ui_server.pid"
LOG_FILE="$PROJECT_DIR/.ui_server.log"
LAUNCH_LOG="$PROJECT_DIR/.ui_launcher.log"
URL="http://127.0.0.1:8000"
CURL_BIN="/usr/bin/curl"
OPEN_BIN="/usr/bin/open"
LSOF_BIN="/usr/sbin/lsof"
SLEEP_BIN="/bin/sleep"
OSASCRIPT_BIN="/usr/bin/osascript"

{
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') ===="
  echo "Launcher avviato"
} >>"$LAUNCH_LOG"

cd "$PROJECT_DIR"

if [ ! -x "$VENV_PY" ]; then
  echo "Virtualenv non trovato. Verifica che esista $VENV_PY"
  exit 1
fi

find_running_ui_pid() {
  "$LSOF_BIN" -ti tcp:8000 | head -n 1 || true
}

existing_pid="$(find_running_ui_pid)"
if [ -n "${existing_pid:-}" ]; then
  kill "$existing_pid" >/dev/null 2>&1 || true
  echo "Server precedente fermato: $existing_pid" >>"$LAUNCH_LOG"
  "$SLEEP_BIN" 1
fi

rm -f "$PID_FILE"

MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib" \
XDG_CACHE_HOME="$PROJECT_DIR/.cache" \
nohup "$VENV_PY" "$UI_SCRIPT" >"$LOG_FILE" 2>&1 &

server_pid=$!
echo "$server_pid" >"$PID_FILE"
echo "Nuovo server avviato con PID $server_pid" >>"$LAUNCH_LOG"

for _ in {1..40}; do
  if "$CURL_BIN" -s "$URL" >/dev/null 2>&1; then
    echo "Server raggiungibile, apro il browser su $URL" >>"$LAUNCH_LOG"
    "$OPEN_BIN" "$URL" >/dev/null 2>&1 || \
    "$OSASCRIPT_BIN" -e "open location \"$URL\"" >/dev/null 2>&1 || true
    exit 0
  fi
  "$SLEEP_BIN" 0.5
done

echo "Timeout: server non raggiungibile" >>"$LAUNCH_LOG"
"$OSASCRIPT_BIN" -e 'display dialog "Il server non ha risposto in tempo. Controlla il file .ui_server.log nella cartella del progetto." buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
exit 1
