"""
web_engine.py — ULTRON Web Fetching & Live Research Engine.

Capabilities:
- DuckDuckGo Instant Knowledge API (zero latency, exact factual definitions)
- DuckDuckGo Search (multi-tier Lite & HTML)
- Wikipedia Article Search & Intro Extracts
- Clean Web Page Text Extractor
"""

import re
import logging
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("ultron.web")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


async def search_web(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Perform a live web search aggregating Instant Knowledge, Wikipedia, and DDG."""
    clean_query = query.strip()
    log.info(f"Searching web for: {clean_query}")
    
    results = []

    # 1. DuckDuckGo Instant Knowledge API
    try:
        ddg_api_url = "https://api.duckduckgo.com/"
        params = {
            "q": clean_query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        async with httpx.AsyncClient(timeout=4.0, verify=False) as client:
            resp = await client.get(ddg_api_url, params=params, headers={"User-Agent": "UltronAI/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText") or data.get("Abstract") or data.get("Answer")
                heading = data.get("Heading")
                if abstract and len(abstract) > 30:
                    results.append({
                        "title": f"Fact: {heading or clean_query}",
                        "href": data.get("AbstractURL", ""),
                        "body": abstract
                    })
    except Exception as e:
        log.debug(f"DDG Instant API failed: {e}")

    # 2. DuckDuckGo Lite / HTML Search
    try:
        url = "https://lite.duckduckgo.com/lite/"
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with httpx.AsyncClient(timeout=5.0, verify=False, follow_redirects=True) as client:
            resp = await client.post(url, data={"q": clean_query}, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("a.result-link")
                snippets = soup.select("td.result-snippet")
                for link, snip in zip(links, snippets):
                    title = link.get_text(strip=True)
                    body = snip.get_text(strip=True)
                    if title and body:
                        results.append({
                            "title": title,
                            "href": link.get("href", ""),
                            "body": body
                        })
                    if len(results) >= max_results:
                        break
    except Exception as e:
        log.debug(f"DDG search failed: {e}")

    # 3. Wikipedia Search API
    if len(results) < 2:
        try:
            wiki_url = "https://en.wikipedia.org/w/api.php"
            headers = {"User-Agent": "UltronAI/1.0 (contact@ultron.io)"}
            async with httpx.AsyncClient(timeout=4.0, verify=False) as client:
                search_resp = await client.get(wiki_url, params={
                    "action": "query",
                    "list": "search",
                    "srsearch": clean_query,
                    "format": "json",
                    "srlimit": "2"
                }, headers=headers)
                
                if search_resp.status_code == 200:
                    search_data = search_resp.json()
                    hits = search_data.get("query", {}).get("search", [])
                    if hits:
                        titles = [h["title"] for h in hits]
                        extract_resp = await client.get(wiki_url, params={
                            "action": "query",
                            "prop": "extracts",
                            "exintro": "1",
                            "explaintext": "1",
                            "titles": "|".join(titles),
                            "format": "json"
                        }, headers=headers)
                        
                        if extract_resp.status_code == 200:
                            pages = extract_resp.json().get("query", {}).get("pages", {})
                            for pid, page in pages.items():
                                p_title = page.get("title", "")
                                p_ext = page.get("extract", "").strip()
                                if p_ext:
                                    results.append({
                                        "title": f"Wikipedia: {p_title}",
                                        "href": f"https://en.wikipedia.org/wiki/{p_title.replace(' ', '_')}",
                                        "body": p_ext[:600]
                                    })
        except Exception as e:
            log.debug(f"Wikipedia search failed: {e}")

    return results


async def fetch_url_content(url: str, max_chars: int = 4000) -> Dict[str, Any]:
    """Fetch a web page and extract clean text content."""
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url
        
    log.info(f"Fetching URL: {clean_url}")
    headers = {"User-Agent": USER_AGENT}
    
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False, follow_redirects=True) as client:
            resp = await client.get(clean_url, headers=headers)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "text": ""}
                
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
                tag.decompose()
                
            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            title = soup.title.string.strip() if soup.title and soup.title.string else clean_url
            
            return {
                "success": True,
                "title": title,
                "url": str(resp.url),
                "text": text[:max_chars],
                "char_count": len(text)
            }
    except Exception as e:
        log.error(f"Failed to fetch {clean_url}: {e}")
        return {"success": False, "error": str(e), "text": ""}


async def get_weather(city: str = "London") -> str:
    """Fetch current weather using wttr.in format."""
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%w+%h"
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200 and resp.text.strip():
                return f"Weather in {city}: {resp.text.strip()}"
    except Exception as e:
        log.debug(f"Weather fetch failed: {e}")
    return f"Unable to fetch current weather for {city}."


async def quick_search_summary(query: str) -> str:
    """Search and return a combined text summary ready for LLM synthesis."""
    results = await search_web(query, max_results=3)
    if not results:
        return f"I could not find direct results for '{query}'."
        
    summary_parts = []
    for r in results:
        summary_parts.append(f"• {r['title']}: {r['body']}")
        
    return "\n".join(summary_parts)
