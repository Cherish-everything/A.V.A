import ast
import shutil
import io
import mimetypes
import base64

import subprocess
import sys
import tempfile
from pathlib import Path
from registry.registry import tool
from core.llm import chat, strip_thinking

MAX_OUTPUT = 4000
SANDBOX_DIR = Path(__file__).parent.parent / "ava_sandbox"

BLOCKED_MODULES = {"os", "sys", "subprocess", "shutil", "pathlib", "socket", "urllib", "requests", "http", "importlib"}
BLOCKED_CALLS = {"exec", "eval", "compile", "__import__"}

from core.config import AVA_VAULT

VAULT_DIR = Path(AVA_VAULT).resolve() if AVA_VAULT else None

def _resolve_target(filename: str, location: str = "sandbox") -> Path:
    """Resolves a safe path inside either ava_sandbox or AVA_VAULT."""
    clean_path = str(filename).strip().strip('"').lstrip("/\\")
    
    if location == "vault":
        if not VAULT_DIR or not VAULT_DIR.exists():
            raise ValueError("AVA_VAULT is not configured or does not exist.")
        base = VAULT_DIR
    else:
        base = SANDBOX_DIR.resolve()

    target = (base / clean_path).resolve()

    # Security check: prevent '../' traversal outside the chosen root
    if base not in target.parents and target != base:
        raise PermissionError("Path traversal outside allowed directory is blocked.")

    if target.suffix.lower() not in EDITABLE:
        raise ValueError(f"Can't edit {target.suffix} files.")

    return target

def _validate_safe_ast(code: str):
    """Inspects the Python syntax tree and blocks dangerous imports or built-ins before execution."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BLOCKED_MODULES:
                    raise PermissionError(f"Blocked import: '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in BLOCKED_MODULES:
                raise PermissionError(f"Blocked import from: '{node.module}'")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALLS:
                raise PermissionError(f"Blocked built-in call: '{node.func.id}()'")

EDITABLE = {".qml", ".py", ".txt", ".md", ".json", ".html", ".csv", ".js", ".css"}

def _sb_path(filename: str) -> Path:
    """Resolves a path inside ava_sandbox, preserving subdirectories like skills/."""
    # Clean up the filename string and prevent path traversal
    clean_path = str(filename).strip().strip('"').lstrip("/\\")
    p = SANDBOX_DIR / clean_path
    
    # Ensure the file extension is allowed
    if p.suffix.lower() not in EDITABLE:
        raise ValueError(f"Can't edit {p.suffix} files.")
    return p

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

def _image_data_url(path: Path) -> str:
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        img.thumbnail((1024, 1024))            # keeps the upload small
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        data, mime = buf.getvalue(), "image/jpeg"
    except ImportError:
        data, mime = path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"

@tool(scope="sandbox.read", risk="read")
def describe_sandbox_image(filename: str, focus: str = "") -> dict:
    """Look at an image in ava_sandbox (a reference screenshot or mockup) and get a detailed description to build from."""
    try:
        p = SANDBOX_DIR / Path(filename).name
        if p.suffix.lower() not in IMG_EXTS:
            return {"error": "Only png, jpg, jpeg and webp images are supported."}
        if not p.exists():
            return {"error": f"'{p.name}' not found in ava_sandbox."}
        prompt = ("Describe this image for a developer who has to recreate it in QML: layout, shapes, "
                  "proportions, colors (hex estimates), gradients, glow and shadow effects, spacing, and any text. "
                  "Be concrete and structured."
                  + (f" Focus on: {focus}" if focus else ""))
        resp = chat([{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _image_data_url(p)}},
        ]}], tier="chat", max_tokens=3000)
        text = strip_thinking(resp.choices[0].message.content or "")
        return {"name": p.name, "description": text or "The vision model returned nothing."}
    except Exception as e:
        return {"error": f"Couldn't read the image: {type(e).__name__}: {e}"}

@tool(scope="sandbox.run", risk="read")
def read_sandbox_file(filename: str, offset: int = 0, max_chars: int = 20000, location: str = "sandbox") -> dict:
    """Read a file from ava_sandbox or vault (set location='vault' for Obsidian notes)."""
    try:
        p = _resolve_target(filename, location)
        if not p.exists():
            return {"error": f"'{p.name}' not found in {location}."}
        text = p.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
        return {"name": p.name, "total_chars": len(text),
                "content": text[offset:offset + max_chars],
                "truncated": offset + max_chars < len(text)}
    except Exception as e:
        return {"error": str(e)}

@tool(scope="sandbox.run", risk="additive")
def edit_sandbox_file(filename: str, old: str, new: str, location: str = "sandbox") -> dict:
    """Replace one exact, unique block of text in an ava_sandbox file. Prefer this over rewriting the whole file."""
    try:
        p = _resolve_target(filename, location)
        raw = p.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        n = text.count(old)
        if n != 1:
            return {"error": f"'old' must match exactly once, matched {n} times. Re-read the file and copy it exactly."}
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
        text = text.replace(old, new)
        p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        return {"ok": True, "file": p.name, "backup": p.name + ".bak"}
    except Exception as e:
        return {"error": str(e)}

@tool(scope="sandbox.run", risk="additive")
def write_sandbox_file(filename: str, content: str, location: str = "sandbox") -> dict:
    """Create or fully overwrite a file in ava_sandbox or vault (keeps a .bak of the old one)."""
    try:
        p = _resolve_target(filename, location)
        
        # Block saving skills directly via sandbox file tools
        if "skills" in p.parts or "skills" in filename.lower() or "def run(**kwargs)" in content:
            return {"error": "Error: Skills must be created using the `create_skill` tool, not `write_sandbox_file`."}

        p.parent.mkdir(parents=True, exist_ok=True)
        SANDBOX_DIR.mkdir(exist_ok=True)
        if p.exists():
            shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "file": p.name, "chars": len(content)}
    except Exception as e:
        return {"error": str(e)}
    
@tool(scope="sandbox.run", risk="additive")
def run_ephemeral_script(
    code: str,
    input_filename: str = "",
    output_filename: str = ""
) -> dict:
    """Run a Python script in an isolated self-deleting temp folder.
    - If input_filename is given, copies that file from 'ava_sandbox' into the temp workspace so your script can open(input_filename).
    - If output_filename is given, copies that generated file back into 'ava_sandbox' after execution."""
    try:
        _validate_safe_ast(code)
        SANDBOX_DIR.mkdir(exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # 1. Stage input file from ava_sandbox into the isolated workspace
            if input_filename:
                safe_in = Path(input_filename).name  # Prevents '../' path traversal
                host_in = SANDBOX_DIR / safe_in
                if not host_in.exists():
                    return {"error": f"Input file '{safe_in}' not found in ava_sandbox."}
                shutil.copy2(host_in, tmp_path / safe_in)

            # 2. Write and run A.V.A's script inside the temporary folder
            script_path = tmp_path / "run.py"
            script_path.write_text(code, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-I", str(script_path)],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=10
            )

            # 3. Export only the specified output file back to ava_sandbox
            saved_to = None
            if result.returncode == 0 and output_filename:
                safe_out = Path(output_filename).name
                tmp_out = tmp_path / safe_out
                if tmp_out.exists():
                    shutil.copy2(tmp_out, SANDBOX_DIR / safe_out)
                    saved_to = str(SANDBOX_DIR / safe_out)

            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout[:MAX_OUTPUT],
                "stderr": result.stderr[:MAX_OUTPUT],
                "saved_output": saved_to,
            }
    except (SyntaxError, PermissionError) as e:
        return {"error": f"Security check failed: {e}"}
    except subprocess.TimeoutExpired:
        return {"error": "Script execution timed out after 10 seconds."}
    except Exception as e:
        return {"error": f"Sandbox execution error: {type(e).__name__}: {e}"}


import textwrap

if __name__ == "__main__":
    print("--- Testing Sandbox Security & Execution ---")
    
    # Test 1: Safe code execution
    res_safe = run_ephemeral_script(code="print('Hello from sandbox!')")
    print("Test 1 (Safe Code):", res_safe)
    
    # Test 2: Blocked import (should raise PermissionError)
    res_blocked = run_ephemeral_script(code="import os\nprint(os.listdir('.'))")
    print("Test 2 (Blocked Import):", res_blocked)
    
    # Test 3: File bridging test
    SANDBOX_DIR.mkdir(exist_ok=True)
    test_in = SANDBOX_DIR / "test_input.txt"
    test_in.write_text("Hello A.V.A!", encoding="utf-8")
    
    bridge_code = textwrap.dedent("""
        with open('test_input.txt', 'r') as f:
            content = f.read()
        print(f"Read from file: {content}")

        with open('test_output.txt', 'w') as f:
            f.write(content.upper())
    """)
    
    res_bridge = run_ephemeral_script(
        code=bridge_code,
        input_filename="test_input.txt",
        output_filename="test_output.txt"
    )
    print("Test 3 (File Bridge):", res_bridge)
    
    # Keep test_input.txt around if you want to inspect it, or comment out unlink
    # if test_in.exists():
    #     test_in.unlink()
    
    print("--- Sandbox Tests Complete ---")