from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from core.timeutil import today
import imgkit

TEMPLATE_DIR = Path(__file__).parent.parent / "skills" / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "skills" / "output"

def generate_image(agenda_data):
    file_name = f"morning_brief_{today()}.png"
    output_image_path = OUTPUT_DIR / file_name

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("newspaper.html")

    rendered_html = template.render(
        date_string=agenda_data.get("date"),
        events=agenda_data.get("events", []),
        tasks_due=agenda_data.get("tasks_due", []),
        user = "Cherish"
    )

    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    options = {
        'format': 'png',
        'width': 680,
        'enable-local-file-access': None
    }
    imgkit.from_string(rendered_html, str(output_image_path).replace("\\", "/"), options=options)
    print(f"Generated image at: {output_image_path}")
    
    return str(output_image_path)
