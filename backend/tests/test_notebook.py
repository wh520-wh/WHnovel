"""Notebook pure-function tests: numbering, injection section, apply update."""

from app.api.notebook import (
    MAX_ACTIVE_PER_LINE,
    apply_notebook_update,
    build_notebook_section,
    format_notebook_for_tail,
)


def _nb(world=None, character=None, relationship=None):
    return {
        "world_line": world or [],
        "character_line": character or [],
        "relationship_line": relationship or [],
    }


def test_build_section_empty_returns_none():
    assert build_notebook_section(None) is None
    assert build_notebook_section(_nb()) is None


def test_build_section_includes_active_with_ids():
    nb = _nb(world=[{"text": "魔教攻入皇城", "status": "active"}])
    section = build_notebook_section(nb)
    assert "[W1] 魔教攻入皇城" in section
    assert "禁止在正文中复述" in section


def test_build_section_three_lines_and_closed_recent():
    nb = _nb(
        world=[
            {"text": "比武大会落幕", "status": "closed"},
            {"text": "魔教攻入皇城", "status": "active"},
        ],
        character=[{"text": "主角获得玄铁剑", "status": "active"}],
        relationship=[{"text": "师徒反目", "status": "active"}],
    )
    section = build_notebook_section(nb)
    # active 先编号，closed 紧随
    assert "[W1] 魔教攻入皇城" in section
    assert "[W2] 比武大会落幕" in section
    assert "[C1] 主角获得玄铁剑" in section
    assert "[R1] 师徒反目" in section


def test_build_section_closed_beyond_10_dropped():
    nb = _nb(world=[{"text": f"旧事{i}", "status": "closed"} for i in range(15)])
    section = build_notebook_section(nb)
    assert "旧事0" not in section
    assert "旧事14" in section


def test_build_section_hard_char_limit():
    nb = _nb(world=[{"text": "长" * 4000, "status": "active"}])  # 4000 字 + header 超 4000 上限
    assert build_notebook_section(nb) is None


def test_apply_adds_new_entries_active():
    nb = _nb()
    out = apply_notebook_update(
        nb,
        {"add_world": ["魔教攻入皇城"], "add_character": ["主角获得玄铁剑"]},
    )
    assert out["world_line"] == [{"text": "魔教攻入皇城", "status": "active"}]
    assert out["character_line"] == [{"text": "主角获得玄铁剑", "status": "active"}]


def test_apply_closes_by_id():
    nb = _nb(world=[{"text": "魔教攻入皇城", "status": "active"}])
    out = apply_notebook_update(nb, {"close_world": ["W1"]})
    assert out["world_line"][0]["status"] == "closed"


def test_apply_ignores_unknown_close_id():
    nb = _nb(world=[{"text": "魔教攻入皇城", "status": "active"}])
    out = apply_notebook_update(nb, {"close_world": ["W99"], "close_character": ["C1"]})
    assert out["world_line"][0]["status"] == "active"
    assert len(out["character_line"]) == 0


def test_apply_does_not_mutate_input():
    nb = _nb(world=[{"text": "魔教攻入皇城", "status": "active"}])
    apply_notebook_update(nb, {"close_world": ["W1"]})
    assert nb["world_line"][0]["status"] == "active"


def test_apply_active_cap_drops_oldest_active():
    nb = _nb(world=[{"text": f"事件{i}", "status": "active"} for i in range(MAX_ACTIVE_PER_LINE)])
    out = apply_notebook_update(nb, {"add_world": ["新事件"]})
    texts = [e["text"] for e in out["world_line"]]
    assert "事件0" not in texts  # 最旧 active 被挤掉
    assert "新事件" in texts


def test_apply_none_notebook_creates():
    out = apply_notebook_update(None, {"add_world": ["新事件"]})
    assert out["world_line"] == [{"text": "新事件", "status": "active"}]


def test_format_tail_includes_closed_recent():
    nb = _nb(world=[{"text": "比武大会落幕", "status": "closed"}])
    text = format_notebook_for_tail(nb)
    assert "比武大会落幕" in text
    assert "W1" in text
