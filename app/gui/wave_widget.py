"""
wave_widget.py
--------------
The "alive" part of the GUI: a bar-style waveform (like Siri / a music
equalizer) that animates continuously at ~60fps and changes shape, speed and
color depending on what the assistant is doing.

How it works (for the Python-curious):
- A QTimer fires every ~16ms (60 times a second) and calls `_tick`.
- `_tick` advances a time counter and asks `update()` to repaint.
- `paintEvent` draws N vertical bars. Each bar's height is the sum of a
  couple of sine waves with different frequencies/phases, so the bars
  don't all move in lockstep -> it reads as an organic wave, not a
  robotic pulse.
- `level` (0..1) is a smoothly animated "how big should the wave be"
  value. It's driven by QPropertyAnimation so state changes (idle ->
  listening -> speaking) ease in/out instead of snapping.
- `set_amplitude(0..1)` lets real audio data (mic input level, or TTS
  output level) drive the wave once STT/TTS are wired up. Until then,
  each state has a synthetic amplitude pattern so it still looks alive
  standalone.
"""

import math
import random

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen
from PyQt6.QtWidgets import QWidget

from .theme import STATE_COLORS

BAR_COUNT = 48


class WaveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        self._mode = "light"
        self._state = "idle"
        self._color = QColor(STATE_COLORS["idle"])
        self._t = 0.0
        self._level = 0.18          # current animated amplitude (0..1)
        self._target_amplitude = 0.18
        self._external_amp = None    # set via set_amplitude() for real audio

        # per-bar random phase so bars don't move identically
        self._phases = [random.uniform(0, math.tau) for _ in range(BAR_COUNT)]
        self._speeds = [random.uniform(0.8, 1.3) for _ in range(BAR_COUNT)]

        self._level_anim = QPropertyAnimation(self, b"level")
        self._level_anim.setDuration(450)
        self._level_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._color_from = QColor(self._color)
        self._color_to = QColor(self._color)
        self._color_progress = 1.0
        self._color_anim = QPropertyAnimation(self, b"colorProgress")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60fps

    # -- animated "level" property (0..1 wave amplitude) -----------------
    def getLevel(self):
        return self._level

    def setLevel(self, v):
        self._level = v
        self.update()

    level = pyqtProperty(float, getLevel, setLevel)

    # -- animated color transition ---------------------------------------
    def getColorProgress(self):
        return self._color_progress

    def setColorProgress(self, v):
        self._color_progress = v
        self.update()

    colorProgress = pyqtProperty(float, getColorProgress, setColorProgress)

    def _current_color(self):
        t = self._color_progress
        r = self._color_from.red() + (self._color_to.red() - self._color_from.red()) * t
        g = self._color_from.green() + (self._color_to.green() - self._color_from.green()) * t
        b = self._color_from.blue() + (self._color_to.blue() - self._color_from.blue()) * t
        return QColor(int(r), int(g), int(b))

    # -- public API --------------------------------------------------------
    def set_theme(self, mode: str):
        self._mode = mode
        self.update()

    def set_state(self, state: str):
        """Switch visual mode: idle / listening / thinking / speaking / error."""
        if state == self._state:
            return
        self._state = state

        # animate amplitude toward the new state's resting level
        target = {
            "idle": 0.16,
            "listening": 0.55,
            "thinking": 0.30,
            "speaking": 0.85,
            "error": 0.25,
        }.get(state, 0.2)
        self._target_amplitude = target
        self._level_anim.stop()
        self._level_anim.setStartValue(self._level)
        self._level_anim.setEndValue(target)
        self._level_anim.start()

        # animate color crossfade to the new state's color
        new_color = QColor(STATE_COLORS.get(state, STATE_COLORS["idle"]))
        self._color_from = self._current_color()
        self._color_to = new_color
        self._color_progress = 0.0
        self._color_anim.stop()
        self._color_anim.setDuration(400)
        self._color_anim.setStartValue(0.0)
        self._color_anim.setEndValue(1.0)
        self._color_anim.start()

    def set_amplitude(self, value: float):
        """Feed a real 0..1 audio level in (mic input or TTS output RMS).

        Call this from your STT/TTS pipeline once it's wired up; while it's
        None the widget falls back to a synthetic "breathing" pattern per
        state so the GUI still looks alive during development.
        """
        self._external_amp = max(0.0, min(1.0, value)) if value is not None else None

    # -- animation loop ------------------------------------------------------
    def _tick(self):
        self._t += 0.016
        self.update()

    def _synthetic_amplitude(self):
        """A believable amplitude curve per state, used when no real audio
        level has been supplied yet."""
        base = self._level
        if self._state == "listening":
            # jittery, like a mic picking up speech
            return base * (0.7 + 0.3 * random.random())
        if self._state == "speaking":
            # smoother, syllable-like undulation
            return base * (0.75 + 0.25 * math.sin(self._t * 6.0))
        if self._state == "thinking":
            return base * (0.6 + 0.4 * (0.5 + 0.5 * math.sin(self._t * 3.0)))
        # idle: slow gentle breathing
        return base * (0.6 + 0.4 * (0.5 + 0.5 * math.sin(self._t * 1.2)))

    # -- painting -------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mid_y = h / 2

        amp = self._external_amp if self._external_amp is not None else self._synthetic_amplitude()
        amp = max(0.03, amp)  # never fully flat - it should always feel alive

        color = self._current_color()
        bar_width = w / (BAR_COUNT * 1.6)
        gap = bar_width * 0.6
        total_w = BAR_COUNT * (bar_width + gap) - gap
        start_x = (w - total_w) / 2

        gradient = QLinearGradient(0, 0, 0, h)
        top = QColor(color)
        top.setAlpha(255)
        bottom = QColor(color)
        bottom.setAlpha(95 if self._mode == "light" else 60)
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)

        max_bar_h = h * 0.42
        for i in range(BAR_COUNT):
            phase = self._phases[i]
            speed = self._speeds[i]
            # two overlapping sine waves = less mechanical, more organic
            wave = (
                math.sin(self._t * 3.4 * speed + phase) * 0.6
                + math.sin(self._t * 1.7 * speed + phase * 1.7) * 0.4
            )
            bar_h = max(3, (0.25 + 0.75 * abs(wave)) * max_bar_h * amp)

            x = start_x + i * (bar_width + gap)
            y = mid_y - bar_h
            painter.drawRoundedRect(
                int(x), int(y), max(2, int(bar_width)), int(bar_h * 2),
                bar_width / 2, bar_width / 2,
            )

        painter.end()
