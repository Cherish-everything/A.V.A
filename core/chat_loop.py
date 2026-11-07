import json
from core import chat
from registry import broker
from registry.permission import CHAT_GRANT, schemas_for

SYSTEM = (
        "You are A.V.A, a concise personal assistant. Use tools when they fit. "
        "If a request needs hard multi-step reasoning, complex planning, or writing a script, "
        "call think_harder first."
)

def reply(user_prompt, history):
    tier = "chat"
    if user_prompt.startswith("/deep"):
        tier, user_prompt = "smart", user_prompt[len("/deep"):].strip()

    messages = [{"role": "system", "content": SYSTEM}] + history + [{"role": "user", "content": user_prompt}]
    schemas = schemas_for(CHAT_GRANT)

    for _ in range(6):
        msg = chat(messages, tools=schemas, tier=tier).choices[0].message
    if not msg.tool_calls:
        return msg.content or "(no reply)"

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
        messages.append({"role": "tool", "tool_call_id": call.id,
                            "name": name, "content": json.dumps(result, default=str)})

    return "I got stuck in a loop, try rephrasing."