"""
AES-256-GCM encryption for sensitive strings (e.g., API keys).
Key is loaded from environment or .env file.
"""
import os
import base64
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    AESGCM = None
    logger.warning("cryptography package not installed; encryption disabled")


def _load_key() -> Optional[bytes]:
    """Load 32-byte encryption key from environment."""
    env_key = os.environ.get("ENCRYPTION_KEY", "")
    if env_key:
        # If it's a hex string (64 chars = 32 bytes), decode from hex
        if len(env_key) == 64:
            return bytes.fromhex(env_key)
        # Otherwise treat as raw bytes (ensure 32 bytes)
        return env_key.encode()[:32].ljust(32, b'\0')

    # Try to load from .env file in project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ENCRYPTION_KEY="):
                    val = line.split("=", 1)[1].strip()
                    if len(val) == 64:
                        return bytes.fromhex(val)
                    return val.encode()[:32].ljust(32, b'\0')

    # Derive a key from a machine-specific secret (better than nothing)
    try:
        import uuid
        machine_id = uuid.getnode()
        secret = f"whainoel_secret_{machine_id}".encode()
        return hashlib.sha256(secret).digest()
    except Exception:
        return None


_encryption_key: Optional[bytes] = None


def _get_key() -> Optional[bytes]:
    global _encryption_key
    if _encryption_key is None:
        _encryption_key = _load_key()
    return _encryption_key


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext with AES-256-GCM. Returns base64 string (nonce + ciphertext)."""
    if not CRYPTO_AVAILABLE:
        logger.warning("cryptography unavailable; storing plaintext")
        return plaintext

    key = _get_key()
    if key is None:
        logger.warning("No encryption key; storing plaintext")
        return plaintext

    try:
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Prepend nonce to ciphertext for storage
        return base64.b64encode(nonce + ct).decode("ascii")
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return plaintext


def decrypt(ciphertext: str) -> str:
    """Decrypt AES-256-GCM ciphertext. Returns plaintext string.

    If the input is not valid base64 or decryption fails (e.g. encryption key
    drift), the input is assumed to be plaintext already and returned as-is.
    This handles the case where keys were stored before encryption was enabled.
    """
    if not CRYPTO_AVAILABLE:
        return ciphertext

    key = _get_key()
    if key is None:
        return ciphertext

    # Quick check: if it doesn't look like base64, it's probably plaintext
    try:
        data = base64.b64decode(ciphertext.encode("ascii"), validate=True)
    except Exception:
        # Not valid base64 — treat as plaintext
        return ciphertext

    if len(data) < 13:  # 12-byte nonce + at least 1 byte ciphertext
        return ciphertext

    try:
        nonce = data[:12]
        ct = data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ""


def mask_secret(original: str) -> str:
    """Return a masked version for API responses."""
    if not original:
        return ""
    if len(original) <= 4:
        return "****"
    return original[:2] + "****" + original[-2:]
