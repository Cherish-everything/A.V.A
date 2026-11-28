import string
import json
import importlib.util
from pathlib import Path
from dotenv import load_dotenv
from registry.registry import tool

load_dotenv()

SKILLS_DIR = Path(__file__).parent.parent / "ava_sandbox" / "skills"
PERMS_FILE = Path("permissions.json")

SKILLS_DIR.mkdir(parents=True, exist_ok=True)
if not PERMS_FILE.exists():
    PERMS_FILE.write_text(json.dumps({"approved_services": []}, indent=2))

def check_permission(service_name: str) -> bool:
    """Checks if the user has already granted A.V.A permission to connect to a service."""
    perms = json.loads(PERMS_FILE.read_text())
    return service_name.lower() in perms["approved_services"]

def grant_permission(service_name: str):
    """Saves user approval so A.V.A doesn't nag every single time."""
    perms = json.loads(PERMS_FILE.read_text())
    service = service_name.lower()
    if service not in perms["approved_services"]:
        perms["approved_services"].append(service)
        PERMS_FILE.write_text(json.dumps(perms, indent=2))

SKILL_TEMPLATE = string.Template('''"""
Skill: $safe_name
Description: $description
Required Service: $required_service
"""
import os
import requests
from tools.skill_manager import check_permission

$indented_code
''')

@tool(scope="skill.create", risk="additive")
def create_skill(skill_name: str, skill_type: str, content: str = "", description: str = "", required_service: str = "", python_code: str = "") -> str:
    """
    Creates a new skill for A.V.A.
    - Set skill_type to 'instruction' for writing styles, personas, or prompt guidelines (saves as .md).
    - Set skill_type to 'action' for Python scripts that automate tasks or connect to APIs (saves as .py).
    """
    safe_name = "".join(c for c in skill_name if c.isalnum() or c == "_").lower()
    
    if skill_type == "instruction":
        file_path = SKILLS_DIR / f"{safe_name}.md"
        file_path.write_text(content, encoding="utf-8")
        return f"Created instruction skill '{safe_name}.md'"
    
    file_path = SKILLS_DIR / f"{safe_name}.py"
    
    # Clean up python_code if A.V.A accidentally included its own def run() wrapper
    cleaned_code = python_code.strip()
    if cleaned_code.startswith("def run("):
        lines = cleaned_code.splitlines()
        cleaned_code = "\n".join(lines[1:]).strip()
        cleaned_code = "\n".join(line[4:] if line.startswith("    ") else line for line in cleaned_code.splitlines())

    rendered = SKILL_TEMPLATE.substitute(
        safe_name=safe_name,
        description=description,
        required_service=required_service,
        indented_code=indent_code(cleaned_code, 0)
    )
    file_path.write_text(rendered, encoding="utf-8")
    return f"Successfully created skill '{safe_name}' at {file_path}"

@tool(scope="skill.run", risk="read")
def execute_skill(skill_name: str, **kwargs) -> str:
    """
    Executes a previously created Python skill from the skills folder by its name.
    Use this when the user asks to run a custom skill or automated workflow.
    """
    safe_name = "".join(c for c in skill_name if c.isalnum() or c == "_").lower()
    file_path = SKILLS_DIR / f"{safe_name}.py"

    if not file_path.exists():
        return f"Error: Skill '{safe_name}' does not exist."

    try:
        spec = importlib.util.spec_from_file_location(safe_name, file_path)
        skill_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(skill_module)

        if hasattr(skill_module, "run"):
            result = skill_module.run(**kwargs)
            
            if isinstance(result, str) and result.startswith("PERMISSION_REQUIRED:"):
                service = result.split(":")
                return f"A.V.A needs your permission to connect to '{service}'. Please allow it in the UI!"
            
            if result is None:
                return f"Skill '{safe_name}' executed, but returned no output (None)."
            
            return str(result)
        else:
            return f"Error: Skill '{safe_name}' is missing a required run() function."

    except Exception as e:
        return f"Error executing skill '{safe_name}': {str(e)}"

def indent_code(code: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in code.splitlines())