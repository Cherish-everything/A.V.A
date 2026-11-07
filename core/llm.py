from groq import Groq
from core.config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)

# Model options like model options in claude
TIERS = {
    "fast":  {"model": "openai/gpt-oss-20b", "temperature": 0.1,
              "max_tokens": 256, "extra_body": {"reasoning_effort": "low"}},
    "chat":  {"model": "openai/gpt-oss-20b", "temperature": 0.7},
    "smart": {"model": "qwen/qwen3.8-27b",   "temperature": 0.6},
}

def chat(messages, tools=None, tier="chat", **kwargs):
    """Every LLM call goes through here."""
    params = {**TIERS[tier], "messages": messages}  
    params.update(kwargs)                      
    if tools:
        params["tools"] = tools
    return _client.chat.completions.create(**params)