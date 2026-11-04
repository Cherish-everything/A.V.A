# core/config.py
from dotenv import load_dotenv
import os

load_dotenv()  # reads the .env file in your project folder

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH")

GROQ_MODEL_CHAT = "openai/gpt-oss-20b"
GROQ_MODEL_SCRIPT = "qwen/qwen3.6-27b"  # used later, for writing scripts

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Check your .env file.")