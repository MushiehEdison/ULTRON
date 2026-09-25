#!/usr/bin/env bash
# Fallback for systems without `fpm`/`rpmbuild` (i.e. not building an .rpm):
# installs the already-built binary's icon + app-menu entry for the current
# user only, no root/package manager needed.
#
# Run AFTER build/linux/build.sh has produced build/linux/dist/ULTRON:
#   bash build/linux/build.sh
#   bash build/linux/install_local.sh
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
BIN="$REPO_ROOT/build/linux/dist/ULTRON"

if [ ! -f "$BIN" ]; then
    echo "Couldn't find $BIN - run 'bash build/linux/build.sh' first."
    exit 1
fi

mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/share/icons/hicolor/256x256/apps
cp "$BIN" ~/.local/bin/ultron
chmod +x ~/.local/bin/ultron
cp "$REPO_ROOT/app/gui/assets/icon_256.png" ~/.local/share/icons/hicolor/256x256/apps/ultron.png

sed "s#Exec=/usr/local/bin/ultron#Exec=$HOME/.local/bin/ultron#; s#Icon=ultron#Icon=$HOME/.local/share/icons/hicolor/256x256/apps/ultron.png#" \
    "$HERE/ultron.desktop" > ~/.local/share/applications/ultron.desktop
chmod +x ~/.local/share/applications/ultron.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true

echo "Installed. ULTRON should now appear in your application launcher."

if [ -d ~/Desktop ]; then
    cp ~/.local/share/applications/ultron.desktop ~/Desktop/ultron.desktop
    chmod +x ~/Desktop/ultron.desktop
    echo "Also added a launcher to ~/Desktop (right-click it and choose"
    echo "'Allow Launching' the first time - standard Linux security prompt)."
fi
