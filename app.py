import sys
import threading
from pathlib import Path
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from core import reply
from tools import load_all_tools


class BackendProcessor(QObject):
    """Bridge between the QML window and the A.V.A core."""

    replyReady = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.history = []

    @pyqtSlot(str)                           
    def process_data(self, user_prompt):
        print(f"Received prompt: {user_prompt}")
        threading.Thread(target=self._work, args=(user_prompt,), daemon=True).start()

    def _work(self, user_prompt):
        try:
            answer = reply(user_prompt, self.history) or "(no reply)"
        except Exception as e:
            answer = f"Error: {e}"
        self.history += [{"role": "user", "content": user_prompt},
                         {"role": "assistant", "content": answer}]
        self.history = self.history[-20:]
        self.replyReady.emit(answer)


if __name__ == "__main__":
    load_all_tools()                                

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    backend = BackendProcessor()
    engine.rootContext().setContextProperty("backend", backend)

    engine.load(str(Path(__file__).parent / "orb.qml"))
    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())                             # inside the if-block, after the check