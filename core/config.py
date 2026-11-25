# core/config.py
from dotenv import load_dotenv
import os

load_dotenv()  # reads the .env file in your project folder

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
AVA_SEARCH_FOLDER = os.environ.get("AVA_SEARCH_FOLDER")
AVA_VAULT = os.environ.get("AVA_VAULT")

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

if not NVIDIA_API_KEY:
    raise RuntimeError("NVIDIA_PI_KEY is missing. Check your .env file.")

if not NVIDIA_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Check your .env file.")