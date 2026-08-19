"""
web_navigation.py — ULTRON Hands-Free Voice Web Navigation.

Capabilities:
- Open websites and perform direct searches hands-free
- Quick navigation shortcuts: YouTube, GitHub, Reddit, Google Maps, Amazon, StackOverflow, Twitter/X
"""

import re
import logging
import subprocess
import urllib.parse
from typing import Dict, Any

log = logging.getLogger("ultron.navigation")

SITE_MAP = {
    "github": ("https://github.com/search?q=", "https://github.com"),
    "reddit": ("https://www.reddit.com/search/?q=", "https://www.reddit.com"),
    "maps": ("https://www.google.com/maps/search/", "https://www.google.com/maps"),
    "google maps": ("https://www.google.com/maps/search/", "https://www.google.com/maps"),
    "amazon": ("https://www.amazon.com/s?k=", "https://www.amazon.com"),
    "stackoverflow": ("https://stackoverflow.com/questions/tagged/", "https://stackoverflow.com"),
    "twitter": ("https://twitter.com/search?q=", "https://twitter.com"),
    "x": ("https://x.com/search?q=", "https://x.com"),
    "youtube": ("https://www.youtube.com/results?search_query=", "https://www.youtube.com"),
    "wikipedia": ("https://en.wikipedia.org/wiki/Special:Search?search=", "https://en.wikipedia.org"),
    "gmail": ("https://mail.google.com", "https://mail.google.com"),
}


def navigate_to(text: str) -> Dict[str, Any]:
    """Parse site and optional search query, then launch in default browser."""
    clean = text.lower().strip()
    
    # Strip common navigation prefixes
    for pfx in ["open ", "go to ", "navigate to ", "search ", "find "]:
        if clean.startswith(pfx):
            clean = clean[len(pfx):].strip()
            break

    target_site = None
    query = ""

    # Match site from SITE_MAP
    for site, (search_url, base_url) in SITE_MAP.items():
        if clean.startswith(site):
            target_site = site
            remainder = clean[len(site):].strip()
            # Extract query (e.g. "github and search for react")
            q_match = re.sub(r'^(?:and search for|search for|for)\s+', '', remainder).strip()
            query = q_match
            break

    if target_site:
        search_url, base_url = SITE_MAP[target_site]
        if query:
            full_url = f"{search_url}{urllib.parse.quote_plus(query)}"
            msg = f"Searching {target_site.title()} for {query}, sir."
        else:
            full_url = base_url
            msg = f"Opening {target_site.title()}, sir."

        try:
            subprocess.Popen(f'start "" "{full_url}"', shell=True)
            return {"success": True, "url": full_url, "message": msg}
        except Exception as e:
            log.error(f"Navigation error: {e}")
            return {"success": False, "message": f"Failed to open {target_site}: {e}"}

    # Fallback to direct URL or Google Search
    if clean.endswith((".com", ".org", ".net", ".io", ".dev", ".ai", ".in")):
        url = "https://" + clean if not clean.startswith("http") else clean
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return {"success": True, "url": url, "message": f"Opening {clean}, sir."}

    # Default Google search
    google_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(clean)}"
    subprocess.Popen(f'start "" "{google_url}"', shell=True)
    return {"success": True, "url": google_url, "message": f"Opening search for {clean}, sir."}
