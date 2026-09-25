#!/usr/bin/env bash
# Build ULTRON as a standalone binary, then wrap it into a .rpm with fpm.
# Run from the repo root:  bash build/linux/build.sh
set -euo pipefail

pip install -r requirements.txt

# Use an absolute source path for --add-data: PyInstaller resolves relative
# source paths against --specpath (build/linux here), not the repo root, so
# a relative path silently breaks once --specpath differs from cwd — which
# is exactly what was causing "Unable to find .../build/linux/app/gui/assets".
REPO_ROOT="$(pwd)"

pyinstaller \
  --name ULTRON \
  --onefile \
  --add-data "${REPO_ROOT}/app/gui/assets:app/gui/assets" \
  --hidden-import faster_whisper \
  --hidden-import qtawesome \
  --collect-data qtawesome \
  --distpath build/linux/dist \
  --workpath build/linux/work \
  --specpath build/linux \
  app/main.py

# Wrap the PyInstaller binary into a proper Fedora .rpm, including a
# desktop menu entry + icon so it shows up in the app launcher like any
# other installed app (not just a bare binary on PATH).
if command -v fpm >/dev/null 2>&1; then
  fpm -s dir -t rpm \
    -n ultron \
    -v "${ULTRON_VERSION:-0.1.0}" \
    --description "Voice-controlled PC automation assistant" \
    --license MIT \
    --prefix /usr/local/bin \
    -p build/linux/ultron.rpm \
    build/linux/dist/ULTRON=ultron \
    build/linux/ultron.desktop=/usr/share/applications/ultron.desktop \
    "${REPO_ROOT}/app/gui/assets/icon_256.png"=/usr/share/icons/hicolor/256x256/apps/ultron.png
  echo "Done: build/linux/ultron.rpm"
else
  echo "fpm not found — skipping .rpm packaging. Binary is at build/linux/dist/ULTRON"
  echo "To still get an app-menu icon without building an rpm, run:"
  echo "  bash build/linux/install_local.sh"
fi
