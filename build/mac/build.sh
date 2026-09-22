#!/usr/bin/env bash
# Build ULTRON.app on macOS with PyInstaller, then wrap it into a .dmg.
# Run from the repo root:  bash build/mac/build.sh
set -euo pipefail

pip install -r requirements.txt

# macOS's system bash is 3.2, which throws "unbound variable" when expanding
# "${ARR[@]}" on an *empty* array under `set -u` (fixed only in bash 4.4+).
# The ${ARR[@]+"${ARR[@]}"} idiom below expands to nothing if ICON_ARGS is
# empty/unset, and to the array elements otherwise — safe on bash 3.2+.
ICON_ARGS=()
if [ -f "build/mac/icon.icns" ]; then
  ICON_ARGS=(--icon build/mac/icon.icns)
fi

# Use an absolute source path for --add-data: PyInstaller resolves relative
# source paths against --specpath (build/mac here), not the repo root, so a
# relative path silently breaks once --specpath differs from cwd.
REPO_ROOT="$(pwd)"

pyinstaller \
  --name ULTRON \
  --windowed \
  ${ICON_ARGS[@]+"${ICON_ARGS[@]}"} \
  --add-data "${REPO_ROOT}/app/gui/assets:app/gui/assets" \
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
