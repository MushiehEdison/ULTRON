"""
generate_icon.py
-----------------
Generates the ULTRON app icon (a static version of the in-app reactor
widget) as a set of PNGs, then packages those into a Windows .ico and,
where possible, a macOS .iconset / .icns.

Run this once whenever you want to change the icon design:

    python -m app.gui.assets.generate_icon

Output (all committed to the repo, so this script is optional to re-run):
    app/gui/assets/icon.png            <- 1024x1024 master, transparent bg
    app/gui/assets/icon_<size>.png      <- 16/32/48/64/128/256/512 PNGs
    app/gui/assets/icon.ico              <- multi-size Windows icon
                                             (also copy to build/windows/icon.ico)
    app/gui/assets/icon.iconset/*.png     <- macOS iconset
    app/gui/assets/icon.icns               <- macOS icon, only if Pillow can write
                                               it on this machine; otherwise build
                                               it on a Mac with:
                                               iconutil -c icns app/gui/assets/icon.iconset
                                               (also copy the result to build/mac/icon.icns)
"""

import math
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QLinearGradient, QPen, QPixmap, QPainterPath
from PyQt6.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))

ACCENT = "#2f7dff"
ACCENT_2 = "#8a5bff"
BG_DARK_1 = "#0a0d16"
BG_DARK_2 = "#141b2e"

SIZES = [16, 24, 32, 48, 64, 128, 256, 512, 1024]


def paint_icon(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx = cy = size / 2

    # rounded-square "tile" background, like a modern app icon
    tile_path = QPainterPath()
    radius = size * 0.22
    tile_path.addRoundedRect(0, 0, size, size, radius, radius)
    bg_grad = QLinearGradient(0, 0, size, size)
    bg_grad.setColorAt(0.0, QColor(BG_DARK_2))
    bg_grad.setColorAt(1.0, QColor(BG_DARK_1))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(bg_grad)
    painter.drawPath(tile_path)
    painter.setClipPath(tile_path)

    base_r = size * 0.15

    # soft outer glow
    glow_r = size * 0.42
    glow = QRadialGradient(cx, cy, glow_r)
    glow_c = QColor(ACCENT)
    glow_c.setAlpha(140)
    glow_edge = QColor(ACCENT)
    glow_edge.setAlpha(0)
    glow.setColorAt(0.0, glow_c)
    glow.setColorAt(1.0, glow_edge)
    painter.setBrush(glow)
    painter.drawEllipse(int(cx - glow_r), int(cy - glow_r), int(glow_r * 2), int(glow_r * 2))

    # outer tick ring (static, 12 ticks)
    pen = QPen(QColor(ACCENT))
    pen.setWidthF(max(1.2, size * 0.012))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    ring_r = size * 0.34
    tick_len = size * 0.045
    for i in range(12):
        a = math.radians(i * 30)
        x1 = cx + ring_r * math.cos(a)
        y1 = cy + ring_r * math.sin(a)
        x2 = cx + (ring_r - tick_len) * math.cos(a)
        y2 = cy + (ring_r - tick_len) * math.sin(a)
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    # chrome housing ring
    housing_r = base_r * 1.45
    housing_pen = QPen(QColor("#3a4360"))
    housing_pen.setWidthF(max(1.5, size * 0.014))
    painter.setPen(housing_pen)
    painter.setBrush(QColor(BG_DARK_2))
    painter.drawEllipse(int(cx - housing_r), int(cy - housing_r), int(housing_r * 2), int(housing_r * 2))

    # bright core
    core = QRadialGradient(cx, cy, base_r)
    core.setColorAt(0.0, QColor(255, 255, 255, 240))
    core.setColorAt(0.5, QColor(ACCENT_2))
    core.setColorAt(1.0, QColor(ACCENT))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(core)
    painter.drawEllipse(int(cx - base_r), int(cy - base_r), int(base_r * 2), int(base_r * 2))

    # facet lines through the core (matches in-app reactor)
    facet_pen = QPen(QColor(255, 255, 255, 200))
    facet_pen.setWidthF(max(1.0, size * 0.009))
    painter.setPen(facet_pen)
    for i in range(6):
        a = math.radians(i * 60 + 15)
        x1 = cx + base_r * 0.12 * math.cos(a)
        y1 = cy + base_r * 0.12 * math.sin(a)
        x2 = cx + base_r * 0.85 * math.cos(a)
        y2 = cy + base_r * 0.85 * math.sin(a)
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    painter.end()
    return pm


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    out_dir = HERE
    master = paint_icon(1024)
    master.save(os.path.join(out_dir, "icon.png"), "PNG")

    for size in SIZES:
        pm = paint_icon(size)
        pm.save(os.path.join(out_dir, f"icon_{size}.png"), "PNG")
    print(f"Wrote {len(SIZES) + 1} PNGs to {out_dir}")

    # --- Windows .ico (multi-size, single file) ---------------------------
    try:
        from PIL import Image

        ico_sizes = [16, 24, 32, 48, 64, 128, 256]
        base = Image.open(os.path.join(out_dir, "icon_256.png"))
        base.save(
            os.path.join(out_dir, "icon.ico"),
            sizes=[(s, s) for s in ico_sizes],
        )
        print("Wrote icon.ico")
    except Exception as exc:
        print(f"Skipped icon.ico ({exc}) - install Pillow: pip install pillow")

    # --- macOS .iconset (+ .icns if this machine can write one) ----------
    iconset_dir = os.path.join(out_dir, "icon.iconset")
    os.makedirs(iconset_dir, exist_ok=True)
    # Apple's required filenames for `iconutil -c icns`
    mac_map = {
        "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
    }
    for filename, size in mac_map.items():
        pm = paint_icon(size)
        pm.save(os.path.join(iconset_dir, filename), "PNG")
    print(f"Wrote macOS iconset to {iconset_dir}")

    try:
        from PIL import Image
        Image.open(os.path.join(out_dir, "icon.png")).save(
            os.path.join(out_dir, "icon.icns")
        )
        print("Wrote icon.icns")
    except Exception as exc:
        print(
            f"Skipped icon.icns ({exc}) - on a Mac, run:\n"
            f"  iconutil -c icns {iconset_dir} -o {os.path.join(out_dir, 'icon.icns')}"
        )


if __name__ == "__main__":
    main()
