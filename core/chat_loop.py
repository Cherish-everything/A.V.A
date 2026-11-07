import json
import re
from core import chat
from registry import broker
from registry.permission import CHAT_GRANT, schemas_for

SYSTEM = (
        "You are A.V.A, a concise personal assistant. Use tools when they fit. "
        "If a request needs hard multi-step reasoning, complex planning, or writing a script, "
        "call think_harder first."
        "Keep your responses succinct but still warm and proffessional. Keep spoken responses under 50 words, ignore this limit for script generation"
        "Do NOT use markdown formatting (e.g **) in your responses, keep it in plain text and keep it natural-sounding."
)

STYLE_REMINDER = (
    "[Voice reply: max 2 short sentences, under 40 words, no lists, no markdown. "
    "For options: names only (max 3), then ask which one they want to hear about.]"
)
def clean_reply(text: str) -> str:
        text = re.sub(r"\*+|`+", "", text)                       # **bold**, `code`
        text = re.sub(r"^\s*#+\s*", "", text, flags=re.M)        # # headings
        text = re.sub(r"^\s*(\d+[.)]|[-•])\s+", "", text, flags=re.M)   # list markers
        return re.sub(r"\n{2,}", "\n", text).strip()

WANTS_DETAIL = ("detail", "explain", "in depth", "full list", "all of", "step by step", "tell me", "is nice", "sounds great")

def shorten_if_needed(text, user_prompt, tier):
    if tier == "smart" or len(text.split()) <= 45:
        return text
    if any(w in user_prompt.lower() for w in WANTS_DETAIL):    # the user asked for the long version
        return text
    resp = chat([
        {"role": "system", "content":
            "Rewrite this assistant reply for a voice assistant: at most 2 short sentences, under 35 words, "
            "plain text. If it lists options, name up to 3 by name only, then ask which one the user wants "
            "to hear about. Keep only what answers the question."},
        {"role": "user", "content": f"User asked: {user_prompt}\n\nReply to shorten:\n{text}"},
    ], tier="fast")
    return (resp.choices[0].message.content or text).strip()

def reply(user_prompt, history):
    tier = "chat"
    if user_prompt.startswith("/deep"):
        tier, user_prompt = "smart", user_prompt[len("/deep"):].strip()

    messages = ([{"role": "system", "content": SYSTEM}] + history
                + [{"role": "user", "content": f"{user_prompt}\n\n{STYLE_REMINDER}"}])
    schemas = schemas_for(CHAT_GRANT)

    for _ in range(6):
        msg = chat(messages, tools=schemas, tier=tier).choices[0].message
        if not msg.tool_calls:
            final = msg.content or "(no reply)"
            return clean_reply(shorten_if_needed(final, user_prompt, tier))

        messages.append(msg)
        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = broker.call(name, args, CHAT_GRANT)
            if name == "think_harder":
                tier = "smart"
            messages.append({"role": "tool", "tool_call_id": call.id, "name": name,
                    "content": json.dumps({"result": result,
                                        "reminder": "Answer in 1-2 short sentences."}, default=str)})

    return "I got stuck in a loop, try rephrasing."