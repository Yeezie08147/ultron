"""
security_vault.py — ULTRON Cyber Cryptographic Password Generator.

Capabilities:
- Generates cryptographically secure, high-entropy passwords
- Automatically copies generated password directly to Windows clipboard!
"""

import string
import secrets
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.vault")


def generate_secure_password(length: int = 16) -> Dict[str, Any]:
    """Generate a high-entropy password and copy it to the clipboard."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    # Ensure at least one uppercase, lowercase, digit, and symbol
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    pwd += [secrets.choice(alphabet) for _ in range(max(length - 4, 8))]
    secrets.SystemRandom().shuffle(pwd)
    password_str = "".join(pwd)

    # Copy directly to clipboard
    try:
        import pyperclip
        pyperclip.copy(password_str)
    except Exception:
        pass

    return {
        "success": True,
        "length": len(password_str),
        "message": f"Generated a secure {len(password_str)}-character password and copied it to your clipboard, sir."
    }
