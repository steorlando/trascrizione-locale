#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="$PROJECT_DIR/.venv/bin/python"
VENV_PYINSTALLER="$PROJECT_DIR/.venv/bin/pyinstaller"
SPEC_FILE="$PROJECT_DIR/Trascrizione Locale.spec"
DIST_DIR="$PROJECT_DIR/dist"
APP_NAME="Trascrizione Locale.app"
APP_PATH="$DIST_DIR/$APP_NAME"
ARCH_SUFFIX="$(uname -m)"
ZIP_PATH="$DIST_DIR/Trascrizione-Locale-macOS-$ARCH_SUFFIX.zip"

cd "$PROJECT_DIR"

rm -rf "$PROJECT_DIR/build" "$DIST_DIR"

"$VENV_PY" "$PROJECT_DIR/scripts/generate_app_icon.py"
"$VENV_PYINSTALLER" --noconfirm --clean "$SPEC_FILE"

if [ ! -d "$APP_PATH" ]; then
  echo "Build fallita: app bundle non trovato in $APP_PATH" >&2
  exit 1
fi

/usr/bin/xattr -cr "$APP_PATH"
if ! /usr/bin/codesign --force --deep --sign - "$APP_PATH"; then
  echo "Avviso: firma ad-hoc non riuscita. L'app resta utilizzabile in locale," >&2
  echo "ma su altri Mac potrebbe essere necessario usare tasto destro > Apri." >&2
fi

/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

echo "App standalone creata:"
echo "  $APP_PATH"
echo "Archivio pronto per altri Mac:"
echo "  $ZIP_PATH"
