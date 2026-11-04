import sys
from pathlib import Path
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, pyqtProperty

class BackendProcessor(QObject):
    """Script to process data and send to QML"""

    statusChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._data = "Null"

    def get_data(self):
        return self._data

    def set_data(self, data):
        if self._data != data:
            self._data = data
            self.statusChanged.emit(self._data)

    user_data = pyqtProperty(str, get_data, set_data, notify=statusChanged)

    @pyqtSlot(str, result=str)
    def process_data(self, text):
        return f"Processed: {text}"

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