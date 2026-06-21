"""Tests for crypto decrypt/decrypt_safe drift detection."""
from app import crypto


def test_decrypt_safe_valid_ciphertext_returns_plaintext():
    enc = crypto.encrypt("sk-secret")
    value, is_drift = crypto.decrypt_safe(enc)
    assert value == "sk-secret"
    assert is_drift is False


def test_decrypt_safe_plaintext_non_base64_returns_as_is():
    value, is_drift = crypto.decrypt_safe("not-a-base64!!!key")
    assert value == "not-a-base64!!!key"
    assert is_drift is False


def test_decrypt_safe_short_base64_returns_as_is():
    import base64
    short = base64.b64encode(b"short").decode("ascii")  # < 13 bytes
    value, is_drift = crypto.decrypt_safe(short)
    assert value == short
    assert is_drift is False


def test_decrypt_safe_drift_blob_returns_ciphertext_true(monkeypatch):
    """用 keyA 加密，切换到 keyB 解密 → is_drift=True，返回原 blob。"""
    blob = crypto.encrypt("sk-drift-test")

    original_load = crypto._load_key

    def fake_load_key():
        return b"\x11" * 32  # 不同于真实 key 的 32 字节

    monkeypatch.setattr(crypto, "_load_key", fake_load_key)
    monkeypatch.setattr(crypto, "_encryption_key", None)  # 触发重新加载

    value, is_drift = crypto.decrypt_safe(blob)
    assert value == blob  # 返回原密文（不再空串）
    assert is_drift is True


def test_decrypt_drift_returns_ciphertext_not_empty_string(monkeypatch):
    """核心契约回归：漂移时 decrypt 返回原值，不再返回 ''。"""
    blob = crypto.encrypt("sk-drift-decrypt")
    monkeypatch.setattr(crypto, "_load_key", lambda: b"\x22" * 32)
    monkeypatch.setattr(crypto, "_encryption_key", None)
    assert crypto.decrypt(blob) == blob  # 不再 == ""


def test_decrypt_delegates_to_decrypt_safe():
    """decrypt 内部委托 decrypt_safe。"""
    enc = crypto.encrypt("delegate-test")
    assert crypto.decrypt(enc) == crypto.decrypt_safe(enc)[0]


def test_decrypt_safe_plaintext_base64_key_boundary():
    """合法 base64 且解码>=13 字节的明文 key → decrypt_safe 判 is_drift=True
    （但 decrypt 仍返回该 key 非空，调用方靠'仅失败时归因'吸收）。"""
    import base64
    plaintext_key = "AIzaSyFakeKeyForTesting1234567890"
    blob_like = base64.b64encode(plaintext_key.encode()).decode("ascii")
    value, is_drift = crypto.decrypt_safe(blob_like)
    assert value == blob_like
    assert crypto.decrypt(blob_like) == blob_like
