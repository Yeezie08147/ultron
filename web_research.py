import httpx
import logging
from bs4 import BeautifulSoup

log = logging.getLogger("ultron.web_research")

async def search_and_scrape(query: str) -> str:
    """Performs a web search via DuckDuckGo HTML and scrapes the top result."""
    try:
        log.info(f"Web research initiated for: {query}")
        # Search DuckDuckGo HTML version
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = await client.get(search_url, headers=headers, timeout=10.0)
            
            if resp.status_code != 200:
                return f"Search failed with status {resp.status_code}."
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            results = soup.find_all('a', class_='result__snippet')
            
            if not results:
                return "No useful information found on the web."
            
            # Combine the top 3 snippets for a quick summary
            snippets = [res.text.strip() for res in results[:3]]
            combined = " ".join(snippets)
            
            if len(combined) > 800:
                combined = combined[:800] + "..."
                
            return f"Web Research Results: {combined}"
            
    except Exception as e:
        log.error(f"Web research error: {e}")
        return f"I encountered an error accessing the web: {e}"
