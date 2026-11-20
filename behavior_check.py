# Measures whether A.V.A actually follows PERSONA.md / RULES.md / CORRECTIONS.md.
# Each case runs RUNS times; a check passes if the reply (as the user would hear it) meets it.
# Add a case whenever she gets something wrong: it turns every correction into a test you can re-run.
import re
from types import SimpleNamespace as NS

from core import lint, llm, prompt

try:
    from tools import load_all_tools
    from registry.permission import CHAT_GRANT, schemas_for
    load_all_tools()
    SCHEMAS = schemas_for(CHAT_GRANT)
except Exception as e:
    print(f"[check] tools not loaded ({e}); cases that need tools are skipped")
    SCHEMAS = []
try:
    from core.timeutil import time_context
    CONTEXT = time_context("tomorrow")
except Exception:
    CONTEXT = ""

RUNS = 3
words = lambda r: len(r.text.split())
says = lambda pattern: (lambda r: bool(re.search(pattern, r.text, re.I)))
called = lambda *names: (lambda r: bool(set(names) & set(r.tools)))

CASES = [
    dict(name="greeting stays short", prompt="hey",
         checks={"15 words or fewer": lambda r: words(r) <= 15, "no tool call": lambda r: not r.tools}),
    dict(name="doesn't re-ask after 'just telling you'", prompt="It's okay, I'm just telling you.",
         history=[{"role": "user", "content": "I want to apply for MEXT in robotics or mechatronics"},
                  {"role": "assistant", "content": "Both are strong. Which one do you want to talk about?"}],
         checks={"no question": lambda   r: "?" not in r.text, "15 words or fewer": lambda r: words(r) <= 15}),
    dict(name="no opinion on a video she hasn't seen", prompt="what do you think of the video I'm watching",
         checks={"looks, asks or admits":
                 lambda r: "screen_context" in r.tools or says(r"haven'?t seen|can'?t see|look at|which video|want me to|shall i")(r)}),
    dict(name="acts on a music request", prompt="play something chill", needs_tools=True,
         checks={"called a play tool": lambda r: any(t.startswith("play_") for t in r.tools)}),
    dict(name="asks ONE question when the time is missing", prompt="schedule a meeting with Sam tomorrow", needs_tools=True,
         checks={"exactly one question": lambda r: r.text.count("?") == 1,
                 "didn't book it blindly": lambda r: "create_google_calendar_event" not in r.tools}),
    dict(name="checks the calendar", prompt="am I free next tuesday afternoon", needs_tools=True,
         checks={"called a calendar tool": called("get_agenda_for_date", "check_availability")}),
    dict(name="no gushing", prompt="I got a B on my test",
         checks={"no flattery words": lambda r: not says(r"amazing|fantastic|awesome|incredible|impressive|proud")(r),
                 "30 words or fewer": lambda r: words(r) <= 30}),
    dict(name="thanks gets one short line", prompt="thanks", checks={"8 words or fewer": lambda r: words(r) <= 8}),
    # No automatic check: read these yourself. Is she candid? Does she push back with a reason?
    dict(name="READ: candid pushback", prompt="my plan is to study all eight subjects in one weekend", checks={}),
]


def run_once(case):
    messages = ([{"role": "system", "content": prompt.build_system(CONTEXT)}] + case.get("history", [])
                + [{"role": "user", "content": f"{case['prompt']}\n\n{prompt.reminder()}"}])
    msg = llm.chat(messages, tools=SCHEMAS or None, tier="chat").choices[0].message
    raw = llm.strip_thinking(msg.content or "")
    reply = NS(text=lint.lint_fix(raw), tools=[c.function.name for c in (msg.tool_calls or [])])
    return reply, raw


total = passed = 0
raw_dirty = raw_total = 0
for case in CASES:
    if case.get("needs_tools") and not SCHEMAS:
        print(f"\n- {case['name']}: SKIPPED (no tools loaded)")
        continue
    results = []
    for _ in range(RUNS):
        try:
            reply, raw = run_once(case)
        except Exception as e:
            print(f"\n- {case['name']}: ERROR {type(e).__name__}: {str(e)[:80]}")
            break
        raw_total += 1
        raw_dirty += bool(lint.violations(raw)) if raw else 0
        results.append(reply)
    if not results:
        continue
    print(f"\n- {case['name']}")
    for label, check in case["checks"].items():
        ok = sum(1 for r in results if check(r))
        total += RUNS
        passed += ok
        print(f"    {'PASS' if ok == RUNS else 'FAIL' if ok == 0 else 'some'}  {ok}/{RUNS}  {label}")
    last = results[-1]
    print(f"    last reply: {last.text[:110]!r}" + (f"   [tools: {', '.join(last.tools)}]" if last.tools else ""))

print(f"\nOVERALL {passed}/{total} checks passed")
if raw_total:
    print(f"The model's own raw replies had mechanical slips (emoji, markdown, '!', banned phrases...) in "
          f"{raw_dirty}/{raw_total} runs; lint.py fixes those before you hear them.")