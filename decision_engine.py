"""
decision_engine.py — ULTRON Randomization & Decision Matrix.

Capabilities:
- Coin flip (Heads/Tails)
- Dice rolling (d6, d20, d100)
- Random number generation between bounds
- Decision maker between options ("Choose between X and Y")
"""

import random
import re
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.decision")


def flip_coin() -> Dict[str, Any]:
    """Flip a virtual coin."""
    res = random.choice(["Heads", "Tails"])
    return {
        "success": True,
        "result": res,
        "message": f"The coin landed on {res}, sir."
    }


def roll_dice(sides: int = 6) -> Dict[str, Any]:
    """Roll a virtual die."""
    res = random.randint(1, sides)
    return {
        "success": True,
        "result": res,
        "sides": sides,
        "message": f"Rolled a {sides}-sided die: Result is {res}, sir."
    }


def pick_random_number(text: str) -> Dict[str, Any]:
    """Pick a random number between min and max."""
    nums = [int(n) for n in re.findall(r'\b\d+\b', text)]
    if len(nums) >= 2:
        low, high = min(nums[0], nums[1]), max(nums[0], nums[1])
    elif len(nums) == 1:
        low, high = 1, nums[0]
    else:
        low, high = 1, 100

    res = random.randint(low, high)
    return {
        "success": True,
        "result": res,
        "low": low,
        "high": high,
        "message": f"Random number between {low} and {high}: {res}, sir."
    }


def choose_option(text: str) -> Dict[str, Any]:
    """Choose randomly between options separated by 'or' / 'and'."""
    clean = re.sub(r'^(?:choose|pick|select)(?:\s+between)?\s+', '', text, flags=re.I)
    options = re.split(r'\s+or\s+|\s+and\s+|,\s*', clean)
    options = [o.strip() for o in options if o.strip()]

    if len(options) >= 2:
        chosen = random.choice(options)
        return {
            "success": True,
            "chosen": chosen,
            "message": f"The calculated choice is: {chosen}, sir."
        }
    return {
        "success": False,
        "message": "Provide at least two options to choose between, sir."
    }
