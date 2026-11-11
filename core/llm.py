from groq import Groq
import re
from core.config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)

# Model options like model options in claude
TIERS = {
    "fast":  {"model": "openai/gpt-oss-20b", "temperature": 0.2, "max_tokens": 256,
              "extra_body": {"reasoning_effort": "low"}},
    "chat":  {"model": "openai/gpt-oss-20b", "temperature": 0.7},
    "smart": {"model": "qwen/qwen3.8-27b", "temperature": 0.7}
}

def chat(messages, tools=None, tier="chat", **kwargs):
    """Every LLM call goes through here."""
    params = {**TIERS[tier], "messages": messages}  
    params.update(kwargs)                      
    if tools:
        params["tools"] = tools

    print(f"Chat: {tier}")
    return _client.chat.completions.create(**params)

def strip_thinking(text: str) -> str:
    """Removes a model's visible reasoning: <think>...</think> blocks, or a lone </think> where the opening tag is missing."""
    text = text or ""
    text = re.sub(r"(?is)<think>.*?</think>", "", text)       # complete blocks
    text = re.sub(r"(?is)<think>.*$", "", text)               # reasoning cut off before it closed
    if "</think>" in text:                                    # opening tag missing: everything before it is reasoning
        text = text.split("</think>", 1)[1]
    return re.sub(r"(?i)</?think>", "", text).strip()