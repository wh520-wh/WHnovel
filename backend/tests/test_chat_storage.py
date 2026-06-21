"""Tests for chat_storage utilities."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from app import models, schemas
from app.api.chat_storage import (
    _count_rounds_without_plot_label,
    _get_or_create_settings,
    _persist_exchange,
)
from app.database import SessionLocal
from sqlalchemy.exc import IntegrityError


def test_get_or_create_settings_existing_record_no_extra_commit():
    """已有完整记录时，不应再触发无意义的 db.commit()。"""
    db = MagicMock()
    existing = MagicMock()
    existing.backup_model_ids = []
    existing.auto_generate_options = 1
    db.query.return_value.first.return_value = existing

    result = _get_or_create_settings(db)

    assert result == existing
    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_get_or_create_settings_new_record_commits():
    """记录不存在时，应创建并 commit 一次。"""
    db = MagicMock()
    db.query.return_value.first.return_value = None

    result = _get_or_create_settings(db)

    assert result is not None
    assert db.commit.call_count == 1
    assert db.refresh.call_count == 1


def test_get_or_create_settings_existing_null_fields_commits_once():
    """已有记录但默认字段为 None 时，应只 commit 一次。"""
    db = MagicMock()
    existing = MagicMock()
    existing.backup_model_ids = None
    existing.auto_generate_options = None
    db.query.return_value.first.return_value = existing

    result = _get_or_create_settings(db)

    assert result == existing
    assert db.commit.call_count == 1
    assert db.refresh.call_count == 1


def test_persist_exchange_rollback_on_integrity_error():
    """db.commit 抛出 IntegrityError 时，应 rollback 并重新抛出异常。"""
    db = MagicMock()
    db.commit.side_effect = IntegrityError("test", {}, Exception("boom"))

    archive = MagicMock()
    archive.id = 1
    archive.state_data = {}
    archive.story_state = {"chapter": "第一章", "progress": 0}
    archive.memory_log = []

    validated = schemas.ChatResponse(
        reply_text="hello",
        scene="",
        character_state=schemas.CharacterState(),
        story_state=schemas.StoryState(),
        options=[],
        memory_update=[],
    )

    with pytest.raises(IntegrityError):
        _persist_exchange(db, archive=archive, user_content="hi", validated=validated)

    db.rollback.assert_called_once()


def test_count_rounds_without_plot_label_counts_messages_after_latest_label():
    """Only assistant messages after the latest non-empty plot_label should count."""
    db = SessionLocal()
    story = models.Story(title="plot count test")
    archive = models.Archive(story=story, name="plot count archive")
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    archive.messages = [
        models.ChatMessage(
            role="assistant", content="labeled", plot_label="破局", created_at=base_time
        ),
        models.ChatMessage(
            role="assistant",
            content="plain 1",
            plot_label=None,
            created_at=base_time + timedelta(minutes=1),
        ),
        models.ChatMessage(
            role="user", content="user", created_at=base_time + timedelta(minutes=2)
        ),
        models.ChatMessage(
            role="assistant",
            content="plain 2",
            plot_label="",
            created_at=base_time + timedelta(minutes=3),
        ),
    ]
    db.add(story)
    db.commit()
    try:
        assert _count_rounds_without_plot_label(db, archive.id) == 2
    finally:
        db.delete(story)
        db.commit()
        db.close()


def test_query_dialogue_history_excludes_draft_broadcast_image_and_empty():
    """_query_dialogue_history 只返回正常对话消息，排除 draft/broadcast/空内容。"""
    from app.api.chat_storage import _query_dialogue_history

    db = SessionLocal()
    story = models.Story(title="history filter test")
    archive = models.Archive(story=story, name="filter archive")
    db.add(archive)
    db.commit()
    db.refresh(archive)

    base = datetime(2026, 1, 1, 12, 0, 0)
    # 正常对话
    db.add_all([
        models.ChatMessage(archive_id=archive.id, role="user", content="u1", created_at=base),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="a1", created_at=base + timedelta(seconds=1), is_draft=0),
        models.ChatMessage(archive_id=archive.id, role="user", content="u2", created_at=base + timedelta(seconds=2)),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="a2", created_at=base + timedelta(seconds=3), is_draft=0),
    ])
    # 污染消息（都应被排除）
    db.add_all([
        models.ChatMessage(archive_id=archive.id, role="assistant", content="draft残文", created_at=base + timedelta(seconds=4), is_draft=1),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="属性 | 属性值", created_at=base + timedelta(seconds=5), is_state_broadcast=1),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="", created_at=base + timedelta(seconds=6), is_draft=0, is_state_broadcast=0, image_url="x.png"),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="", created_at=base + timedelta(seconds=7), is_draft=0, is_state_broadcast=0),
    ])
    db.commit()

    result = _query_dialogue_history(db, archive.id, 100)
    contents = [m.content for m in result]
    assert contents == ["u1", "a1", "u2", "a2"]  # 最旧在前，仅正常对话
    assert "draft残文" not in contents
    assert "属性 | 属性值" not in contents

    # limit 生效：取最近 N 条正常对话，返回时最旧在前
    result_limited = _query_dialogue_history(db, archive.id, 2)
    assert [m.content for m in result_limited] == ["u2", "a2"]


def test_build_messages_excludes_non_dialogue_history():
    """_build_messages 构建的 history 不含 draft/broadcast/图片消息。"""
    from app.api.chat_storage import _build_messages
    from app.api.ai_contracts import TASK_CHAT_RESPONSE, get_contract_output_rule

    db = SessionLocal()
    story = models.Story(title="bm test", world_setting="")
    archive = models.Archive(story=story, name="bm archive")
    db.add(archive)
    db.commit()
    db.refresh(archive)

    base = datetime(2026, 1, 1, 12, 0, 0)
    db.add_all([
        models.ChatMessage(archive_id=archive.id, role="user", content="hello", created_at=base),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="world", created_at=base + timedelta(seconds=1), is_draft=0),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="broadcast text", created_at=base + timedelta(seconds=2), is_state_broadcast=1),
    ])
    db.commit()

    settings = _get_or_create_settings(db)
    messages = _build_messages(
        story, archive, "next input", settings, db,
        include_history=True,
        output_rule_prompt=get_contract_output_rule(TASK_CHAT_RESPONSE),
    )
    # messages[0]=system, 之后是 history(user/assistant) + 末尾 user
    bodies = [m["content"] for m in messages[1:]]
    assert "broadcast text" not in bodies
    assert "hello" in bodies and "world" in bodies


def test_count_rounds_excludes_draft_broadcast_image():
    """_count_rounds 不计 draft/broadcast/图片这类无 plot_label 的 assistant。"""
    db = SessionLocal()
    story = models.Story(title="count filter test")
    archive = models.Archive(story=story, name="cf archive")
    db.add(archive)
    db.commit()
    db.refresh(archive)

    base = datetime(2026, 1, 1, 12, 0, 0)
    # 一条带 label 的 + 多条无 label 的污染消息
    db.add_all([
        models.ChatMessage(archive_id=archive.id, role="assistant", content="labeled", created_at=base, is_draft=0, plot_label="起"),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="draft", created_at=base + timedelta(seconds=1), is_draft=1),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="broadcast", created_at=base + timedelta(seconds=2), is_state_broadcast=1),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="", created_at=base + timedelta(seconds=3), is_draft=0, image_url="x.png"),
        models.ChatMessage(archive_id=archive.id, role="assistant", content="real no-label", created_at=base + timedelta(seconds=4), is_draft=0),
    ])
    db.commit()

    # labeled 之后只有 1 条真正无 label 的正常 assistant
    assert _count_rounds_without_plot_label(db, archive.id) == 1
