from tools import generate_image, get_agenda_for_date
from core.config import LOG_DIR
from pathlib import Path
from core.timeutil import today
import threading

def _morning_brief() -> str:
    log = Path(LOG_DIR)
    filename = "morning_chronicle.txt"
    pathfile = log / filename

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
            target=lambda: generate_image(get_agenda_for_date("today")), 
            daemon=True
        ).start()  
        
        with open(pathfile, 'w', encoding="utf-8") as f:
            f.write(today_str) 
            
        return f"Briefing sent for {today_str}."

if __name__ == "__main__":
    _morning_brief()

