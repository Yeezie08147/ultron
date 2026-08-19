"""
news_radar.py — ULTRON Global & Tech Intelligence Briefing Engine.

Capabilities:
- Real-time Hacker News top headlines (AI, Software, Tech)
- Live Global news summaries via public RSS feeds
"""

import httpx
import logging
from typing import Dict, Any, List

log = logging.getLogger("ultron.news")


def get_tech_briefing(count: int = 3) -> Dict[str, Any]:
    """Fetch top tech intelligence stories from Hacker News."""
    try:
        with httpx.Client(verify=False, timeout=6.0) as client:
            # Top story IDs
            top_ids_resp = client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            if top_ids_resp.status_code != 200:
                return {"success": False, "message": "Global intelligence feed unreachable."}

            story_ids = top_ids_resp.json()[:count]
            stories = []
            
            for sid in story_ids:
                item_resp = client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                if item_resp.status_code == 200:
                    item_data = item_resp.json()
                    title = item_data.get("title", "")
                    if title:
                        stories.append(title)

            if stories:
                bulletin = "; ".join([f"{i+1}. {s}" for i, s in enumerate(stories)])
                msg = f"Tech intelligence briefing: {bulletin}."
                return {
                    "success": True,
                    "stories": stories,
                    "message": msg
                }
    except Exception as e:
        log.warning(f"News fetch failed: {e}")

    return {
        "success": False,
        "message": "Intelligence briefing streams currently offline, sir."
    }
