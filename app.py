import sys
import os
import time
import threading
from pathlib import Path
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from core import reply, Speaker, clean_reply, chat_log_write, memory_context, load_history, warm_up
from tools import load_all_tools
from core.llm import chat
os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg*=false"


class BackendProcessor(QObject):
    """Bridge between the QML window and the A.V.A core."""

    replyReady = pyqtSignal(str)

    @property
    def generation(self):
        return self._generation

    def __init__(self, speaker):
        super().__init__()
        self.speaker = speaker
        self.history = load_history(turns=10)
        self._turn = 0 #inc on every new message
        self._lock = threading.Lock() #locked each time
        speaker.textReady.connect(self.replyReady)
        threading.Thread(target=lambda: chat([{"role": "user", "content": "hi"}], tier="fast", max_tokens=5), daemon=True).start()

    @pyqtSlot(str)                           
    def process_data(self, user_prompt):
        self._turn += 1
        turn = self._turn
        self.speaker.stop(flush_text=False)
        speech_gen = self.speaker.generation
        print(f"Received prompt: {user_prompt}")
        threading.Thread(target=self._work, args=(user_prompt, turn, speech_gen), daemon=True).start()

    def _remember(self, user_prompt, answer):
        messages = [{"role": "user", "content": user_prompt}]
        if answer is not None:
            messages.append({"role": "assistant", "content": answer})
        chat_log_write({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "messages": messages})
        self.history = (self.history + messages)[-20:]

    def _work(self, user_prompt, turn, speech_gen):
        is_stale  = lambda: turn != self._turn
        with self._lock:
            if is_stale():
                self._remember(user_prompt, None)
                return
            try:
                answer = reply(user_prompt, self.history, memory_text=memory_context(user_prompt), cancelled=is_stale) or "(no reply)"
            except Exception as e:
                answer = f"Error: {e}"

            self._remember(user_prompt, answer)
        if answer is not None and not is_stale():
            self.speaker.speak(answer, show_text=answer, generation=speech_gen)


if __name__ == "__main__":
    load_all_tools()          
    threading.Thread(target=warm_up, daemon=True).start()                      
    app = QGuiApplication(sys.argv)
    speaker = Speaker()
    backend = BackendProcessor(speaker)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)

    engine.load(str(Path(__file__).parent / "orb.qml"))
    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())                             # inside the if-block, after the check