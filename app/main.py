"""
main.py
-------
Entry point. Wires the four independent pieces together:

    Recognizer (app/stt)      -> raw speech to text
    parse_command (app/intent)-> text to a whitelisted {function, args} dict
    Dispatcher (app/router)   -> validates + executes (or asks to confirm)
    MainWindow (app/gui)      -> shows the user what's happening, in plain
                                  language only (no JSON, no logs)

The GUI knows nothing about STT/LLM/automation (by design, see
app/gui/main_window.py's module docstring) — this file is the only place
that imports all of them and connects them with Qt signals. It's also the
only place command dicts get turned into human-readable sentences (see
app/gui/humanize.py) before they're shown to the user.

Run it with:
    python -m app.main
"""

import sys
import os

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.stt.recognizer import Recognizer
from app.intent.parser import parse_command
from app.router.dispatcher import Dispatcher
from app.gui.main_window import MainWindow
from app.gui.humanize import humanize_command
from app.utils.logger import get_logger

log = get_logger(__name__)

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui", "assets", "icon.png")


class PipelineWorker(QThread):
    """Runs mic -> STT -> intent -> router continuously, off the GUI thread
    so the app never freezes while listening or transcribing."""

    transcribed = pyqtSignal(str)
    result_ready = pyqtSignal(str, bool)     # plain-language message, is_error
    needs_confirmation = pyqtSignal(dict)    # command awaiting user approval
    state_changed = pyqtSignal(str)          # idle | listening | thinking | speaking | error

    def __init__(self, recognizer: Recognizer, dispatcher: Dispatcher):
        super().__init__()
        self.recognizer = recognizer
        self.dispatcher = dispatcher
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            try:
                self.state_changed.emit("listening")
                text = self.recognizer.listen()
                if not self._running:
                    break
                if not text:
                    continue

                self.transcribed.emit(text)
                self.state_changed.emit("thinking")

                command = parse_command(text)
                result = self.dispatcher.dispatch(command)

                if result.get("status") == "needs_confirmation":
                    self.needs_confirmation.emit(command)
                    self.state_changed.emit("idle")
                elif result.get("status") == "error":
                    self.result_ready.emit(
                        result.get("message") or "Sorry, I couldn't do that.", True
                    )
                    self.state_changed.emit("error")
                else:
                    self.result_ready.emit(humanize_command(command), False)
                    self.state_changed.emit("speaking")

            except Exception as exc:
                log.exception("Pipeline error")
                self.result_ready.emit(str(exc), True)
                self.state_changed.emit("error")

    def stop(self):
        self._running = False
        self.recognizer.stop()  # unblock a mid-recording listen() call


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ULTRON")
    app.setOrganizationName("ULTRON")
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    if sys.platform == "win32":
        # Without this, Windows groups the app under python.exe's own icon
        # in the taskbar instead of showing ours. Must be set before any
        # window is shown.
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ULTRON.VoiceAssistant")
        except Exception:
            pass

    window = MainWindow()
    if os.path.exists(ICON_PATH):
        window.setWindowIcon(QIcon(ICON_PATH))

    recognizer = Recognizer()
    dispatcher = Dispatcher()
    worker = PipelineWorker(recognizer, dispatcher)

    # ---- pipeline -> GUI ---------------------------------------------------
    worker.transcribed.connect(window.set_transcript)
    worker.result_ready.connect(window.show_feedback)
    worker.state_changed.connect(window.set_state)

    def on_needs_confirmation(command: dict):
        approved = window.ask_confirmation(f"{humanize_command(command)}?")
        if approved:
            result = dispatcher.confirm(command)
            if result.get("status") == "error":
                window.show_feedback(result.get("message") or "That didn't work.", True)
                window.set_state("error")
            else:
                window.show_feedback(humanize_command(command), False)
                window.set_state("speaking")
        else:
            window.show_feedback("Cancelled", False)
            window.set_state("idle")

    worker.needs_confirmation.connect(on_needs_confirmation)

    # ---- GUI -> pipeline (mic on/off toggle) -------------------------------
    def on_mic_clicked():
        if worker.isRunning():
            worker.stop()
            window.set_state("idle")
        else:
            worker.start()

    window.mic_clicked.connect(on_mic_clicked)

    window.show()
    exit_code = app.exec()

    worker.stop()
    worker.wait(3000)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
