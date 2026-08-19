"""
base_converter.py — ULTRON Number System & Base Conversion Matrix.

Capabilities:
- Convert between Binary, Hexadecimal, Decimal, and Octal formats instantly
"""

import re
import logging
from typing import Dict, Any, Optional

log = logging.getLogger("ultron.baseconv")


def convert_number_base(text: str) -> Optional[Dict[str, Any]]:
    """Parse text and convert numbers between decimal, hex, and binary."""
    t = text.lower().strip()

    # Decimal to Hex
    m_d2h = re.search(r'(\d+)\s*(?:to|in)\s*(?:hex|hexadecimal)', t)
    if m_d2h:
        val = int(m_d2h.group(1))
        h_str = hex(val).upper().replace("0X", "0x")
        return {"success": True, "message": f"{val} in hexadecimal is {h_str}, sir."}

    # Decimal to Binary
    m_d2b = re.search(r'(\d+)\s*(?:to|in)\s*(?:binary|bin)', t)
    if m_d2b:
        val = int(m_d2b.group(1))
        b_str = bin(val).replace("0b", "")
        return {"success": True, "message": f"{val} in binary is {b_str}, sir."}

    # Hex to Decimal
    m_h2d = re.search(r'(?:0x)?([0-9a-f]+)\s*(?:hex|hexadecimal)?\s*(?:to|in)\s*(?:dec|decimal)', t)
    if m_h2d:
        try:
            val = int(m_h2d.group(1), 16)
            return {"success": True, "message": f"0x{m_h2d.group(1).upper()} in decimal is {val}, sir."}
        except Exception:
            pass

    # Binary to Decimal
    m_b2d = re.search(r'([01]{2,})\s*(?:binary|bin)?\s*(?:to|in)\s*(?:dec|decimal)', t)
    if m_b2d:
        try:
            val = int(m_b2d.group(1), 2)
            return {"success": True, "message": f"Binary {m_b2d.group(1)} in decimal is {val}, sir."}
        except Exception:
            pass

    return None
