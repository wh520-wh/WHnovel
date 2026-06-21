"""
AES-256-GCM encryption for sensitive strings (e.g., API keys).
Key is loaded from environment or .env file.
"""

import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    AESGCM = None
    logger.warning("cryptography package not installed; encryption disabled")


def _load_key() -> bytes | None:
    """Load 32-byte encryption key from environment."""
    env_key = os.environ.get("ENCRYPTION_KEY", "")
    if env_key:
        # If it's a hex string (64 chars = 32 bytes), decode from hex
        if len(env_key) == 64:
            return bytes.fromhex(env_key)
        # Otherwise treat as raw bytes (ensure 32 bytes)
        return env_key.encode()[:32].ljust(32, b"\0")

    # Try to load from .env file in project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("ENCRYPTION_KEY="):
                    val = line.split("=", 1)[1].strip()
                    if len(val) == 64:
                        return bytes.fromhex(val)
                    return val.encode()[:32].ljust(32, b"\0")

    # Derive a key from a machine-specific secret (better than nothing)
    try:
        import uuid

        machine_id = uuid.getnode()
        secret = f"whainoel_secret_{machine_id}".encode()
        return hashlib.sha256(secret).digest()
    except Exception:
        return None


_encryption_key: bytes | None = None


def _get_key() -> bytes | None:
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


def decrypt_safe(ciphertext: str) -> tuple[str, bool]:
    """解密并返回 (明文或原值, 是否漂移)。

    - 非合法 base64 / 长度<13 / 加密未启用 / 无 key → 视为明文，返回 (原值, False)
    - 解密成功 → (明文, False)
    - 解密失败（疑似密钥漂移）→ (原值, True)

    is_drift=True 时调用方应"仅失败时归因"：照常发请求，合法明文 key 会 200 成功、
    is_drift 永不浮现；只有真正 401 时才用 is_drift 区分文案。
    注意：合法明文 key 若恰好是合法 base64 且解码>=13 字节会被判 is_drift=True，
    这是可接受的启发式误判（靠"仅失败时归因"吸收，重填提示对两种情况都有效）。
    """
    if not CRYPTO_AVAILABLE:
        return ciphertext, False

    key = _get_key()
    if key is None:
        return ciphertext, False

    # Quick check: if it doesn't look like base64, it's probably plaintext
    try:
        data = base64.b64decode(ciphertext.encode("ascii"), validate=True)
    except Exception:
        # Not valid base64 — treat as plaintext
        return ciphertext, False

    if len(data) < 13:  # 12-byte nonce + at least 1 byte ciphertext
        return ciphertext, False

    try:
        nonce = data[:12]
        ct = data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8"), False
    except Exception as e:
        logger.warning(
            "Decryption failed (likely encryption key drift or plaintext-as-base64): %s; "
            "returning ciphertext as-is",
            e,
        )
        return ciphertext, True


def decrypt(ciphertext: str) -> str:
    """Decrypt AES-256-GCM ciphertext. Returns plaintext string.

    If the input is not valid base64 or decryption fails (e.g. encryption key
    drift), the input is assumed to be plaintext already and returned as-is.
    This handles the case where keys were stored before encryption was enabled.

    Note: chat_models.py 故意保留 decrypt 调用（不迁移到 decrypt_safe）以兼容
    test_structured_output_robust.py 的 5 处 patch('app.api.chat_models.decrypt')。
    需要漂移信号时用 decrypt_safe。
    """
    return decrypt_safe(ciphertext)[0]


def mask_secret(original: str) -> str:
    """Return a masked version for API responses."""
    if not original:
        return ""
    if len(original) <= 4:
        return "****"
    return original[:2] + "****" + original[-2:]
