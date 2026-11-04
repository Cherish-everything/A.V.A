# /registry/broker.py
import json
import os
import time

from core.config import LOG_DIR
from registry.registry import TOOLS

AUDIT_FILE = os.path.join(LOG_DIR, "audit.jsonl")

def user_confirmation(name, args) -> bool:
    """Terminal confirm temporarily"""
    return input(f"Confirm {name} with args {args}? (y/n)").lower().strip() == "y"

confirm_hook = user_confirmation

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