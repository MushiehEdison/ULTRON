"""
hud_panel.py
------------
A QWidget that paints itself like a sci-fi HUD panel: rounded card
background, faint dot-grid, four corner "targeting brackets", and an
optional slow scanline that sweeps top-to-bottom. Used as the container for
the reactor/wave stage so the whole thing feels like a heads-up display
rather than a plain settings dialog.

Child widgets (the reactor, wave, labels, buttons) are added on top via a
normal QVBoxLayout, same as any QWidget - this class only customizes the
background paint.
"""

from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath
from PyQt6.QtWidgets import QWidget

from .theme import palette, BRAND_ACCENT


class HudPanel(QWidget):
    def __init__(self, parent=None, scanline: bool = True):
        super().__init__(parent)
        self.setObjectName("HudPanel")
        self._mode = "light"
        self._scanline_enabled = scanline
        self._scan_y = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_theme(self, mode: str):
        self._mode = mode
        self.update()

    def _tick(self):
        if self._scanline_enabled:
            self._scan_y = (self._scan_y + 0.6) % (self.height() + 60 if self.height() else 400)
            self.update()

    def paintEvent(self, event):
        p = palette(self._mode)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = 16

        # base card
        painter.setPen(QPen(QColor(p["border"]), 1))
        painter.setBrush(QColor(p["panel"]))
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)

        # clip everything below to the rounded card so the grid/scanline
        # never draw sharp corners over the rounded edges
        card_path = QPainterPath()
        card_path.addRoundedRect(QRectF(rect.adjusted(0, 0, -1, -1)), radius, radius)
        painter.save()
        painter.setClipPath(card_path)

        # faint dot grid
        dot_color = QColor(p["grid"])
        step = 26
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        y = 14
        while y < rect.height() - 6:
            x = 14
            while x < rect.width() - 6:
                painter.drawEllipse(x, y, 1, 1)
                x += step
            y += step

        # slow scanline sweep (very subtle - fades in and back out, never opaque)
        if self._scanline_enabled and rect.height() > 0:
            grad = QLinearGradient(0, self._scan_y - 40, 0, self._scan_y + 40)
            transparent = QColor(BRAND_ACCENT)
            transparent.setAlpha(0)
            mid = QColor(BRAND_ACCENT)
            mid.setAlpha(20)
            grad.setColorAt(0.0, transparent)
            grad.setColorAt(0.5, mid)
            grad.setColorAt(1.0, transparent)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRect(0, int(self._scan_y - 40), rect.width(), 80)

        painter.restore()

        # corner HUD brackets
        accent = QColor(BRAND_ACCENT)
        pen = QPen(accent)
        pen.setWidthF(2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        L = 18
        m = 10
        w, h = rect.width(), rect.height()
        # top-left
        painter.drawLine(m, m + L, m, m)
        painter.drawLine(m, m, m + L, m)
        # top-right
        painter.drawLine(w - m - L, m, w - m, m)
        painter.drawLine(w - m, m, w - m, m + L)
        # bottom-left
        painter.drawLine(m, h - m - L, m, h - m)
        painter.drawLine(m, h - m, m + L, h - m)
        # bottom-right
        painter.drawLine(w - m - L, h - m, w - m, h - m)
        painter.drawLine(w - m, h - m, w - m, h - m - L)

        painter.end()
