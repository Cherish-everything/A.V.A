import re
from pathlib import Path

# Resolve and assemble system prompt cleanly!

_HERE = Path(__file__).resolve().parent
SEARCH_DIRS = [_HERE, _HERE.parent, Path.cwd()] #searches through folder for prompts

MAX_CORRECTIONS = 12

DEFAULTS = {"PERSONA.md": "You are A.V.A, a personal voice assistant. Be brief, calm and honest.",
            "RULES.md": "", "CORRECTIONS.md": ""}

_cache = {}
_warned = set()

def _find(name):
    for base in SEARCH_DIRS:
        for sub in ("", "prompts"):
            path = base / sub / name
            if path.exists():
                return path
    return None

def _read(name):
    path = _find(name)
    if path is None:
        return DEFAULTS[name]
    mtime = path.stat().st_mtime
    hit = _cache.get(name)
    if hit and hit[0] == mtime:
        return hit[1]

    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S).strip()
    _cache[name] = (mtime, text)
    return text

def _sections(text):
    """'## Title' sections -> [(title, body)]. Anything before the first section (the file's intro) is ignored."""
    out = []
    for part in re.split(r"(?m)^##\s+", text)[1:]:
        title, _, body = part.partition("\n")
        out.append((title.strip(), body.strip()))    
    return out

def priority_titles():
    """Titles of the corrections marked with '!', without the '!'."""
    return [t.lstrip("! ").strip() for t, _ in _sections(_read("CORRECTIONS.md")) if t.startswith("!")]

def reminder(max_words=50):
    """One line attached to every user message, where it is obeyed best (it is the last thing the model reads)."""
    line = f"[Voice reply: plain speech, under {max_words} words. Answer only what the user just said."
    titles = priority_titles()
    if titles:
        line += " Remember: " + "; ".join(titles) + "."
    return line + "]"

def build_system(context = ""):
    """context = the changing parts (time line, notes about the user, topic rules)."""

    parts = [_read("PERSONA.md"), _read("RULES.md"),(context or "").strip()]
    sections = _sections(_read("CORRECTIONS.md"))
    if sections:
        if len(sections) > MAX_CORRECTIONS and "many" not in _warned:
            _warned.add("many")
            print(f"[prompts] CORRECTIONS.md has {len(sections)} entries. Above ~{MAX_CORRECTIONS} they get ignored: "
                  "delete the ones she no longer breaks.")
        body = "\n\n".join(f"{t.lstrip('! ').strip()}\n{b}" for t, b in sections)
        parts.append("CORRECTIONS. The user has already corrected you on these. Follow them exactly:\n\n" + body)
    return "\n\n".join(p for p in parts if p)


