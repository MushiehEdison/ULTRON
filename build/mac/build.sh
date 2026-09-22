#!/usr/bin/env bash
# Build ULTRON.app on macOS with PyInstaller, then wrap it into a .dmg.
# Run from the repo root:  bash build/mac/build.sh
set -euo pipefail

pip install -r requirements.txt

ICON_ARGS=()
if [ -f "build/mac/icon.icns" ]; then
  ICON_ARGS=(--icon build/mac/icon.icns)
fi

pyinstaller \
  --name ULTRON \
  --windowed \
  "${ICON_ARGS[@]}" \
  --add-data "app/gui/assets:app/gui/assets" \
  --hidden-import faster_whisper \
  --hidden-import qtawesome \
  --collect-data qtawesome \
  --distpath build/mac/dist \
  --workpath build/mac/work \
  --specpath build/mac \
  app/main.py

# ULTRON.app now exists at build/mac/dist/ULTRON.app — compress into a .dmg.
hdiutil create -volname ULTRON \
  -srcfolder build/mac/dist/ULTRON.app \
  -ov -format UDZO \
  build/mac/ULTRON.dmg

echo "Done: build/mac/ULTRON.dmg"
