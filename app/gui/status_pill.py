"""
status_pill.py
---------------
The small rounded label in the top-right ("LISTENING", "THINKING"...).
Its background color smoothly crossfades between states instead of
snapping, matching the wave/orb.
"""

from PyQt6.QtCore import QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel

from .theme import STATE_COLORS


class StatusPill(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self._mode = "light"
        self._color_progress = 1.0
        self._color_from = QColor(STATE_COLORS["idle"])
        self._color_to = QColor(STATE_COLORS["idle"])
        self._anim = QPropertyAnimation(self, b"colorProgress")
        self.set_state("idle")

    def set_theme(self, mode: str):
        self._mode = mode
        self._apply_style()

    def getColorProgress(self):
        return self._color_progress

    def setColorProgress(self, v):
        self._color_progress = v
        self._apply_style()

    colorProgress = pyqtProperty(float, getColorProgress, setColorProgress)

    def _current_color(self):
        t = self._color_progress
        c1, c2 = self._color_from, self._color_to
        r = c1.red() + (c2.red() - c1.red()) * t
        g = c1.green() + (c2.green() - c1.green()) * t
        b = c1.blue() + (c2.blue() - c1.blue()) * t
        return QColor(int(r), int(g), int(b))

    def _apply_style(self):
        color = self._current_color()
        bg = QColor(color)
        bg.setAlpha(28 if self._mode == "light" else 35)
        self.setStyleSheet(
            f"""
            #StatusPill {{
                background-color: rgba({bg.red()},{bg.green()},{bg.blue()},{bg.alpha()});
                color: rgb({color.red()},{color.green()},{color.blue()});
                border: 1px solid rgba({color.red()},{color.green()},{color.blue()},90);
                border-radius: 11px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: 11px;
                letter-spacing: 1px;
            }}
            """
        )

    def set_state(self, state: str):
        labels = {
            "idle": "IDLE",
            "listening": "LISTENING",
            "thinking": "THINKING",
            "speaking": "SPEAKING",
            "error": "ATTENTION",
        }
        self.setText(labels.get(state, state.upper()))

        self._color_from = self._current_color()
        self._color_to = QColor(STATE_COLORS.get(state, STATE_COLORS["idle"]))
        self._color_progress = 0.0
        self._anim.stop()
        self._anim.setDuration(400)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
