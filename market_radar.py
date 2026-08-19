"""
market_radar.py — ULTRON Real-Time Financial & Crypto Market Radar.

Capabilities:
- Real-time Crypto pricing (Bitcoin, Ethereum, Solana, Doge, etc.) via CoinGecko API
- Real-time Stock quotes (Apple, Nvidia, Tesla, Microsoft, etc.) via public endpoints
- Zero API keys required
"""

import httpx
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.market")

CRYPTO_MAP = {
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "solana": "solana",
    "sol": "solana",
    "doge": "dogecoin",
    "dogecoin": "dogecoin",
    "cardano": "cardano",
    "ada": "cardano",
    "ripple": "ripple",
    "xrp": "ripple"
}


def get_crypto_price(asset: str) -> Dict[str, Any]:
    """Get live crypto price and 24h change."""
    clean = asset.lower().strip()
    coin_id = CRYPTO_MAP.get(clean, clean)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"

    try:
        with httpx.Client(verify=False, timeout=6.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if coin_id in data:
                    usd = data[coin_id].get("usd", 0)
                    change = data[coin_id].get("usd_24h_change", 0)
                    change_str = f"{change:+.2f}%"
                    name_pretty = coin_id.capitalize()
                    msg = f"{name_pretty} is currently trading at ${usd:,.2f} USD ({change_str} in 24h), sir."
                    return {
                        "success": True,
                        "asset": coin_id,
                        "price": usd,
                        "change_24h": change,
                        "message": msg
                    }
    except Exception as e:
        log.warning(f"Crypto price lookup failed: {e}")

    return {
        "success": False,
        "message": f"Market telemetry unavailable for {asset}, sir."
    }
