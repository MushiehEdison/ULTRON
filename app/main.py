import sys
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal

from app.stt.recognizer import Recognizer
from app.intent.parser import parse_command
from app.router.dispatcher import Dispatcher
from app.gui.main_window import MainWindow
from app.utils.logger import get_logger

log = get_logger(__name__)


class PipelineWorker(QThread):
    """Runs one full mic -> STT -> intent -> router cycle per loop iteration,
    off the GUI thread so the app never freezes."""

    transcribed = pyqtSignal(str)
    command_parsed = pyqtSignal(dict)
    status = pyqtSignal(str, bool)          # message, is_error
    needs_confirmation = pyqtSignal(dict)   # command awaiting user approval

    def __init__(self, recognizer: Recognizer, dispatcher: Dispatcher):
        super().__init__()
        self.recognizer = recognizer
        self.dispatcher = dispatcher
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            try:
                text = self.recognizer.listen()
                if not text:
                    continue
                self.transcribed.emit(text)

                command = parse_command(text)
                self.command_parsed.emit(command)

                result = self.dispatcher.dispatch(command)

                if result.get("status") == "needs_confirmation":
                    self.needs_confirmation.emit(command)
                elif result.get("status") == "error":
                    self.status.emit(result.get("message", "Command failed"), True)
                else:
                    self.status.emit(result.get("message", "Done"), False)

            except Exception as exc:
                log.exception("Pipeline error")
                self.status.emit(str(exc), True)

    def stop(self):
        self._running = False


def main():
    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    window = MainWindow()

    recognizer = Recognizer()
    dispatcher = Dispatcher()
    worker = PipelineWorker(recognizer, dispatcher)

    # wire pipeline -> GUI
    worker.transcribed.connect(window.update_transcript)
    worker.command_parsed.connect(window.update_command)
    worker.status.connect(window.update_status)

def handle_confirmation(command: dict):
    if window.ask_confirmation(command):
        result = dispatcher.confirm(command)
        window.update_status(result.get("message", "Done"), result.get("status") == "error")
    else:
        window.update_status("Cancelled", False)

        worker.needs_confirmation.connect(handle_confirmation)

        # wire GUI -> pipeline (mic on/off toggle)
def handle_listening_toggle(is_listening: bool):
    if is_listening and not worker.isRunning():
        worker.start()
    elif not is_listening and worker.isRunning():
        worker.stop()

        window.listening_toggled.connect(handle_listening_toggle)

        window.show()
        exit_code = app.exec()

        worker.stop()
        worker.wait()
        sys.exit(exit_code)


if __name__ == "__main__":
    main()