from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import imgkit

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_IMAGE = Path(__file__).parent / "output" / "morning_brief.png"

def generate_image(agenda_data):
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("newspaper.html")

    rendered_html = template.render(
        date_string=agenda_data.get("date"),
        events=agenda_data.get("events", []),
        tasks_due=agenda_data.get("tasks_due", [])
    )

    OUTPUT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    options = {
        'format': 'png',
        'width': 680,
        'enable-local-file-access': None
    }

    imgkit.from_string(rendered_html, str(OUTPUT_IMAGE), options=options)

    return str(OUTPUT_IMAGE)

if __name__ == "__main__":
    mock_agenda = {
        "date": "Sunday 15 November 2026",
        "events": [
            {"start": "07:00", "end": "08:00", "summary": "Morning Coffee & System Check"},
            {"start": "09:30", "end": "11:00", "summary": "Architecture Review: A.V.A Telegram Integration"},
            {"start": "13:00", "end": "14:00", "summary": "Lunch Break"},
            {"start": "16:00", "end": "17:30", "summary": "Configure Headless Linux on Acer TravelMate"}
        ],
        "tasks_due": [
            "Fix chat loop fallback behavior",
            "Test Jinja-to-image conversion script",
            "Back up MEMORY.md to local logs"
        ]
    }
    image_path = generate_image(mock_agenda)
    print(f"Newspaper generated at: {image_path}")
