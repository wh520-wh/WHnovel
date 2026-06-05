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
