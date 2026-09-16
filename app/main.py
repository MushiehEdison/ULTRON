"""
Entry point for Project Ultron.

Right now this just launches the GUI on its own (no STT/LLM/router wired up
yet - those are empty modules under app/stt, app/intent, app/router).
The GUI cycles through fake states/text every couple seconds so you can see
it working end to end.

Once the other modules are implemented, replace `_run_demo()` below with
real wiring, e.g.:

    from PyQt6.QtWidgets import QApplication
    from app.gui import MainWindow
    from app.stt.recognizer import Recognizer
    from app.intent.parser import parse_intent
    from app.router.dispatcher import dispatch

    app = QApplication(sys.argv)
    window = MainWindow()

    def on_mic_clicked():
        window.set_state("listening")
        text = Recognizer().listen()
        window.set_transcript(text)
        window.set_state("thinking")
        command = parse_intent(text)
        window.set_command(json.dumps(command, indent=2))
        window.set_state("speaking")
        dispatch(command)
        window.set_state("idle")

    window.mic_clicked.connect(on_mic_clicked)
    window.show()
    sys.exit(app.exec())
"""

import sys
import os

# Allow `python app/main.py` to work directly (not just `python -m app.main`)
# by putting the project root (the folder containing `app/`) on sys.path,
# so the `from app.gui import ...` import below can resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from app.gui import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
