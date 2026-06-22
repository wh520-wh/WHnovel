"""Tests for Bug #7 fix: recall rolls back archive state/story/memory via pre_* snapshot.

撤回最后一轮 AI 时，archive.state_data / story_state / memory_log 必须回到该 AI 写入前的旧值。
_persist_exchange 在改 archive 前把旧值快照到 ai_msg.pre_*；delete_last_ai_message 撤回时恢复。
"""

from app import models, schemas
from app.api.chat_storage import _persist_exchange
from app.database import SessionLocal


def test_persist_exchange_stores_pre_snapshots_on_ai_message():
    """_persist_exchange must snapshot archive 3 fields BEFORE overwriting, onto ai_msg.pre_*."""
    db = SessionLocal()
    try:
        story = models.Story(title="pre-snap test", world_setting="")
        archive = models.Archive(
            story=story,
            name="ps archive",
            state_data={"health": 100, "gold": 50},
            story_state={"chapter": "第二章", "progress": 4},
            memory_log=["获得宝剑"],
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)

        validated = schemas.ChatResponse(
            reply_text="正文",
            scene="",
            character_state=schemas.CharacterState(health=80, extra={"gold": 60}),
            story_state=schemas.StoryState(chapter="第三章", progress=5),
            memory_update=["获得新武器"],
        )
        _persist_exchange(db, archive=archive, user_content="继续", validated=validated)

        ai_msg = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.archive_id == archive.id,
                models.ChatMessage.role == "assistant",
            )
            .order_by(models.ChatMessage.id.desc())
            .first()
        )
        assert ai_msg is not None
        assert ai_msg.pre_state_data == {"health": 100, "gold": 50}
        assert ai_msg.pre_story_state == {"chapter": "第二章", "progress": 4}
        assert ai_msg.pre_memory_log == ["获得宝剑"]
    finally:
        db.close()


def test_persist_exchange_no_prior_archive_uses_defaults():
    """archive 初始值（state_data={} / story_state={} / memory_log=[]）应被快照为空值。"""
    db = SessionLocal()
    try:
        story = models.Story(title="initial pre-snap test", world_setting="")
        archive = models.Archive(story=story, name="init archive")
        db.add(archive)
        db.commit()
        db.refresh(archive)

        validated = schemas.ChatResponse(
            reply_text="正文",
            scene="",
            character_state=schemas.CharacterState(),
            story_state=schemas.StoryState(),
            memory_update=["第一件事"],
        )
        _persist_exchange(db, archive=archive, user_content="开始", validated=validated)

        ai_msg = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.archive_id == archive.id,
                models.ChatMessage.role == "assistant",
            )
            .order_by(models.ChatMessage.id.desc())
            .first()
        )
        assert ai_msg is not None
        assert ai_msg.pre_state_data in (None, {})
        assert ai_msg.pre_story_state in (None, {})
        assert ai_msg.pre_memory_log in (None, [])
    finally:
        db.close()
