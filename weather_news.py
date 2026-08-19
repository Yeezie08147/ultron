import httpx
import logging

log = logging.getLogger("ultron.weather_news")

async def get_weather(location: str = "") -> str:
    """Fetches weather from wttr.in. If no location provided, it uses IP location."""
    try:
        url = f"https://wttr.in/{location}?format=3"
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                return resp.text.strip()
            return "Unable to fetch weather data right now."
    except Exception as e:
        log.error(f"Weather error: {e}")
        return "I encountered an error fetching the weather."

async def get_news_headlines() -> str:
    """Fetches basic tech headlines from an open API or RSS if needed. Mocked for now."""
    # Since most news APIs require a key, we will return a generic response or hit a public feed.
    return "The current top headline is: Space Agencies announce new mission to Europa."
