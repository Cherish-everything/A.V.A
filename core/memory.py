import hashlib
import json
import os
import re
import threading
import time
from collections import deque

import chromadb
from chromadb.config import Settings

from core.config import LOG_DIR
from registry.registry import tool

CHAT_HISTORY = os.path.join(LOG_DIR, "chat_history.jsonl")
MEMORY = os.path.join(LOG_DIR, "MEMORY.md")
ARCHIVE = os.path.join(LOG_DIR, "MEMORY_ARCHIVE.md")
CHROMA_DIR = os.path.join(LOG_DIR, "memory_index")

# Cosine distance: 0 = identical meaning, ~1 = unrelated. Tune both with debug("some message").
MAX_DISTANCE = 0.55         # a saved fact is only shown to the model if it's at least this close
DUPLICATE_DISTANCE = 0.2    # a new fact this close to an existing one counts as a duplicate
DEBUG = False               # True prints memory activity to the console

_EMBEDDER = None            # None = Chroma's built-in default model; tests can inject a fake one
_lock = threading.RLock()
_collection_cache = None


def _log(*args):
    if DEBUG:
        print("[memory]", *args)


def _say(*args):
    """One short console line whenever memory actually changes (or a change fails)."""
    print("[memory]", *args)


# =====================================================================
# Chat log: plain functions
# =====================================================================
def chat_log_write(block):
    """Appends one block (a dict) to the jsonl chat log."""
    if not block:
        return False
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(CHAT_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(block, ensure_ascii=False) + "\n")
    return True


def chat_log_read(limit=50):
    """Returns the last `limit` blocks (all of them if limit is None)."""
    if not os.path.exists(CHAT_HISTORY):
        return []
    lines = deque(maxlen=limit)
    with open(CHAT_HISTORY, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                lines.append(line)
    blocks = []
    for line in lines:
        try:
            blocks.append(json.loads(line))
        except json.JSONDecodeError:
            continue                      # skip a corrupt line instead of crashing
    return blocks

def clean_chat_log():
    """Clean the oldest 20 chat logs to prevent big cache files"""
    with open(CHAT_HISTORY, 'r', encoding="utf-8") as f:
        total = sum(1 for line in f)
        print(total)
    if total > 20:
        with open(CHAT_HISTORY, 'r', encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = lines[20:]
        print(new_lines)
        with open(CHAT_HISTORY, 'w', encoding="utf-8") as f:
            f.writelines(new_lines)

def load_history(turns=10):
    """Flat list of chat messages from the last `turns` saved blocks, ready for the LLM."""
    return [m for b in chat_log_read(limit=turns) for m in b.get("messages", [])]


# =====================================================================
# MEMORY.md
# =====================================================================
def load_facts():
    """All saved facts as a list of strings."""
    if not os.path.exists(MEMORY):
        return []
    facts = []
    with open(MEMORY, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(("* ", "- ")) and line[2:].strip():
                facts.append(line[2:].strip())
    return facts


# =====================================================================
# ChromaDB index
# =====================================================================
def _fact_id(fact):
    return hashlib.sha1(fact.lower().encode("utf-8")).hexdigest()[:16]


def _sync(col):
    """Makes the index match MEMORY.md exactly, so lines you add or delete by hand count."""
    wanted = {_fact_id(f): f for f in load_facts()}
    have = set(col.get()["ids"])
    stale = list(have - wanted.keys())
    if stale:
        col.delete(ids=stale)
    missing = [i for i in wanted if i not in have]
    if missing:
        col.upsert(ids=missing, documents=[wanted[i] for i in missing])


def _collection():
    """Opens the index on first use (this is where the embedding model loads), then reuses it."""
    global _collection_cache
    with _lock:
        if _collection_cache is None:
            os.makedirs(CHROMA_DIR, exist_ok=True)
            client = chromadb.PersistentClient(path=CHROMA_DIR,
                                               settings=Settings(anonymized_telemetry=False))
            kwargs = {"embedding_function": _EMBEDDER} if _EMBEDDER is not None else {}
            col = client.get_or_create_collection("facts", metadata={"hnsw:space": "cosine"}, **kwargs)
            _sync(col)
            _collection_cache = col
        return _collection_cache


def warm_up():
    """Call once at startup in a background thread, so the first message isn't slowed by the model loading."""
    try:
        _collection()
        _say("ready, using", os.path.abspath(MEMORY))
    except Exception as e:
        print("[memory] warm-up failed:", e)


def _search(query, limit, max_distance=None):
    """Returns [(fact, distance)], closest first."""
    with _lock:
        col = _collection()
        n = col.count()
        if n == 0:
            return []
        res = col.query(query_texts=[query], n_results=min(limit, n))
    pairs = list(zip(res["documents"][0], res["distances"][0]))
    if max_distance is not None:
        pairs = [(f, d) for f, d in pairs if d <= max_distance]
    return pairs


_SMALL_TALK = re.compile(
    r"^(hey|hi|hello|yo|sup|ok|okay|alright|thanks|thank you|yes|no|yeah|yep|nah|sure|cool|nice|great|good|bye)\b[\s\W]*$",
    re.I)


def memory_context(query="", limit=3):
    """Facts relevant to the user's message, as text for the system prompt (quiet; empty if nothing is close)."""
    q = query.strip()
    if len(q.split()) < 3 or _SMALL_TALK.match(q):
        return ""
    try:
        pairs = _search(q, limit, max_distance=MAX_DISTANCE)
    except Exception as e:
        print("[memory] search failed:", e)
        return ""
    _log(f"{len(pairs)} fact(s) matched: {q[:40]!r}")
    return "\n".join(f"- {fact}" for fact, _ in pairs)


def debug(query, limit=5):
    """Prints how close each saved fact is to a message. Use it to tune the two distances."""
    for fact, dist in _search(query, limit):
        mark = "USED   " if dist <= MAX_DISTANCE else "ignored"
        print(f"{mark} {dist:.2f}  {fact}")


# =====================================================================
# Saving facts
# =====================================================================
def memory_write(fact):
    """Plain function (NOT a tool): saves one fact to MEMORY.md and the index. Skips duplicates."""
    fact = " ".join(str(fact or "").split())
    if not fact:
        return {"error": "nothing to save"}
    with _lock:
        if fact.lower() in (f.lower() for f in load_facts()):
            return {"ok": True, "note": "already saved"}
        try:
            nearest = _search(fact, 1)
            if nearest and nearest[0][1] < DUPLICATE_DISTANCE:
                return {"ok": True, "note": "similar fact already saved", "similar": nearest[0][0]}
        except Exception as e:
            _log("duplicate check skipped:", e)
        new_file = not os.path.exists(MEMORY)
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(MEMORY, "a", encoding="utf-8") as f:
            if new_file:
                f.write("# Long-Term Memory & Facts\n\n")
            f.write(f"* {fact}\n")
        try:
            _collection().upsert(ids=[_fact_id(fact)], documents=[fact])
        except Exception as e:
            print("[memory] index update failed (it will resync on next start):", e)
    _say("saved:", fact)
    return {"ok": True, "saved": fact}


# ---------------------------------------------------------------------
# Changing and forgetting facts
# ---------------------------------------------------------------------
def _norm(text):
    return " ".join(str(text).split()).lower()


def _archive(action, old, new=None):
    """Logs every change with a timestamp. To undo one, copy the old line back into MEMORY.md."""
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"- [{time.strftime('%Y-%m-%d %H:%M')}] {action}: {old}" + (f"  ->  {new}" if new else "")
    with open(ARCHIVE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _edit_file(old_fact, new_fact=None):
    """Replaces (or, when new_fact is None, removes) the bullet holding old_fact.
    Every other line in the file is left exactly as it was. Returns the matched text, or None."""
    if not os.path.exists(MEMORY):
        return None
    with open(MEMORY, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    out, matched = [], None
    for line in lines:
        s = line.strip()
        if matched is None and s.startswith(("* ", "- ")) and _norm(s[2:]) == _norm(old_fact):
            matched = s[2:].strip()
            if new_fact:
                out.append(f"{s[:2]}{new_fact}")
            continue
        out.append(line)
    if matched is not None:
        text = "\n".join(out) + "\n"
        tmp = MEMORY + ".tmp"  
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, MEMORY)
        except PermissionError:  
            with open(MEMORY, "w", encoding="utf-8") as f:
                f.write(text)
            if os.path.exists(tmp):
                os.remove(tmp)
    return matched


def memory_update(old_fact, new_fact):
    """Plain function (NOT a tool): replaces a saved fact with a new version."""
    new_fact = " ".join(str(new_fact or "").split())
    if not new_fact:
        return {"error": "nothing to save"}
    with _lock:
        matched = _edit_file(old_fact, new_fact)
        if matched is None:
            _say("update failed, couldn't find the line:", old_fact)
            return {"error": "no such fact"}
        _archive("replaced", matched, new_fact)
        try:
            col = _collection()
            col.delete(ids=[_fact_id(matched)])
            col.upsert(ids=[_fact_id(new_fact)], documents=[new_fact])
        except Exception as e:
            print("[memory] index update failed (it will resync on next start):", e)
    _say("updated:", matched, "->", new_fact)
    return {"ok": True, "updated": new_fact}


def memory_delete(fact):
    """Plain function (NOT a tool): removes a saved fact. The old line is kept in MEMORY_ARCHIVE.md."""
    with _lock:
        matched = _edit_file(fact, None)
        if matched is None:
            return {"error": "no such fact"}
        _archive("deleted", matched)
        try:
            _collection().delete(ids=[_fact_id(matched)])
        except Exception as e:
            print("[memory] index update failed (it will resync on next start):", e)
    _say("deleted:", matched)
    return {"ok": True, "deleted": matched}


# ---------------------------------------------------------------------
# Automatic note-keeping after each reply (add / update / delete)
# ---------------------------------------------------------------------
EXTRACT_PROMPT = (
    "You maintain long-term notes about a user. You get the user's latest message, the recent conversation "
    "(context only) and ALL existing notes, each with a number. Decide what to change:\n"
    "- add: a NEW lasting fact (identity, preferences, goals, plans, relationships, routines, ongoing projects).\n"
    "- update: the message replaces or corrects what an existing note says. Give the note's number and the new "
    "full sentence. Never add a second note about the same subject: update the old one instead.\n"
    "- delete: the user says to forget a note, or that it is no longer true with no replacement. "
    "Give the note's number.\n"
    "Ignore questions, commands, small talk, one-off tasks and anything about the assistant. "
    "If the user says 'remember', save what they ask. "
    'Write facts as one short sentence starting with "User".\n'
    "Examples:\n"
    '  notes: 1. User lives in Singapore | message: "I moved to Tokyo" -> '
    '{"add": [], "update": [{"note": 1, "new": "User lives in Tokyo"}], "delete": []}\n'
    '  notes: 1. User likes lofi | message: "I also like jazz" -> '
    '{"add": ["User likes jazz"], "update": [], "delete": []}\n'
    '  notes: 1. User likes lofi | message: "forget that" -> {"add": [], "update": [], "delete": [1]}\n'
    'Reply with ONLY JSON in that format. Use empty lists when nothing applies.'
)

CHANGE_WORDS = ("remember", "forget", "actually", "no longer", "anymore", "instead", "changed", "moved",
                "switched", "stopped", "don't like", "dont like", "never mind", "not true", "that's wrong")
# A delete is only applied if the user's own words contain one of these (guards against a wrong guess by the model)
DELETE_CUES = ("forget", "no longer", "anymore", "stopped", "not true", "delete", "remove", "never mind",
               "don't", "dont", "isn't", "isnt", "wrong", "not ")


def _worth_extracting(text):
    """Cheap filter so most messages never cost an LLM call."""
    t = text.strip().lower()
    if any(w in t for w in CHANGE_WORDS):
        return True
    if len(t.split()) < 4 or _SMALL_TALK.match(t):
        return False
    return not t.endswith("?")


def remember_from_conversation(user_prompt, recent=()):
    """Run in a background thread. Reads the user's message and adds, updates or deletes notes.
    Only the USER's own words are used, so web pages and emails can't change memory."""
    result = {"added": [], "updated": [], "deleted": []}
    if not _worth_extracting(user_prompt):
        return result
    from core.llm import chat, strip_thinking

    related = load_facts()
    if len(related) > 60: 
        try:
            related = [f for f, _ in _search(user_prompt, 20, max_distance=0.95)]
        except Exception:
            related = related[-20:]
    notes = "\n".join(f"{i}. {f}" for i, f in enumerate(related, 1)) or "(none yet)"
    context = "\n".join(f"{m['role']}: {m['content']}" for m in list(recent)[-4:])

    try:
        resp = chat(
            [{"role": "system", "content": EXTRACT_PROMPT},
             {"role": "user", "content": f"Existing notes:\n{notes}\n\nRecent conversation:\n{context}\n\n"
                                         f"User's latest message:\n{user_prompt}"}],
            tier="fast", max_tokens=500, temperature=0,
        )
        raw = strip_thinking(resp.choices[0].message.content or "")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        ops = json.loads(match.group(0)) if match else {}
    except Exception as e:
        print("[memory] extraction failed:", e)
        return result

    def note(n):
        try:
            n = int(n)
        except (TypeError, ValueError):
            return None
        return related[n - 1] if 1 <= n <= len(related) else None

    budget = 4 
    for item in ops.get("update", []) or []:
        old = note(item.get("note")) if isinstance(item, dict) else None
        if old and budget > 0 and memory_update(old, item.get("new")).get("updated"):
            result["updated"].append(item["new"])
            budget -= 1
    if any(cue in user_prompt.lower() for cue in DELETE_CUES):
        for n in ops.get("delete", []) or []:
            old = note(n)
            if old and budget > 0 and memory_delete(old).get("deleted"):
                result["deleted"].append(old)
                budget -= 1
    for fact in ops.get("add", []) or []:
        if isinstance(fact, str) and budget > 0:
            saved = memory_write(fact).get("saved")
            if saved:
                result["added"].append(saved)
                budget -= 1

    proposed = bool(ops.get("update") or ops.get("delete") or ops.get("add"))
    if proposed and not any(result.values()):
        _log("model proposed changes but none were applied:", ops)
    return result


# =====================================================================
# Tool the AI can call
# =====================================================================
@tool(scope="memory.read", risk="read")
def memory_read(search: str = "", limit: int = 5) -> dict:
    """Look up saved facts about the user. ONLY call this when the user asks what you know or
    remember about them, or needs a personal detail that isn't in your notes. Never for greetings
    or general questions. Put what you're looking for in search."""
    if search.strip():
        try:
            pairs = _search(search, limit, max_distance=0.85)
            if pairs:
                return {"facts": [fact for fact, _ in pairs]}
        except Exception as e:
            print("[memory] search failed:", e)
    return {"facts": load_facts()[-limit:]}