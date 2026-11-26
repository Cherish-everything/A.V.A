import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from registry.registry import tool

MAX_OUTPUT = 4000
SANDBOX_DIR = Path(__file__).parent.parent / "ava_sandbox"

BLOCKED_MODULES = {"os", "sys", "subprocess", "shutil", "pathlib", "socket", "urllib", "requests", "http", "importlib"}
BLOCKED_CALLS = {"exec", "eval", "compile", "__import__"}

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