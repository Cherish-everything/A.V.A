# tools/media.py
import sys
import subprocess
import time
import urllib.parse
import pyautogui
from registry.registry import tool


@tool(scope="media.spotify", risk="additive")
def play_spotify(song_or_artist: str) -> dict:
    """Plays a song or artist on Spotify. Use when the user asks to play music."""
    url_safe_song = urllib.parse.quote(song_or_artist)

    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/c", "start", f"spotify:search:{url_safe_song}"], shell=True)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", f"spotify:search:{url_safe_song}"])
    else:
        return {"error": "Spotify launching is only supported on Windows and macOS."}

    time.sleep(2.5)            # let Spotify open and focus
    pyautogui.press("enter")   # select the top search result
    time.sleep(0.5)
    pyautogui.press("enter")   # play it

    return {"ok": True, "playing": song_or_artist}