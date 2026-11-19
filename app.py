import sys
import os
import time
import threading
from pathlib import Path
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from core import reply, Speaker, chat_log_write, memory_context, load_history, warm_up, remember_from_conversation
from tools import load_all_tools, generate_image, get_agenda_for_date, push_briefing_to_telegram, start_telegram
from core.llm import chat
from core.memory import clean_chat_log
from core.config import LOG_DIR
from core.timeutil import today
os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg*=false"

def _run_and_send_brief(pathfile: Path, today_str: str):
    image_path = generate_image(get_agenda_for_date("today"))
    push_briefing_to_telegram(image_path)
    
    with open(pathfile, 'w', encoding="utf-8") as f:
        f.write(today_str)

def _morning_brief() -> str:
    log = Path(LOG_DIR)
    pathfile = log / "morning_chronicle.txt"

    log.mkdir(parents=True, exist_ok=True)
    pathfile.touch(exist_ok=True)

    with open(pathfile, 'r', encoding="utf-8") as f:
        last_log = f.read()

    today_str = str(today())

    if today_str in last_log:
        print("already exist")
        return "Morning briefing already deployed."
    else:
        threading.Thread(
            target=_run_and_send_brief, 
            args=(pathfile, today_str), 
            daemon=True
        ).start()
        return f"Deploying briefing for {today_str}..."
        
class BackendProcessor(QObject):
    """Bridge between the QML window and the A.V.A core."""

    replyReady = pyqtSignal(str)

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
        is_stale = lambda: turn != self._turn
        threading.Thread(target=remember_from_conversation,
                        args=(user_prompt, list(self.history[-4:])), daemon=True).start()
        with self._lock:
            if is_stale():
                self._remember(user_prompt, None)
                return
            try:
                answer = reply(user_prompt, self.history,
                            memory_text=memory_context(user_prompt), cancelled=is_stale)
            except Exception as e:
                answer = f"Error: {e}"
            self._remember(user_prompt, answer)
        if answer is not None and not is_stale():
            self.speaker.speak(answer, show_text=answer, generation=speech_gen)


if __name__ == "__main__":
    load_all_tools()          
    threading.Thread(target=warm_up, daemon=True).start()   
    threading.Thread(target=clean_chat_log, daemon=True).start() 
    threading.Thread(target=start_telegram, daemon=True).start()
    threading.Thread(target=_morning_brief, daemon=True).start()               
    app = QGuiApplication(sys.argv)
    speaker = Speaker()
    backend = BackendProcessor(speaker)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)

    engine.load(str(Path(__file__).parent / "orb.qml"))
    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())                             # inside the if-block, after the check