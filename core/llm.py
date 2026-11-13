from groq import Groq
from openai import OpenAI
import re
from core.config import NVIDIA_API_KEY, GROQ_API_KEY
# CHANGE IT TO NVIDIA

NVIDIA_URL = "https://integrate.api.nvidia.com/v1"
NEMOTRON = "nvidia/nemotron-3.5-super-vl-120b-a12b"
 
# Same fallback for every Nemotron tier: if NVIDIA is down, rate-limited or slow, the reply still happens on Groq.
_GROQ_CHAT = {"provider": "groq", "model": "openai/gpt-oss-20b", "temperature": 0.5,
              "extra_body": {"reasoning_effort": "low"}}
 
TIERS = {
    # quick jobs (is this email important? extract a memory fact): small and fast
    "fast": {"provider": "groq", "model": "openai/gpt-oss-20b", "temperature": 0.1, "max_tokens": 256,
             "extra_body": {"reasoning_effort": "low"}},
    # everyday chat and tool calls: Nemotron with thinking OFF 
    "chat": {"provider": "nvidia", "model": NEMOTRON, "temperature": 0.6, "top_p": 0.95,
             "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
             "fallback": _GROQ_CHAT},
    # hard problems and scripts: Nemotron with thinking ON (give it room: reasoning tokens count against max_tokens)
    "smart": {"provider": "nvidia", "model": NEMOTRON, "temperature": 0.6, "top_p": 0.95, "max_tokens": 8192,
              "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
              "fallback": _GROQ_CHAT},
}
 
_clients = {}
 
 
def _client(provider):
    """Created on first use, so a missing key for a provider you aren't using doesn't crash startup."""
    if provider not in _clients:
        if provider == "groq":
            from groq import Groq
            _clients[provider] = Groq(api_key=GROQ_API_KEY)
        elif provider == "nvidia":
            key = NVIDIA_API_KEY
            if not key:
                raise RuntimeError("NVIDIA_API_KEY is missing. Add it to .env")
            from openai import OpenAI
            _clients[provider] = OpenAI(base_url=NVIDIA_URL, api_key=key, timeout=25.0, max_retries=1)
        else:
            raise ValueError(f"unknown provider: {provider}")
    return _clients[provider]
 
 
def _call(cfg, messages, tools, overrides):
    cfg = dict(cfg)
    provider = cfg.pop("provider")
    cfg.pop("fallback", None)
    params = {**cfg, "messages": messages, **overrides}
    if tools:
        params["tools"] = tools
    return _client(provider).chat.completions.create(**params)
 
 
def chat(messages, tools=None, tier="chat", **kwargs):
    """Every LLM call in A.V.A goes through here. kwargs (temperature, max_tokens...) override the tier."""
    cfg = TIERS[tier]
    try:
        return _call(cfg, messages, tools, kwargs)
    except Exception as e:
        fallback = cfg.get("fallback")
        if not fallback:
            raise
        print(f"[llm] {cfg['provider']} failed ({type(e).__name__}: {str(e)[:80]}); using {fallback['provider']} instead")
        return _call(fallback, messages, tools, kwargs)
 
 
def strip_thinking(text: str) -> str:
    """Removes a model's visible reasoning: <think>...</think> blocks, or a lone </think> where the opening tag is missing."""
    text = text or ""
    text = re.sub(r"(?is)<think>.*?</think>", "", text)       # complete blocks
    text = re.sub(r"(?is)<think>.*$", "", text)               # reasoning cut off before it closed
    if "</think>" in text:                                    # opening tag missing: everything before it is reasoning
        text = text.split("</think>", 1)[1]
    return re.sub(r"(?i)</?think>", "", text).strip()