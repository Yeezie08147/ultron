"""
auth_manager.py — ULTRON Master Passcode Security System.

Provides:
- First-time master passcode creation
- PBKDF2 HMAC SHA-256 hashing with cryptographic salt
- Session token generation and validation
- Passcode change functionality
- Persistent credentials storage in data/auth.json
"""

import os
import json
import secrets
import hashlib
import logging
from pathlib import Path
from typing import Tuple, Set

log = logging.getLogger("ultron.auth")

AUTH_FILE = Path(__file__).parent / "data" / "auth.json"

# In-memory store of active authenticated session tokens
_ACTIVE_SESSIONS: Set[str] = set()


def _ensure_dir():
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)


def is_password_set() -> bool:
    """Check if a master passcode has already been configured."""
    if not AUTH_FILE.exists():
        return False
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return bool(data.get("password_hash") and data.get("salt"))
    except Exception as e:
        log.error(f"Error checking auth status: {e}")
        return False


def _hash_password(password: str, salt_hex: str) -> str:
    """Compute PBKDF2 HMAC SHA-256 hash."""
    salt = bytes.fromhex(salt_hex)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return pwd_hash.hex()


def set_password(password: str) -> Tuple[bool, str]:
    """Create or set the master passcode."""
    if not password or len(password) < 3:
        return False, "Passcode must be at least 3 characters long."
    
    _ensure_dir()
    salt_hex = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt_hex)
    
    data = {
        "password_hash": pwd_hash,
        "salt": salt_hex,
        "created_at": str(os.path.getmtime(AUTH_FILE)) if AUTH_FILE.exists() else None
    }
    
    try:
        # Atomic write
        temp_file = AUTH_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(AUTH_FILE)
        log.info("Master passcode successfully initialized.")
        return True, "Master passcode set successfully."
    except Exception as e:
        log.error(f"Failed to save passcode: {e}")
        return False, f"Failed to save passcode: {str(e)}"


def verify_password(password: str) -> bool:
    """Verify an entered passcode against stored credentials."""
    if not AUTH_FILE.exists():
        return False
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        salt_hex = data.get("salt", "")
        stored_hash = data.get("password_hash", "")
        if not salt_hex or not stored_hash:
            return False
        
        computed_hash = _hash_password(password, salt_hex)
        return secrets.compare_digest(computed_hash, stored_hash)
    except Exception as e:
        log.error(f"Error verifying password: {e}")
        return False


def change_password(old_password: str, new_password: str) -> Tuple[bool, str]:
    """Change the master passcode given the current old passcode."""
    if not verify_password(old_password):
        return False, "Incorrect current passcode."
    return set_password(new_password)


def create_session() -> str:
    """Generate and record a new active session token."""
    token = secrets.token_hex(32)
    _ACTIVE_SESSIONS.add(token)
    return token


def verify_session(token: str) -> bool:
    """Validate a session token. If no password is set, automatically valid."""
    if not is_password_set():
        return True
    return bool(token and token in _ACTIVE_SESSIONS)


def invalidate_session(token: str) -> None:
    """Revoke an active session token."""
    _ACTIVE_SESSIONS.discard(token)


def invalidate_all_sessions() -> None:
    """Revoke all active sessions (e.g. on manual system lock)."""
    _ACTIVE_SESSIONS.clear()
