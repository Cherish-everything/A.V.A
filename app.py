import sys
import os
import threading
from pathlib import Path
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from core import reply, Speaker, clean_reply, shorten_if_needed
from tools import load_all_tools
os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg*=false"


class BackendProcessor(QObject):
    """Bridge between the QML window and the A.V.A core."""

    replyReady = pyqtSignal(str)

    def __init__(self, speaker):
        super().__init__()
        self.speaker = speaker
        self.history = []
        speaker.textReady.connect(self.replyReady)

    def voice_output():
        """A.V.A speaks the text aloud."""

    @pyqtSlot(str)                           
    def process_data(self, user_prompt):
        print(f"Received prompt: {user_prompt}")
        threading.Thread(target=self._work, args=(user_prompt,), daemon=True).start()

    def _work(self, user_prompt):
        try:
            answer = clean_reply(reply(user_prompt, self.history) or "(no reply)")
        except Exception as e:
            answer = f"Error: {e}"
        self.history += [{"role": "user", "content": user_prompt},
                         {"role": "assistant", "content": answer}]
        self.history = self.history[-20:]
        print(f"Reply: {answer}")
        self.speaker.speak(answer, show_text=answer)


if __name__ == "__main__":
    load_all_tools()                                
    app = QGuiApplication(sys.argv)
    speaker = Speaker()
    backend = BackendProcessor(speaker)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)

    engine.load(str(Path(__file__).parent / "orb.qml"))
    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())                             # inside the if-block, after the check