#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$PROJECT_DIR/.desktop_window.log"
VENV_PY="$PROJECT_DIR/.venv/bin/python"

cd "$PROJECT_DIR"

{
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') ===="
  echo "Avvio finestra desktop"
} >>"$LOG_FILE"

MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib" \
XDG_CACHE_HOME="$PROJECT_DIR/.cache" \
"$VENV_PY" "$PROJECT_DIR/desktop_window.py" >>"$LOG_FILE" 2>&1
