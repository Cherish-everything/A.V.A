from groq import Groq
from core.config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)

# Model options like model options in claude
MODELS = {
    "fast": "openai/gpt-oss-20b", # quick responses,triages
    "chat": "openai/gpt-oss-20b", #conversational and tool use
    "smart": "qwen/qwen3.6-27b" #script writing
}

def chat(messages, tools=None, tier="chat", **kwargs):
    """LLM call processed here."""
    params= {"model": MODELS[tier], "messages": messages, **kwargs}
    if tools:
        params["tools"] = tools
    return _client.chat.completions.create(**params)


