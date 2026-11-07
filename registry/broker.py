# registry/broker.py
import json
import os
import time

from core.config import LOG_DIR
from registry.registry import TOOLS

AUDIT_FILE = os.path.join(LOG_DIR, "audit.jsonl")


def ask_user_to_confirm(name, args) -> bool:
    """Terminal confirm for now. The UI can replace this later with a button."""
    return input(f"\n[CONFIRM] Allow {name}({args})? [y/N] ").strip().lower() == "y"


confirm_hook = ask_user_to_confirm


def _audit(source, name, args, result):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "tool": name,
        "args": args,
        "result": str(result)[:300],
    }
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, default=str) + "\n")


def call(name, args, grant):
    """The ONLY way anything runs a tool. Checks permission, runs it, logs it."""
    args = args or {}
    t = TOOLS.get(name)

    if t is None:
        result = {"error": f"no such tool: {name}"}
    elif not grant.allows(t.scope):
        result = {"error": f"not permitted: {t.scope}"}
    elif t.risk == "irreversible" and grant.source == "script":
        result = {"error": "scripts cannot use irreversible tools"}
    elif t.risk == "irreversible" and not confirm_hook(name, args):
        result = {"error": "user declined"}
    else:
        try:
            result = t.fn(**args)
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}

    _audit(grant.source, name, args, result)
    return result