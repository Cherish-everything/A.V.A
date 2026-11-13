# llm_bench.py (project root). Run:  python llm_bench.py
# Measures what matters for a VOICE assistant: seconds per reply, with your real system prompt (so replies are
# short), repeated 3 times because a shared endpoint varies. Also checks that tools fire only when they should.
import statistics
import time

from core import llm

try:
    from core.chat_loop import SYSTEM          # your real rules, so replies are as short as they are in the app
except Exception:
    SYSTEM = "You are A.V.A, a voice assistant. Speak plainly, no markdown, under 50 words."

RUNS = 3
PROMPTS = ["hey", "what's a good name for a study playlist?", "explain what a mutex is",
           "I'm thinking of applying for the MEXT scholarship, any tips?", "what should I eat tonight"]
TOOL = [{"type": "function", "function": {
    "name": "play_music", "description": "Plays music. ONLY when the user asks to play something.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}]


def run(tier, user, tools=None):
    t0 = time.perf_counter()
    r = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], tools=tools, tier=tier)
    secs = time.perf_counter() - t0
    msg = r.choices[0].message
    tokens = getattr(getattr(r, "usage", None), "completion_tokens", None)
    return secs, tokens, msg


for tier in ("chat", "fast"):
    print(f"\n=== tier: {tier} ({llm.TIERS[tier]['provider']}) ===")
    all_secs, all_tokens = [], []
    for p in PROMPTS:
        results = [run(tier, p) for _ in range(RUNS)]
        secs = [r[0] for r in results]
        toks = [r[1] for r in results if r[1]]
        words = len((results[-1][2].content or "").split())
        all_secs += secs
        all_tokens += [(r[0], r[1]) for r in results if r[1]]
        print(f"  {p[:34]:34} {' '.join(f'{s:4.1f}s' for s in secs)}  | ~{words} words, {toks[-1] if toks else '?'} tokens")
    rate = [t / s for s, t in all_tokens if s > 0]
    print(f"  median {statistics.median(all_secs):.2f}s   slowest {max(all_secs):.2f}s"
          + (f"   speed ~{statistics.median(rate):.0f} tokens/s" if rate else ""))

    fired = lambda text: sum(1 for _ in range(RUNS) if run(tier, text, TOOL)[2].tool_calls)
    print(f"  tool fires on 'play some lofi'           : {fired('play some lofi')}/{RUNS}  (want {RUNS})")
    print(f"  tool fires on 'I had mcdonalds for lunch': {fired('I had mcdonalds for lunch')}/{RUNS}  (want 0)")