# tools/media.py
import sys
import os
import subprocess
import time
import urllib.parse
import webbrowser
import pyautogui
import yt_dlp
from registry.registry import tool


@tool(scope="media.spotify", risk="additive", triggers=("play", "music", "song", "spotify", "listen", "put on", "queue"))
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

LONG_MIX_SECONDS = 20 * 60          # a "playlist" request prefers a long mix, so it keeps playing
DOCUMENTARY_SECONDS = 15 * 60


def _pick(entries, kind):
    """Best search result: the first one long enough for the kind of request, else simply the first."""
    entries = [e for e in entries if e and e.get("id")]
    if not entries:
        return None
    wanted = LONG_MIX_SECONDS if kind == "playlist" else DOCUMENTARY_SECONDS
    for e in entries:
        if (e.get("duration") or 0) >= wanted:
            return e
    return entries[0]


@tool(scope="media.youtube", risk="additive",
      triggers=("play", "watch", "youtube", "documentary", "playlist", "mood", "music", "listen",
                "put on", "vibe", "sth", "something to", "mix"))
def play_youtube(genre_or_topic: str, kind: str = "playlist") -> dict:
    """Plays something on YouTube. Use kind="playlist" for a mood, genre or vibe ("something chill",
    "late night writing music"). Use kind="documentary" for a topic to learn about ("bioinformatics").
    NOT for a specific song or artist: use play_spotify for those.
    genre_or_topic is the search words, kept specific (e.g. "dark late night lofi"), without the word
    playlist or documentary."""
    kind = "documentary" if str(kind).lower().startswith("doc") else "playlist"
    topic = " ".join(str(genre_or_topic or "").split())
    if not topic:
        return {"error": "nothing to search for"}
    query = topic if kind in topic.lower() else f"{topic} {kind}"

    try:
        import yt_dlp                                    # imported here so a missing package isn't fatal
        opts = {"quiet": True, "skip_download": True, "extract_flat": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch8:{query}", download=False)
        best = _pick(info.get("entries", []), kind)
        if best:
            url = best.get("url") or f"https://www.youtube.com/watch?v={best['id']}"
            webbrowser.open(url)
            return {"ok": True, "playing": best.get("title", query), "url": url}
    except ImportError:
        pass
    except Exception as e:
        print("[youtube] search failed, opening the results page instead:", e)

    webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query))
    return {"ok": True, "opened": "YouTube search results for " + query,
            "note": "Nothing is playing yet: the user has to click a video. Say that."}

