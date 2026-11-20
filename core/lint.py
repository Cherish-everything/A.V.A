# Enforce formatting and wording rules

import re

EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\uFE0F\u200d]")
BANNED_OPENERS = re.compile(r"^\s*(?:certainly|absolutely|great question|i'?d be happy to(?: help)?)\s*[!,.\u2014-]*\s*", re.I)
BANNED_CLOSERS = re.compile(
    r"\s*(?:let me know if (?:you )?(?:need|want) anything(?: else)?|is there anything else(?: i can help (?:you )?with)?|"
    r"hope that helps|feel free to ask)\s*[.!?]*\s*$", re.I)
MARKDOWN = re.compile(r"\*\*|__|`|^\s*#{1,6}\s|^\s*[-*\u2022]\s|^\s*\d+[.)]\s", re.M)

def lint_fix(text):
    """Deterministic clean-up of a spoken reply. Never returns an empty string."""
    out = EMOJI.sub("", text)
    stripped = BANNED_OPENERS.sub("", out, count=1)
    out = stripped if stripped.strip() else out
    stripped = BANNED_CLOSERS.sub("", out)
    out = stripped if stripped.strip() else out
    out = re.sub(r"!+", ".", out)
    out = re.sub(r"\.{2,}(?!\.)", ".", out).replace("..", ".")
    out = re.sub(r"[ \t]{2,}", ".", out)
    out = re.sub(r"(^|[.?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out) #recapitalized after cutting

    return out.strip() or text.strip()

def violations(text, max_words = 60):
    """What is wrong with a reply (used by behavior_check.py to measure compliance). Empty list = clean."""
    found = []
    if len(text.split()) > max_words:
        found.append(f"over {max_words} words")
    if EMOJI.search(text):
        found.append("emoji")
    if MARKDOWN.search(text):
        found.append("markdown")
    if "!" in text:
        found. append("exclamation mark")
    if BANNED_OPENERS.search(text) or BANNED_CLOSERS.search(text):
        found.append("banned phrase")
    if text.count("?") > 1:
        found.append("more than one question")
    print(found)
    return found
