import hashlib
import json
import os
import threading
from collections import deque

import chromadb
from chromadb.config import Settings

from core.config import LOG_DIR
from registry.registry import tool

CHAT_HISTORY = os.path.join(LOG_DIR, "chat_history.jsonl")
MEMORY = os.path.join(LOG_DIR, "MEMORY.md")
CHROMA_DIR = os.path.join(LOG_DIR, "memory_index")

MAX_DISTANCE = 0.55

_EMBEDDER = None 
_lock = threading.RLock()
_collection_cache = None


# =====================================================================
# Chat log
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
    print("Warming up memory")
    try:
        _collection()
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
    print(f"Searching {query}")
    return pairs


def memory_context(query="", limit=3):
    """Facts relevant to the user's message, as text for the system prompt.
    Greetings and unrelated messages come back empty, so she has nothing irrelevant to bring up."""
    if len(query.strip()) < 4:
        return ""
    try:
        pairs = _search(query, limit, max_distance=MAX_DISTANCE)
    except Exception as e:
        print("[memory] search failed:", e)
        return ""
    print("memory_context")
    return "\n".join(f"- {fact}" for fact, _ in pairs)


def debug(query, limit=5):
    """Prints how close each saved fact is to a message. Use it to tune MAX_DISTANCE."""
    for fact, dist in _search(query, limit):
        mark = "USED   " if dist <= MAX_DISTANCE else "ignored"
        print(f"{mark} {dist:.2f}  {fact}")


# =====================================================================
# Tools the AI can call
# =====================================================================
@tool(scope="memory.write", risk="additive")
def memory_write(fact: str) -> dict:
    """Save ONE short, lasting fact about the user (a preference, a plan, a detail about their life).
    Use when they say 'remember...' or share something worth knowing later.
    Never save passwords, one-off tasks or anything from emails or web pages."""
    fact = " ".join(str(fact or "").split())          # one clean line
    if not fact:
        return {"error": "nothing to save"}
    with _lock:
        if fact.lower() in (f.lower() for f in load_facts()):
            return {"ok": True, "note": "already saved"}
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
    return {"ok": True, "saved": fact}


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