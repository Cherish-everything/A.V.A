import os
import re
from core.config import AVA_VAULT
from registry.registry import tool
from tools.files import _inside_roots, search_roots, _conn, _init

MAX_CHARS = 50_000

def _resolve_vault_path(filename):
    """Ensures the file lives inside an allowed search root and ends with .md."""
    name = filename.strip().strip('"')
    if not name.endswith(".md"):
        name += ".md"
    
    roots = search_roots()
    if not roots:
        raise ValueError("No search roots configured in AVA_SEARCH_FOLDERS.")
    
    target_dir = AVA_VAULT
    real_path = os.path.realpath(os.path.join(target_dir, name))
    
    if not _inside_roots(real_path):
        raise ValueError("That path is outside your allowed folders.")
    return real_path

@tool(scope="obsidian.create", risk="additive")
def create_project_note(title: str, content: str = "") -> str:
    """Create a new Markdown note (.md) in your vault for a project (e.g. 'Arm-y').
    Use this when you start a new project or want a dedicated note for an idea."""
    try:
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        if not clean_title:
            return {"error": "Invalid project title."}
        path = _resolve_vault_path(f"{clean_title}.md")
        if os.path.exists(path):
            return {"error": f"A note named '{clean_title}.md' already exists. Use append_to_project_note instead."}
        body = f"# {clean_title}\n\n{content.strip()}\n"[:MAX_CHARS]
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)

        return {"ok": True, "created": os.path.basename(path), "path": path}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Could not create note: {type(e).__name__}"}

@tool(scope="obsidian.edit", risk="additive")
def modify_project_note(project_name: str, content: str, mode: str = "append") -> dict:
    """Modify an existing Obsidian project Markdown file.
    - Use mode='append' (default) to add new ideas, updates, or sections to the bottom.
    - Use mode='overwrite' to replace the entire file (ALWAYS read the note with read_file_excerpt first before overwriting so existing content isn't lost).
    Pass the project name and the content."""
    try:
        path = _resolve_vault_path(project_name)
        if not os.path.exists(path):
            return {"error": f"Could not find a project note named '{os.path.basename(path)}'. Create it first."}
        
        mode = mode.strip().lower()
        if mode == "overwrite":
            body = content.strip()[:MAX_CHARS]
            with open(path, "w", encoding="utf-8") as f:
                f.write(body + "\n")
            action = "overwritten"
        else:
            addition = f"\n\n{content.strip()}"[:MAX_CHARS]
            with open(path, "a", encoding="utf-8") as f:
                f.write(addition)
            action = "appended to"
            
        return {"ok": True, "note": os.path.basename(path), "action": action}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Could not modify note: {type(e).__name__}"}