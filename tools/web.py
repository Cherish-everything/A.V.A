import json
import urllib.parse
from tavily import TavilyClient
import os
from registry.registry import tool
import requests
from core.config import TAVILY_API_KEY

@tool(scope="web.search", risk="read")
def basic_web_search(query: str, news: bool = False) -> dict:
    """Quick web search for current facts. Set news=True for recent news.
    Returns a short answer plus a few sources."""
    if not TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY is missing. Check your .env file."}

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth="basic",       # "advanced" is slower and costs 2 credits instead of 1
            max_results=3,              # fewer results = fewer tokens
            include_answer=True,        # Tavily writes a short summary for you
            include_raw_content=False,  # skip the full page text (this is the big one)
            include_images=False,
            topic="news" if news else "general",
        )
        return {
            "answer": response.get("answer"),
            "sources": [
                {"title": r["title"], "url": r["url"], "snippet": r["content"][:300]}
                for r in response.get("results", [])
            ],
        }
    except Exception as e:
        return {"error": f"search failed: {e}"}
    
# tools/weather.py
import urllib.parse
import requests
from registry.registry import tool


@tool(scope="weather.read", risk="read", triggers=("weather", "rain", "going out", "should I", "umbrella", "go out", "head out", "should"))
def get_weather_forecast(location: str = "Singapore", days: int = 1, include_temps: bool = False) -> dict:
    """Weather forecast. location is a city name, default Singapore. days is 1 to 3.
    By default returns only the basic outlook (condition and chance of rain).
    Set include_temps=True ONLY if the user asks about temperature, heat, or how hot or cold it is."""
    try:
        resp = requests.get(
            f"https://wttr.in/{urllib.parse.quote(location)}",
            params={"format": "j1"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        days = max(1, min(int(days), len(data["weather"])))   # wttr only gives about 3 days

        forecast = []
        for d in data["weather"][:days]:
            day = {
                "date": d["date"],
                "condition": d["hourly"][4]["weatherDesc"][0]["value"],   # the 12:00 reading
                "rain_chance": max(int(h["chanceofrain"]) for h in d["hourly"]),
            }
            if include_temps:
                day["min_c"] = d["mintempC"]
                day["max_c"] = d["maxtempC"]
            forecast.append(day)

        result = {"location": location, "forecast": forecast}
        if include_temps:
            now = data["current_condition"][0]
            result["now"] = {"temp_c": now["temp_C"], "feels_like_c": now["FeelsLikeC"]}
        return result
    except Exception as e:
        return {"error": f"weather lookup failed: {e}"}