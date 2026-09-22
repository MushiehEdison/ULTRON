#!/usr/bin/env bash
# Build ULTRON as a standalone binary, then wrap it into a .rpm with fpm.
# Run from the repo root:  bash build/linux/build.sh
set -euo pipefail

pip install -r requirements.txt

pyinstaller \
  --name ULTRON \
  --onefile \
  --add-data "app/gui/assets:app/gui/assets" \
  --hidden-import faster_whisper \
  --hidden-import qtawesome \
  --collect-data qtawesome \
  --distpath build/linux/dist \
  --workpath build/linux/work \
  --specpath build/linux \
  app/main.py

# Wrap the PyInstaller binary into a proper Fedora .rpm.
# Requires `fpm` (gem install fpm) and `rpmbuild` on PATH.
if command -v fpm >/dev/null 2>&1; then
  fpm -s dir -t rpm \
    -n ultron \
    -v "${ULTRON_VERSION:-0.1.0}" \
    --description "Voice-controlled PC automation assistant" \
    --license MIT \
    --prefix /usr/local/bin \
    -p build/linux/ultron.rpm \
    build/linux/dist/ULTRON=ultron
  echo "Done: build/linux/ultron.rpm"
else
  echo "fpm not found — skipping .rpm packaging. Binary is at build/linux/dist/ULTRON"
fi
