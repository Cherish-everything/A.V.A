import sys
import subprocess
import time
from datetime import datetime
import pyautogui
import os
import shutil
import platform
from pathlib import Path
from registry.registry import tool

EXTENSIONS = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".avif"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv"},
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".md"},
    }



if __name__ == "__main__":
    file_organize()