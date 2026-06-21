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


def test_build_messages_injects_memory_section():
    from app import models
    from app.api.ai_contracts import TASK_CHAT_RESPONSE, get_contract_output_rule
    from app.api.chat_storage import _build_messages, _build_memory_section, _get_or_create_settings
    from app.database import SessionLocal

    db = SessionLocal()
    story = models.Story(title="mem inject test", world_setting="")
    archive = models.Archive(story=story, name="mi archive", memory_log=["关键事件A", "关键事件B"])
    db.add(archive)
    db.commit()
    db.refresh(archive)

    settings = _get_or_create_settings(db)
    section = _build_memory_section(archive.memory_log, 50, archive_id=archive.id)
    messages = _build_messages(
        story, archive, "input", settings, db,
        include_history=False,
        output_rule_prompt=get_contract_output_rule(TASK_CHAT_RESPONSE),
        memory_section=section,
    )
    system_content = messages[0]["content"]
    assert "关键事件A" in system_content
    assert "关键事件B" in system_content


def test_build_messages_no_memory_section_when_none():
    """memory_section=None → system 不含记忆 section（默认调用方零变化）。"""
    from app import models
    from app.api.ai_contracts import TASK_CHAT_RESPONSE, get_contract_output_rule
    from app.api.chat_storage import _build_messages, _get_or_create_settings
    from app.database import SessionLocal

    db = SessionLocal()
    story = models.Story(title="no mem test", world_setting="")
    archive = models.Archive(story=story, name="nm archive", memory_log=["不应出现的记忆"])
    db.add(archive)
    db.commit()
    db.refresh(archive)

    settings = _get_or_create_settings(db)
    messages = _build_messages(
        story, archive, "input", settings, db,
        include_history=False,
        output_rule_prompt=get_contract_output_rule(TASK_CHAT_RESPONSE),
        # 不传 memory_section → 默认 None
    )
    assert "不应出现的记忆" not in messages[0]["content"]


def test_persist_exchange_conservative_dedupe():
    """_persist_exchange 保守去重：超集新条保留，子串新条丢弃，绝不删既有。"""
    from app import models, schemas
    from app.api.chat_storage import _persist_exchange
    from app.database import SessionLocal

    db = SessionLocal()
    story = models.Story(title="dedupe persist test")
    archive = models.Archive(story=story, name="dp archive", memory_log=["获得宝剑"])
    db.add(archive)
    db.commit()
    db.refresh(archive)

    validated = schemas.ChatResponse(
        reply_text="正文",
        scene="",
        character_state=schemas.CharacterState(),
        story_state=schemas.StoryState(),
        options=[],
        memory_update=["获得宝剑的剑鞘", "获得宝剑"],  # 超集保留 + 子串丢弃
    )
    _persist_exchange(db, archive=archive, user_content="u", validated=validated)
    db.refresh(archive)
    # 既有"获得宝剑"保留 + 新"获得宝剑的剑鞘"保留，"获得宝剑"被子串去重丢弃
    assert "获得宝剑" in archive.memory_log
    assert "获得宝剑的剑鞘" in archive.memory_log
    assert archive.memory_log.count("获得宝剑") == 1  # 不重复


def test_persist_exchange_empty_existing_passthrough():
    """空 existing → 保守去重透传（回归 test_structured_state_integration 不变量）。"""
    from app import models, schemas
    from app.api.chat_storage import _persist_exchange
    from app.database import SessionLocal

    db = SessionLocal()
    story = models.Story(title="empty existing test")
    archive = models.Archive(story=story, name="ee archive", memory_log=[])
    db.add(archive)
    db.commit()
    db.refresh(archive)

    validated = schemas.ChatResponse(
        reply_text="正文", scene="",
        character_state=schemas.CharacterState(), story_state=schemas.StoryState(),
        options=[], memory_update=["测试记忆"],
    )
    _persist_exchange(db, archive=archive, user_content="u", validated=validated)
    db.refresh(archive)
    assert archive.memory_log == ["测试记忆"]


def test_persist_exchange_never_drops_existing_facts():
    """绝对不变量：去重绝不删除/替换既有条目，即便新条与既有重叠。"""
    from app import models, schemas
    from app.api.chat_storage import _persist_exchange
    from app.database import SessionLocal

    db = SessionLocal()
    story = models.Story(title="never drop existing test")
    archive = models.Archive(
        story=story, name="nde archive", memory_log=["既有事件A", "既有事件B"]
    )
    db.add(archive)
    db.commit()
    db.refresh(archive)

    validated = schemas.ChatResponse(
        reply_text="正文", scene="",
        character_state=schemas.CharacterState(), story_state=schemas.StoryState(),
        options=[], memory_update=["既有事件A"],  # 与既有完全相同 → 丢弃新条
    )
    _persist_exchange(db, archive=archive, user_content="u", validated=validated)
    db.refresh(archive)
    # 既有两条原样保留，新增的重复条被丢弃
    assert archive.memory_log == ["既有事件A", "既有事件B"]


def _ensure_stream_model_config(db) -> None:
    """流式正文生成需要可用模型候选，否则 _get_normal_model_candidates 抛 503。"""
    from app import models

    model = models.ModelConfig(
        name="memory-inject-stream-model",
        model_id="memory-inject-stream-model",
        api_base_url="https://example.com/v1",
        api_key="x",
        enabled=1,
        priority=1,
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    settings = db.query(models.UserSettings).first()
    if not settings:
        settings = models.UserSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    settings.primary_model_id = model.id
    settings.backup_model_ids = []
    db.commit()


def test_stream_chat_response_injects_memory():
    """流式正文生成时 system 含记忆 section。"""
    from app import models
    from app.api import chat_stream
    from app.api.chat_storage import _get_or_create_settings
    from app.database import SessionLocal

    db = SessionLocal()
    _ensure_stream_model_config(db)
    story = models.Story(title="stream mem test")
    archive = models.Archive(story=story, name="sm archive", memory_log=["第1轮关键事件"])
    db.add(archive)
    db.commit()
    db.refresh(archive)

    captured = {}

    def fake_stream(model_cfg, messages, temperature, usage):
        captured["messages"] = messages
        usage["prompt_tokens"] = 1
        yield ""

    settings = _get_or_create_settings(db)
    settings.memory_inject_count = 50
    db.commit()

    gen = chat_stream._stream_chat_response(
        db, story=story, archive=archive, settings=settings,
        user_content="继续", persist_user_content="继续",
        include_history=False, first_opening=False, stream_fn=fake_stream,
    )
    list(gen)
    assert "第1轮关键事件" in captured["messages"][0]["content"]


def test_stream_chat_response_no_memory_when_count_zero():
    """memory_inject_count=0 → system 不含记忆 section。"""
    from app import models
    from app.api import chat_stream
    from app.api.chat_storage import _get_or_create_settings
    from app.database import SessionLocal

    db = SessionLocal()
    _ensure_stream_model_config(db)
    story = models.Story(title="zero mem test")
    archive = models.Archive(story=story, name="zm archive", memory_log=["不应出现"])
    db.add(archive)
    db.commit()
    db.refresh(archive)

    captured = {}

    def fake_stream(model_cfg, messages, temperature, usage):
        captured["messages"] = messages
        usage["prompt_tokens"] = 1
        yield ""

    settings = _get_or_create_settings(db)
    settings.memory_inject_count = 0
    db.commit()

    gen = chat_stream._stream_chat_response(
        db, story=story, archive=archive, settings=settings,
        user_content="继续", persist_user_content="继续",
        include_history=False, first_opening=False, stream_fn=fake_stream,
    )
    list(gen)
    assert "不应出现" not in captured["messages"][0]["content"]


def test_tail_prompt_memory_update_constraint():
    from app.prompts.chat_tail import _TAIL_META_PROMPT

    assert "与已有记忆重复则不记" in _TAIL_META_PROMPT
    assert "无新增返回空数组 []" in _TAIL_META_PROMPT
    assert "不得编造" in _TAIL_META_PROMPT
    # 不再授权矛盾纠错
    assert "修正" not in _TAIL_META_PROMPT
    # 记忆区标题改为"已记忆事件"，引导判断重复而非简单罗列
    assert "已记忆事件" in _TAIL_META_PROMPT
