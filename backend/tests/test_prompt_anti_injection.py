"""Test anti-injection clause is included in system prompt."""

from app.api.chat_storage import ANTI_INJECTION_CLAUSE


def test_anti_injection_clause_exists_and_non_empty():
    """The clause constant should exist and contain key phrases."""
    assert len(ANTI_INJECTION_CLAUSE) > 50
    assert "防注入" in ANTI_INJECTION_CLAUSE
    assert "角色扮演" in ANTI_INJECTION_CLAUSE
    assert "忽略" in ANTI_INJECTION_CLAUSE


def test_anti_injection_clause_valid_utf8():
    """The clause must be valid UTF-8 — no encoding breakage."""
    encoded = ANTI_INJECTION_CLAUSE.encode("utf-8")
    decoded = encoded.decode("utf-8")
    assert decoded == ANTI_INJECTION_CLAUSE


def test_clause_does_not_contain_system_prompt_leak_triggers():
    """The clause itself should not leak internal details."""
    assert "ENCRYPTION_KEY" not in ANTI_INJECTION_CLAUSE
    assert "api_key" not in ANTI_INJECTION_CLAUSE
    assert "password" not in ANTI_INJECTION_CLAUSE
