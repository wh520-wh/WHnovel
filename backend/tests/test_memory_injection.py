"""Tests for memory injection into chat body generation."""
from app.api.chat_storage import (
    _build_memory_section,
    _dedupe_memory_updates,
    _normalize_memory,
    _resolve_memory_inject_count,
    _sanitize_memory_entry,
)


def test_resolve_memory_inject_count():
    assert _resolve_memory_inject_count(None) == 50
    assert _resolve_memory_inject_count(-1) == 0
    assert _resolve_memory_inject_count(150) == 100
    assert _resolve_memory_inject_count(30) == 30


def test_normalize_memory():
    assert _normalize_memory("  获得 宝剑 ") == "获得宝剑"


def test_sanitize_memory_entry_truncates_long():
    long = "事件" * 200  # 400 字
    out = _sanitize_memory_entry(long)
    assert len(out) <= 203  # 200 + …
    assert out.endswith("…")


def test_sanitize_memory_entry_drops_code_fence():
    out = _sanitize_memory_entry("```\ncode\n```")
    assert out is None


def test_sanitize_memory_entry_drops_json_leak():
    out = _sanitize_memory_entry('"character_state": {...}')
    assert out is None


def test_sanitize_memory_entry_drops_non_string():
    assert _sanitize_memory_entry(123) is None
    assert _sanitize_memory_entry(None) is None
    assert _sanitize_memory_entry("   ") is None


def test_build_memory_section_basic():
    section = _build_memory_section(["A", "B", "C"], 2)
    assert "B" in section and "C" in section
    assert "A" not in section
    assert "禁止在正文中复述" in section


def test_build_memory_section_zero_count_returns_none():
    assert _build_memory_section(["A"], 0) is None


def test_build_memory_section_empty_log_returns_none():
    assert _build_memory_section([], 50) is None
    assert _build_memory_section(None, 50) is None


def test_build_memory_section_window_n50():
    log = [f"事件{i}" for i in range(1, 51)]  # 第1-50
    section = _build_memory_section(log, 50)
    assert "事件1" in section  # 含第1轮
    assert "事件50" in section


def test_build_memory_section_hard_char_limit_drops_oldest():
    # 50 条各 200 字 = 10000 < 12000，不触发上限
    log = ["字" * 200 for _ in range(50)]
    section = _build_memory_section(log, 50)
    assert section is not None
    # 100 条各 200 字 = 20000 > 12000，触发上限，从最旧丢
    log_big = ["字" * 200 for _ in range(100)]
    section_big = _build_memory_section(log_big, 100)
    assert len(section_big) <= 12000


def test_dedupe_drops_redundant_new():
    # existing 含超集，new 是子串 → 丢弃 new
    assert _dedupe_memory_updates(["获得宝剑的剑鞘"], ["获得宝剑"]) == []


def test_dedupe_keeps_superset_new():
    # existing 是子串，new 是超集 → 保留 new（绝不删已存事实）
    assert _dedupe_memory_updates(["获得宝剑"], ["获得宝剑的剑鞘"]) == ["获得宝剑的剑鞘"]


def test_dedupe_within_batch():
    assert _dedupe_memory_updates([], ["A", "A"]) == ["A"]
    assert _dedupe_memory_updates([], ["获得宝剑的剑鞘", "获得宝剑"]) == ["获得宝剑的剑鞘"]
