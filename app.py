import sys
import threading
from pathlib import Path
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, pyqtProperty
from core import chat, reply
from registry import broker
from registry.permission import CHAT_GRANT, schemas_for

class BackendProcessor(QObject):
    """Script to process data and send to QML"""

    statusChanged = pyqtSignal(str)
    replyReady = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._data = "Guest"
        self.history = []

    def get_user_prompt(self):
        return self._data

    def set_user_prompt(self, data):
        if self._data != data:
            self._data = data
            self.statusChanged.emit(self._data)

    user_prompt = pyqtProperty(str, get_user_prompt, set_user_prompt, notify=statusChanged)

    history = {}

    @pyqtSlot(str, result=str)
    def process_data(self, user_prompt):
        threading.Thread(target=self._work, args=(user_prompt,), daemon=True).start()

    def _work(self, user_prompt):
        try:
            answer = reply(user_prompt, self.history)
        except Exception as e:
            answer = f"Error: {e}"
        self.history += [{"role": "user", "content": user_prompt},
                         {"role": "assistant", "content": answer}]
        self.history = self.history[-20:]          # keep the last few turns only
        self.replyReady.emit(answer)

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    backend = BackendProcessor()
    engine.rootContext().setContextProperty("backend", backend)

    qml_file = Path(__file__).parent / "orb.qml"
    engine.load(str(qml_file))

    if not engine.rootObjects():
        sys.exit(-1)
sys.exit(app.exec())