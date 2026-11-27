import json
import importlib.util
from pathlib import Path
from dotenv import load_dotenv
from registry.registry import tool

load_dotenv()

SKILLS_DIR = Path("ava_sandbox/skills")
PERMS_FILE = Path("permissions.json")

SKILLS_DIR.mkdir(exist_ok=True)
if not PERMS_FILE.exists():
    PERMS_FILE.write_text(json.dumps({"approved_services": []}, indent= 2))

def check_permission(service_name: str) -> bool:
    """Checks if the user has already granted A.V.A permission to connect to a service."""
    perms = json.loads(PERMS_FILE.read_text())
    return service_name.lower() in perms["approved_services"]

def grant_permission(service_name:str):
    """Saves user approval so A.V.A doesn't nag every single time."""
    perms = json.loads(PERMS_FILE.read_text())
    service = service_name.lower()
    if service not in perms["approved_services"]:
        perms["approved_services"].append(service)
        PERMS_FILE.write_text(json.dumps(perms, indent= 2))

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

    template = f'''"""
Skill: {safe_name}
Description: {description}
Required Service: {required_service}
"""
import os
from skill_manager import check_permission

def run(**kwargs):
    service = "{required_service}"
    if service and not check_permission(service):
        return f"PERMISSION_REQUIRED:{{service}}"
    
{indent_code(python_code, 4)}
'''
    file_path.write_text(template, encoding="utf-8")
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
        # Dynamically import the Python file from the skills folder
        spec = importlib.util.spec_from_file_location(safe_name, file_path)
        skill_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(skill_module)

        # Check if the skill has a run function and execute it
        if hasattr(skill_module, "run"):
            result = skill_module.run(**kwargs)
            
            # Handle the permission gate response if triggered
            if isinstance(result, str) and result.startswith("PERMISSION_REQUIRED:"):
                service = result.split(":")
                return f"A.V.A needs your permission to connect to '{service}'. Please allow it in the UI!"
            
            return str(result)
        else:
            return f"Error: Skill '{safe_name}' is missing a run() function."

    except Exception as e:
        return f"Error executing skill '{safe_name}': {str(e)}"

def indent_code(code: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in code.splitlines())