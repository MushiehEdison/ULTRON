"""
reactor_widget.py
------------------
The "face" of ULTRON: an arc-reactor-style core (think Tony Stark's chest
piece) with two counter-rotating HUD rings of tick marks around it, plus a
soft glow that breathes at idle and pulses faster/brighter the more active
the assistant is.

Everything is drawn in ONE paintEvent (rings + glow + core) instead of
stacking several translucent widgets - this keeps it visually consistent
across platforms and avoids compositing quirks between OS window managers.

Animation sources, all QTimer-driven at ~60fps:
- `_t`            : general clock, drives the breathing pulse
- `_ring_angle`    : outer ring rotation (clockwise)
- `_ring_angle2`   : inner ring rotation (counter-clockwise, different speed)
- `colorProgress` : QPropertyAnimation-driven crossfade between state colors
"""

import math

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen
from PyQt6.QtWidgets import QWidget

from .theme import STATE_COLORS, palette


class ReactorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(190, 190)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        self._mode = "light"
        self._state = "idle"
        self._color_from = QColor(STATE_COLORS["idle"])
        self._color_to = QColor(STATE_COLORS["idle"])
        self._color_progress = 1.0
        self._pulse_speed = 0.6
        self._t = 0.0
        self._ring_angle = 0.0
        self._ring_angle2 = 0.0
        self._ring_speed = 14.0     # deg/sec, scales with state

        self._color_anim = QPropertyAnimation(self, b"colorProgress")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # -- animated color crossfade -----------------------------------------
    def getColorProgress(self):
        return self._color_progress

    def setColorProgress(self, v):
        self._color_progress = v
        self.update()

    colorProgress = pyqtProperty(float, getColorProgress, setColorProgress)

    def _current_color(self):
        t = self._color_progress
        c1, c2 = self._color_from, self._color_to
        r = c1.red() + (c2.red() - c1.red()) * t
        g = c1.green() + (c2.green() - c1.green()) * t
        b = c1.blue() + (c2.blue() - c1.blue()) * t
        return QColor(int(r), int(g), int(b))

    # -- public API -----------------------------------------------------------
    def set_theme(self, mode: str):
        self._mode = mode
        self.update()

    def set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        self._color_from = self._current_color()
        self._color_to = QColor(STATE_COLORS.get(state, STATE_COLORS["idle"]))
        self._color_progress = 0.0
        self._color_anim.stop()
        self._color_anim.setDuration(400)
        self._color_anim.setStartValue(0.0)
        self._color_anim.setEndValue(1.0)
        self._color_anim.start()

        self._pulse_speed = {
            "idle": 0.6, "listening": 1.6, "thinking": 1.1,
            "speaking": 2.2, "error": 1.4,
        }.get(state, 0.6)
        self._ring_speed = {
            "idle": 10.0, "listening": 55.0, "thinking": 35.0,
            "speaking": 70.0, "error": 20.0,
        }.get(state, 10.0)

    # -- animation loop -----------------------------------------------------
    def _tick(self):
        self._t += 0.016
        self._ring_angle = (self._ring_angle + self._ring_speed * 0.016) % 360
        self._ring_angle2 = (self._ring_angle2 - self._ring_speed * 0.55 * 0.016) % 360
        self.update()

    # -- painting -------------------------------------------------------------
    def _draw_tick_ring(self, painter, cx, cy, radius, angle_offset, count, color, width, length):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(angle_offset)
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for i in range(count):
            a = math.radians(i * (360 / count))
            x1 = radius * math.cos(a)
            y1 = radius * math.sin(a)
            x2 = (radius - length) * math.cos(a)
            y2 = (radius - length) * math.sin(a)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base_r = min(w, h) * 0.16

        pulse = 0.5 + 0.5 * math.sin(self._t * self._pulse_speed)
        core_r = base_r * (0.9 + 0.16 * pulse)
        glow_r = base_r * (2.4 + 0.5 * pulse)
        color = self._current_color()
        p = palette(self._mode)

        # faint static guide ring (very subtle, theme-colored)
        guide_pen = QPen(QColor(p["border_strong"]))
        guide_pen.setWidthF(1.0)
        painter.setPen(guide_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        guide_r = base_r * 2.9
        painter.drawEllipse(int(cx - guide_r), int(cy - guide_r), int(guide_r * 2), int(guide_r * 2))

        # outer rotating tick ring (12 ticks, clockwise)
        outer_color = QColor(color)
        outer_color.setAlpha(190)
        self._draw_tick_ring(painter, cx, cy, base_r * 2.9, self._ring_angle, 12, outer_color, 2.4, base_r * 0.30)

        # inner rotating dashed ring (24 short ticks, counter-clockwise)
        inner_color = QColor(color)
        inner_color.setAlpha(120)
        self._draw_tick_ring(painter, cx, cy, base_r * 2.15, self._ring_angle2, 36, inner_color, 1.6, base_r * 0.12)

        # 4 orbiting "satellite" nodes on the outer ring
        painter.setPen(Qt.PenStyle.NoPen)
        node_color = QColor(color)
        node_color.setAlpha(230)
        painter.setBrush(node_color)
        for i in range(4):
            a = math.radians(self._ring_angle + i * 90)
            nx = cx + base_r * 2.9 * math.cos(a)
            ny = cy + base_r * 2.9 * math.sin(a)
            nr = base_r * 0.09
            painter.drawEllipse(int(nx - nr), int(ny - nr), int(nr * 2), int(nr * 2))

        # outer soft glow
        glow = QRadialGradient(cx, cy, glow_r)
        glow_color = QColor(color)
        glow_color.setAlpha(80)
        glow_edge = QColor(color)
        glow_edge.setAlpha(0)
        glow.setColorAt(0.0, glow_color)
        glow.setColorAt(1.0, glow_edge)
        painter.setBrush(glow)
        painter.drawEllipse(int(cx - glow_r), int(cy - glow_r), int(glow_r * 2), int(glow_r * 2))

        # reactor core: bright white-hot center fading into the state color,
        # with a thin metallic ring around it (the "chrome housing")
        housing_r = core_r * 1.35
        housing_pen = QPen(QColor(p["border_strong"]))
        housing_pen.setWidthF(3.0)
        painter.setPen(housing_pen)
        painter.setBrush(QColor(p["panel"]))
        painter.drawEllipse(int(cx - housing_r), int(cy - housing_r), int(housing_r * 2), int(housing_r * 2))

        core = QRadialGradient(cx, cy, core_r)
        core_center = QColor(255, 255, 255)
        core_center.setAlpha(240)
        core_mid = QColor(color)
        core_mid.setAlpha(255)
        core_edge = QColor(color)
        core_edge.setAlpha(60)
        core.setColorAt(0.0, core_center)
        core.setColorAt(0.5, core_mid)
        core.setColorAt(1.0, core_edge)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(core)
        painter.drawEllipse(int(cx - core_r), int(cy - core_r), int(core_r * 2), int(core_r * 2))

        # triangular "shutter" facets inside the core (Stark-reactor detail)
        facet_pen = QPen(QColor(255, 255, 255, 160))
        facet_pen.setWidthF(1.4)
        painter.setPen(facet_pen)
        for i in range(6):
            a = math.radians(i * 60 + self._ring_angle * 0.4)
            x1 = cx + core_r * 0.15 * math.cos(a)
            y1 = cy + core_r * 0.15 * math.sin(a)
            x2 = cx + core_r * 0.85 * math.cos(a)
            y2 = cy + core_r * 0.85 * math.sin(a)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        painter.end()
