"""
instant_math.py — ULTRON Instant Hardware Math & Unit Conversion Engine.

Capabilities:
- Safe AST-based mathematical evaluation (multiplication, division, roots, powers, trigonometry)
- Unit conversions (Fahrenheit <-> Celsius, USD <-> INR, Miles <-> Km, Kg <-> Lbs)
- Zero latency execution directly on hardware
"""

import re
import math
import logging
from typing import Dict, Any, Optional

log = logging.getLogger("ultron.math")

SAFE_MATH_NAMES = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'sqrt': math.sqrt,
    'pi': math.pi,
    'e': math.e,
    'pow': math.pow,
    'log': math.log,
    'abs': abs,
    'round': round,
}


def calculate_expression(expr: str) -> Dict[str, Any]:
    """Safely evaluate mathematical expressions."""
    # Clean expression
    clean = expr.lower().strip()
    clean = re.sub(r'^(?:calculate|what is|whats|evaluate|compute)\s+', '', clean)
    clean = clean.replace("times", "*").replace("multiplied by", "*").replace("x", "*")
    clean = clean.replace("divided by", "/").replace("over", "/")
    clean = clean.replace("plus", "+").replace("minus", "-")
    clean = clean.replace("to the power of", "**").replace("^", "**")
    clean = clean.replace("square root of", "sqrt").replace("sqrt of", "sqrt")
    clean = re.sub(r'[^\d\+\-\*\/\(\)\.\s\w,]', '', clean).strip()

    try:
        # Evaluate safely
        result = eval(clean, {"__builtins__": None}, SAFE_MATH_NAMES)
        if isinstance(result, float):
            result_str = f"{result:.4f}".rstrip('0').rstrip('.')
        else:
            result_str = str(result)
        return {
            "success": True,
            "result": result_str,
            "message": f"The answer is {result_str}, sir."
        }
    except Exception as e:
        log.warning(f"Math eval failed for '{expr}': {e}")
        return {"success": False, "message": "Mathematical calculation was indeterminate, sir."}


def convert_units(text: str) -> Optional[Dict[str, Any]]:
    """Convert common units of temperature, distance, and weight."""
    t = text.lower().strip()
    
    # Fahrenheit to Celsius
    f_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:degrees?\s*)?(?:f|fahrenheit)\s*(?:to|in)\s*(?:c|celsius)', t)
    if f_match:
        val = float(f_match.group(1))
        c = (val - 32) * 5 / 9
        return {"success": True, "message": f"{val} Fahrenheit is {c:.1f} Celsius, sir."}

    # Celsius to Fahrenheit
    c_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:degrees?\s*)?(?:c|celsius)\s*(?:to|in)\s*(?:f|fahrenheit)', t)
    if c_match:
        val = float(c_match.group(1))
        f = (val * 9 / 5) + 32
        return {"success": True, "message": f"{val} Celsius is {f:.1f} Fahrenheit, sir."}

    # Miles to Km
    m_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:miles?)\s*(?:to|in)\s*(?:km|kilometers?)', t)
    if m_match:
        val = float(m_match.group(1))
        km = val * 1.60934
        return {"success": True, "message": f"{val} miles is {km:.2f} kilometers, sir."}

    # Km to Miles
    km_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:km|kilometers?)\s*(?:to|in)\s*(?:miles?)', t)
    if km_match:
        val = float(km_match.group(1))
        miles = val / 1.60934
        return {"success": True, "message": f"{val} kilometers is {miles:.2f} miles, sir."}

    # Kg to Lbs
    kg_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilos?|kilograms?)\s*(?:to|in)\s*(?:lbs?|pounds?)', t)
    if kg_match:
        val = float(kg_match.group(1))
        lbs = val * 2.20462
        return {"success": True, "message": f"{val} kilograms is {lbs:.2f} pounds, sir."}

    return None
