"""
main.py
-------
Entry point. Wires the four independent pieces together:

    Recognizer (app/stt)      -> raw speech to text
    parse_command (app/intent)-> text to a whitelisted {function, args} dict
    Dispatcher (app/router)   -> validates + executes (or asks to confirm)
    MainWindow (app/gui)      -> shows all of the above live

The GUI knows nothing about STT/LLM/automation (by design, see
app/gui/main_window.py's module docstring) — this file is the only place
that imports all of them and connects them with Qt signals.

Run it with:
    python -m app.main
"""

import json
import sys

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.stt.recognizer import Recognizer
from app.intent.parser import parse_command
from app.router.dispatcher import Dispatcher
from app.gui.main_window import MainWindow
from app.utils.logger import get_logger

log = get_logger(__name__)


class PipelineWorker(QThread):
    """Runs mic -> STT -> intent -> router continuously, off the GUI thread
    so the app never freezes while listening or transcribing."""

    transcribed = pyqtSignal(str)
    command_parsed = pyqtSignal(dict)
    status = pyqtSignal(str, bool)          # message, is_error
    needs_confirmation = pyqtSignal(dict)   # command awaiting user approval
    state_changed = pyqtSignal(str)         # idle | listening | thinking | speaking | error

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
                self.command_parsed.emit(command)

                result = self.dispatcher.dispatch(command)

                if result.get("status") == "needs_confirmation":
                    self.needs_confirmation.emit(command)
                    self.state_changed.emit("idle")
                elif result.get("status") == "error":
                    self.status.emit(result.get("message", "Command failed"), True)
                    self.state_changed.emit("error")
                else:
                    self.status.emit(result.get("message", "Done"), False)
                    self.state_changed.emit("speaking")

            except Exception as exc:
                log.exception("Pipeline error")
                self.status.emit(str(exc), True)
                self.state_changed.emit("error")

    def stop(self):
        self._running = False
        self.recognizer.stop()  # unblock a mid-recording listen() call


def main():
    app = QApplication(sys.argv)
    window = MainWindow()

    recognizer = Recognizer()
    dispatcher = Dispatcher()
    worker = PipelineWorker(recognizer, dispatcher)

    # ---- pipeline -> GUI ---------------------------------------------------
    def on_transcribed(text: str):
        window.set_transcript(text)
        window.append_log(f"[HEARD] {text}")

    def on_command_parsed(command: dict):
        window.set_command(json.dumps(command, indent=2))
        window.append_log(f"[PARSED] {command.get('function')} {command.get('args', {})}")

    def on_status(message: str, is_error: bool):
        window.append_log(f"[{'ERROR' if is_error else 'OK'}] {message}")

    def on_state_changed(state: str):
        window.set_state(state)

    def on_needs_confirmation(command: dict):
        function = command.get("function")
        args = command.get("args", {})
        reply = QMessageBox.question(
            window,
            "Confirm action",
            f"Run '{function}' with {args}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            result = dispatcher.confirm(command)
            window.append_log(
                f"[{'ERROR' if result.get('status') == 'error' else 'OK'}] "
                f"{result.get('message', 'Done')}"
            )
            window.set_state("error" if result.get("status") == "error" else "speaking")
        else:
            window.append_log("[CANCELLED] User declined confirmation")
            window.set_state("idle")

    worker.transcribed.connect(on_transcribed)
    worker.command_parsed.connect(on_command_parsed)
    worker.status.connect(on_status)
    worker.state_changed.connect(on_state_changed)
    worker.needs_confirmation.connect(on_needs_confirmation)

    # ---- GUI -> pipeline (mic on/off toggle) -------------------------------
    def on_mic_clicked():
        if worker.isRunning():
            worker.stop()
            window.set_state("idle")
            window.append_log("[MIC] Stopped listening")
        else:
            worker.start()
            window.append_log("[MIC] Listening started")

    window.mic_clicked.connect(on_mic_clicked)

    window.show()
    exit_code = app.exec()

    worker.stop()
    worker.wait(3000)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
