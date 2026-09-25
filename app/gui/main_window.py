"""
main_window.py
---------------
Assembles the ULTRON window from the pieces in this folder:

    ReactorWidget - reactor_widget.py  - the Stark-reactor-style "face"
    WaveWidget    - wave_widget.py     - the animated waveform beneath it
    StatusPill    - status_pill.py     - colored state label (top-right)
    HudPanel      - hud_panel.py       - sci-fi card background w/ HUD corners
    ConfirmDialog - confirm_dialog.py  - themed Yes/No popup for sensitive actions
    theme.py      - palettes + stylesheet builder (light default, dark toggle)

This is a USER-FACING window only - no JSON, no raw logs, no developer
debug panels. Everything the assistant does is shown in plain language:
what it heard, and one short line about what happened next.

This file does NOT know anything about speech-to-text, LLMs, or OS
automation. It only exposes a small public API that the rest of the app
(main.py, once it wires up STT/intent/router) calls into:

    window.set_state("idle" | "listening" | "thinking" | "speaking" | "error")
    window.set_transcript(text)                 <- what the user said
    window.show_feedback(message, is_error)      <- one plain-language result line
    window.ask_confirmation(message) -> bool     <- themed Yes/No popup
    window.mic_clicked                            <- Qt signal, connect your STT logic

Keeping the GUI ignorant of the backend is deliberate: whoever wires up
STT/LLM/automation just needs to call these methods - nobody has to touch
each other's code.
"""

import sys
import os

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsOpacityEffect,
)

from .theme import build_stylesheet, palette, STATE_COLORS, BRAND_ACCENT
from .reactor_widget import ReactorWidget
from .wave_widget import WaveWidget
from .status_pill import StatusPill
from .hud_panel import HudPanel
from .icons import icon
from .confirm_dialog import ask_confirmation

MIC_HINTS = {
    "idle": "Tap the mic and say a command",
    "listening": "Listening...",
    "thinking": "Thinking...",
    "speaking": "Speaking...",
    "error": "Something went wrong",
}

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")


class MainWindow(QMainWindow):
    # emitted when the mic button is clicked; connect this to your STT
    # start/stop logic once it exists.
    mic_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ULTRON")
        self.resize(760, 760)
        self.setMinimumSize(560, 640)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self._theme = "light"      # light by default, per request
        self._state = "idle"
        self._mic_active = False
        self._themed_widgets = []   # anything with set_theme(mode)

        self._build_ui()
        self.apply_theme("light")
        self.set_state("idle")

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        # ---- header row: title + status pill + theme toggle -------------
        header = QHBoxLayout()

        self.title_icon = QLabel()
        self.title_icon.setFixedSize(24, 24)
        title = QLabel("U L T R O N")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Your voice-controlled assistant")
        subtitle.setObjectName("SubtitleLabel")

        title_top = QHBoxLayout()
        title_top.setSpacing(8)
        title_top.addWidget(self.title_icon)
        title_top.addWidget(title)
        title_top.addStretch(1)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addLayout(title_top)
        title_box.addWidget(subtitle)

        self.status_pill = StatusPill()
        self._themed_widgets.append(self.status_pill)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("IconButton")
        self.theme_button.setFixedSize(36, 36)
        self.theme_button.setIconSize(QSize(16, 16))
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setToolTip("Toggle light / dark theme")
        self.theme_button.clicked.connect(self._toggle_theme)

        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(self.status_pill, alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addSpacing(10)
        header.addWidget(self.theme_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(header)

        # ---- center stage: reactor + wave + transcript + mic ------------
        stage = HudPanel(scanline=True)
        self._themed_widgets.append(stage)
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(28, 36, 28, 32)
        stage_layout.setSpacing(4)

        stage_layout.addStretch(1)

        self.reactor = ReactorWidget()
        self._themed_widgets.append(self.reactor)
        stage_layout.addWidget(self.reactor, alignment=Qt.AlignmentFlag.AlignCenter)

        stage_layout.addSpacing(22)

        self.transcript_label = QLabel("Say something to get started...")
        self.transcript_label.setObjectName("TranscriptLabel")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_label.setWordWrap(True)
        stage_layout.addWidget(self.transcript_label)

        stage_layout.addSpacing(8)

        # one plain-language feedback line, with an icon that reflects
        # success / failure - this replaces the old JSON + log panels
        feedback_row = QHBoxLayout()
        feedback_row.addStretch(1)
        self.feedback_icon = QLabel()
        self.feedback_icon.setFixedSize(14, 14)
        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("FeedbackLabel")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        feedback_row.addWidget(self.feedback_icon, alignment=Qt.AlignmentFlag.AlignTop)
        feedback_row.addSpacing(6)
        feedback_row.addWidget(self.feedback_label)
        feedback_row.addStretch(1)
        self.feedback_widget = QWidget()
        self.feedback_widget.setLayout(feedback_row)
        self.feedback_widget.setMinimumHeight(22)
        stage_layout.addWidget(self.feedback_widget)

        stage_layout.addSpacing(18)

        self.wave = WaveWidget()
        self._themed_widgets.append(self.wave)
        stage_layout.addWidget(self.wave)

        stage_layout.addSpacing(20)

        # mic button, solo and centered - the one control a user needs
        mic_col = QVBoxLayout()
        mic_col.setSpacing(10)
        mic_row = QHBoxLayout()
        mic_row.addStretch(1)

        self.mic_button = QPushButton()
        self.mic_button.setObjectName("MicButton")
        self.mic_button.setFixedSize(76, 76)
        self.mic_button.setIconSize(QSize(28, 28))
        self.mic_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_button.clicked.connect(self._on_mic_clicked)
        mic_row.addWidget(self.mic_button)
        mic_row.addStretch(1)
        mic_col.addLayout(mic_row)

        self.mic_hint = QLabel(MIC_HINTS["idle"])
        self.mic_hint.setObjectName("SubtitleLabel")
        self.mic_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mic_col.addWidget(self.mic_hint)

        stage_layout.addLayout(mic_col)
        stage_layout.addStretch(1)

        outer.addWidget(stage, stretch=1)

    # ---------------------------------------------------------- public API --
    def set_state(self, state: str):
        """state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'error'"""
        if state not in STATE_COLORS:
            state = "idle"
        self._state = state
        self.reactor.set_state(state)
        self.wave.set_state(state)
        self.status_pill.set_state(state)
        self.mic_hint.setText(MIC_HINTS.get(state, ""))

        if state == "idle":
            self.transcript_label.setText("Say something to get started...")

    def set_transcript(self, text: str):
        """Show live/finished speech-to-text output above the wave."""
        self.transcript_label.setText(f"\u201c{text}\u201d")
        self._fade_in(self.transcript_label)

    def show_feedback(self, message: str, is_error: bool = False):
        """Show one short, plain-language result line under the transcript
        (e.g. 'Opened Chrome' or 'Couldn't find that app') with a
        check/alert icon. This is the only feedback a user sees - no logs,
        no raw command data."""
        p = palette(self._theme)
        color = STATE_COLORS["error"] if is_error else STATE_COLORS["listening"]
        glyph = "fa5s.exclamation-circle" if is_error else "fa5s.check-circle"
        self.feedback_icon.setPixmap(icon(glyph, color=color).pixmap(QSize(14, 14)))
        self.feedback_label.setText(message)
        self.feedback_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self._fade_in(self.feedback_widget)

    def ask_confirmation(self, message: str, title: str = "Confirm action") -> bool:
        """Themed Yes/No popup for actions that need explicit approval
        (see app.intent.schema.DESTRUCTIVE_COMMANDS). Blocks until answered."""
        return ask_confirmation(self, message, mode=self._theme, title=title)

    def set_mic_active(self, active: bool):
        """Reflect mic on/off state on the button itself (border glow)."""
        self._mic_active = active
        p = palette(self._theme)
        color = STATE_COLORS["listening"] if active else BRAND_ACCENT
        self.mic_button.setStyleSheet(
            f"""
            QPushButton#MicButton {{
                background-color: {p['panel2']};
                border: 2px solid {color};
                border-radius: 38px;
            }}
            """
        )
        self.mic_button.setIcon(icon("fa5s.microphone", color=color))

    def apply_theme(self, mode: str):
        """mode: 'light' or 'dark'. Restyles the whole window + every
        custom-painted widget (they don't pick up QSS automatically since
        they draw themselves with QPainter)."""
        self._theme = mode
        self.setStyleSheet(build_stylesheet(mode))
        for w in self._themed_widgets:
            w.set_theme(mode)

        self.title_icon.setPixmap(icon("fa5s.bolt", color=BRAND_ACCENT).pixmap(QSize(20, 20)))
        self.theme_button.setIcon(icon("fa5s.sun" if mode == "dark" else "fa5s.moon", color=BRAND_ACCENT))
        self.theme_button.setToolTip(
            "Switch to light theme" if mode == "dark" else "Switch to dark theme"
        )
        self.set_mic_active(self._mic_active)

    # --------------------------------------------------------------- internal --
    def _toggle_theme(self):
        self.apply_theme("dark" if self._theme == "light" else "light")

    def _on_mic_clicked(self):
        self.set_mic_active(not self._mic_active)
        self.mic_clicked.emit()

    def _fade_in(self, widget: QWidget):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(280)
        anim.setStartValue(0.2)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        widget._fade_anim = anim  # keep a reference alive until it finishes


# ---------------------------------------------------------------------------
# Standalone demo: run this file directly to see the GUI cycle through every
# state with fake data, with no STT/LLM/router wired up yet.
#
#     python -m app.gui.main_window
#
# ---------------------------------------------------------------------------
def _run_demo():
    from PyQt6.QtCore import QTimer

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    demo_script = [
        ("idle", "", None),
        ("listening", "open chrome and search cats", None),
        ("thinking", "open chrome and search cats", None),
        ("speaking", "Opening Chrome and searching for cats.", ("Opened Chrome and searched for \u201ccats\u201d", False)),
        ("idle", "", None),
    ]
    state_i = {"i": 0}

    def step():
        state, transcript, feedback = demo_script[state_i["i"] % len(demo_script)]
        window.set_state(state)
        if transcript:
            window.set_transcript(transcript)
        if feedback:
            window.show_feedback(*feedback)
        state_i["i"] += 1

    timer = QTimer()
    timer.timeout.connect(step)
    timer.start(2200)
    step()

    sys.exit(app.exec())


if __name__ == "__main__":
    _run_demo()
