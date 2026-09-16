"""
main_window.py
---------------
Assembles the ULTRON window from the pieces in this folder:

    ReactorWidget - reactor_widget.py - the Stark-reactor-style "face"
    WaveWidget    - wave_widget.py    - the animated waveform beneath it
    StatusPill    - status_pill.py    - colored state label (top-right)
    HudPanel      - hud_panel.py      - sci-fi card background w/ HUD corners
    theme.py      - palettes + stylesheet builder (light default, dark toggle)

This file does NOT know anything about speech-to-text, LLMs, or OS
automation. It only exposes a small public API that the rest of the app
(main.py, once it wires up STT/intent/router) calls into:

    window.set_state("idle" | "listening" | "thinking" | "speaking" | "error")
    window.set_transcript(text)
    window.set_command(json_text)
    window.append_log(line)
    window.mic_clicked            <- a Qt signal you can connect to

Keeping the GUI ignorant of the backend is deliberate: it means you (Roland)
can build and polish this file completely on its own, and whoever wires up
STT/LLM/automation just needs to call these methods - nobody has to touch
each other's code.
"""

import sys

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QPlainTextEdit,
    QGraphicsOpacityEffect,
)

from .theme import build_stylesheet, palette, STATE_COLORS, BRAND_ACCENT
from .reactor_widget import ReactorWidget
from .wave_widget import WaveWidget
from .status_pill import StatusPill
from .hud_panel import HudPanel
from .icons import icon


class MainWindow(QMainWindow):
    # emitted when the mic button is clicked; connect this to your STT
    # start/stop logic once it exists.
    mic_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ULTRON")
        self.resize(920, 700)
        self.setMinimumSize(680, 560)

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
        subtitle = QLabel("VOICE-CONTROLLED AUTOMATION  \u2022  SYSTEM ONLINE")
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
        self.theme_button.setToolTip("Toggle light / dark theme")
        self.theme_button.clicked.connect(self._toggle_theme)

        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(self.status_pill, alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addSpacing(10)
        header.addWidget(self.theme_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(header)

        # ---- center stage: reactor + wave + transcript -------------------
        stage = HudPanel(scanline=True)
        self._themed_widgets.append(stage)
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(28, 30, 28, 22)
        stage_layout.setSpacing(4)

        self.reactor = ReactorWidget()
        self._themed_widgets.append(self.reactor)
        stage_layout.addWidget(self.reactor, alignment=Qt.AlignmentFlag.AlignCenter)

        self.transcript_label = QLabel("Say something to get started...")
        self.transcript_label.setObjectName("TranscriptLabel")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_label.setWordWrap(True)
        stage_layout.addSpacing(10)
        stage_layout.addWidget(self.transcript_label)

        self.wave = WaveWidget()
        self._themed_widgets.append(self.wave)
        stage_layout.addWidget(self.wave)

        # icon row: clear-log | mic | replay-demo, mic in the middle & larger
        icon_row = QHBoxLayout()
        icon_row.addStretch(1)

        self.clear_button = QPushButton()
        self.clear_button.setObjectName("IconButton")
        self.clear_button.setFixedSize(38, 38)
        self.clear_button.setIconSize(QSize(15, 15))
        self.clear_button.setToolTip("Clear activity log")
        self.clear_button.clicked.connect(lambda: self.log_console.clear())
        icon_row.addWidget(self.clear_button)
        icon_row.addSpacing(18)

        self.mic_button = QPushButton()
        self.mic_button.setObjectName("MicButton")
        self.mic_button.setFixedSize(72, 72)
        self.mic_button.setIconSize(QSize(26, 26))
        self.mic_button.clicked.connect(self._on_mic_clicked)
        icon_row.addWidget(self.mic_button)
        icon_row.addSpacing(18)

        self.replay_button = QPushButton()
        self.replay_button.setObjectName("IconButton")
        self.replay_button.setFixedSize(38, 38)
        self.replay_button.setIconSize(QSize(15, 15))
        self.replay_button.setToolTip("Replay demo sequence")
        icon_row.addWidget(self.replay_button)

        icon_row.addStretch(1)
        stage_layout.addSpacing(6)
        stage_layout.addLayout(icon_row)

        outer.addWidget(stage, stretch=3)

        # ---- bottom row: parsed command + log console -------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(16)

        cmd_panel = HudPanel(scanline=False)
        self._themed_widgets.append(cmd_panel)
        cmd_box = QVBoxLayout(cmd_panel)
        cmd_box.setContentsMargins(16, 14, 16, 14)
        cmd_label_row = QHBoxLayout()
        cmd_label_row.setSpacing(6)
        self.cmd_icon = QLabel()
        self.cmd_icon.setFixedSize(13, 13)
        cmd_label = QLabel("PARSED COMMAND")
        cmd_label.setObjectName("SectionLabel")
        cmd_label_row.addWidget(self.cmd_icon)
        cmd_label_row.addWidget(cmd_label)
        cmd_label_row.addStretch(1)
        self.command_view = QPlainTextEdit()
        self.command_view.setObjectName("CommandView")
        self.command_view.setReadOnly(True)
        self.command_view.setPlainText("// waiting for a command...")
        self.command_view.setFixedHeight(120)
        cmd_box.addLayout(cmd_label_row)
        cmd_box.addWidget(self.command_view)

        log_panel = HudPanel(scanline=False)
        self._themed_widgets.append(log_panel)
        log_box = QVBoxLayout(log_panel)
        log_box.setContentsMargins(16, 14, 16, 14)
        log_label_row = QHBoxLayout()
        log_label_row.setSpacing(6)
        self.log_icon = QLabel()
        self.log_icon.setFixedSize(13, 13)
        log_label = QLabel("ACTIVITY LOG")
        log_label.setObjectName("SectionLabel")
        log_label_row.addWidget(self.log_icon)
        log_label_row.addWidget(log_label)
        log_label_row.addStretch(1)
        self.log_console = QTextEdit()
        self.log_console.setObjectName("LogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setFixedHeight(120)
        log_box.addLayout(log_label_row)
        log_box.addWidget(self.log_console)

        bottom.addWidget(cmd_panel, stretch=1)
        bottom.addWidget(log_panel, stretch=1)
        outer.addLayout(bottom, stretch=0)

    # ---------------------------------------------------------- public API --
    def set_state(self, state: str):
        """state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'error'"""
        if state not in STATE_COLORS:
            state = "idle"
        self._state = state
        self.reactor.set_state(state)
        self.wave.set_state(state)
        self.status_pill.set_state(state)

        if state == "idle":
            self.transcript_label.setText("Say something to get started...")

    def set_transcript(self, text: str):
        """Show live/finished speech-to-text output above the wave."""
        self.transcript_label.setText(text)
        self._fade_in(self.transcript_label)

    def set_command(self, command_text: str):
        """Show the structured JSON command the LLM/router produced."""
        self.command_view.setPlainText(command_text)

    def append_log(self, line: str):
        """Append one line to the activity log (auto-scrolls)."""
        self.log_console.append(line)

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
                border-radius: 36px;
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

        p = palette(mode)
        muted = p["muted"]
        self.title_icon.setPixmap(icon("fa5s.bolt", color=BRAND_ACCENT).pixmap(QSize(20, 20)))
        self.theme_button.setIcon(icon("fa5s.sun" if mode == "dark" else "fa5s.moon", color=BRAND_ACCENT))
        self.theme_button.setToolTip(
            "Switch to light theme" if mode == "dark" else "Switch to dark theme"
        )
        self.clear_button.setIcon(icon("fa5s.trash-alt", color=muted))
        self.replay_button.setIcon(icon("fa5s.redo-alt", color=muted))
        self.cmd_icon.setPixmap(icon("fa5s.terminal", color=muted).pixmap(QSize(13, 13)))
        self.log_icon.setPixmap(icon("fa5s.stream", color=muted).pixmap(QSize(13, 13)))
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
        ("thinking", "open chrome and search cats", '{\n  "function": "web_search",\n  "args": {\n    "app": "chrome",\n    "query": "cats"\n  }\n}'),
        ("speaking", "Opening Chrome and searching for cats.", None),
        ("idle", "", None),
    ]
    state_i = {"i": 0}

    def step():
        state, transcript, command = demo_script[state_i["i"] % len(demo_script)]
        window.set_state(state)
        if transcript:
            window.set_transcript(transcript)
        if command:
            window.set_command(command)
        window.append_log(f"[{state.upper()}] {transcript or '...'}")
        state_i["i"] += 1

    timer = QTimer()
    timer.timeout.connect(step)
    timer.start(2200)
    step()
    window.replay_button.clicked.connect(step)

    sys.exit(app.exec())


if __name__ == "__main__":
    _run_demo()
