"""Tests for Bug #7 fix: recall rolls back archive state/story/memory via pre_* snapshot.

撤回最后一轮 AI 时，archive.state_data / story_state / memory_log 必须回到该 AI 写入前的旧值。
_persist_exchange 在改 archive 前把旧值快照到 ai_msg.pre_*；delete_last_ai_message 撤回时恢复。
"""

from datetime import datetime

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


def test_recall_rolls_back_archive_state_story_memory():
    """撤回唯一一轮 AI（pre_* 存在）后，archive 三字段回到 last_ai.pre_*。

    显式 created_at 保证 messages desc 顺序为 [ai, user]，使 last_ai_idx+1 命中 user（deleted=2）。
    """
    from app.api.chat_router import delete_last_ai_message

    db = SessionLocal()
    try:
        story = models.Story(title="recall rollback test", world_setting="")
        archive = models.Archive(
            story=story,
            name="rr archive",
            state_data={"hp": 10, "gold": 5},
            story_state={"chapter": "第十章", "progress": 9},
            memory_log=["最近事件"],
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)

        user_msg = models.ChatMessage(
            archive_id=archive.id,
            role="user",
            content="开始",
            state_snapshot={"hp": 100, "gold": 50},
            story_state={"chapter": "第一章", "progress": 1},
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        ai_msg = models.ChatMessage(
            archive_id=archive.id,
            role="assistant",
            content="正文",
            state_snapshot={"hp": 10, "gold": 5},
            story_state={"chapter": "第十章", "progress": 9},
            pre_state_data={"hp": 100, "gold": 50},
            pre_story_state={"chapter": "第一章", "progress": 1},
            pre_memory_log=["初始事件"],
            created_at=datetime(2026, 1, 1, 12, 0, 1),
        )
        db.add_all([user_msg, ai_msg])
        db.commit()

        result = delete_last_ai_message(archive.id, db)
        assert result["deleted"] == 2

        db.refresh(archive)
        assert archive.state_data == {"hp": 100, "gold": 50}
        assert archive.story_state == {"chapter": "第一章", "progress": 1}
        assert archive.memory_log == ["初始事件"]
    finally:
        db.close()


def test_recall_multi_exchange_restores_from_deleted_ai_pre():
    """多轮撤回：撤回最新 AI 后，archive 应回到 last_ai.pre_*（= 更早 AI 写入后的状态 S1），
    而非 last_remaining_ai.pre_*（= S0，会丢失中间轮次）。这是 Bug #7 的关键不变量。

    场景：S0 -(E1)-> S1 -(E2)-> S2。撤回 E2 后 archive 应为 S1 = ai2.pre_*。
    若错误地从 ai1.pre_* 恢复，会得到 S0，丢失 E1 的影响。
    """
    from app.api.chat_router import delete_last_ai_message

    db = SessionLocal()
    try:
        story = models.Story(title="recall multi test", world_setting="")
        archive = models.Archive(
            story=story,
            name="rm archive",
            state_data={"hp": 10, "gold": 5},  # S2
            story_state={"chapter": "第十章", "progress": 9},
            memory_log=["事件0", "事件1", "事件2"],
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)

        user1 = models.ChatMessage(
            archive_id=archive.id,
            role="user",
            content="走",
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        ai1 = models.ChatMessage(
            archive_id=archive.id,
            role="assistant",
            content="第一章正文",
            state_snapshot={"hp": 80, "gold": 40},  # S1
            story_state={"chapter": "第二章", "progress": 2},
            memory_update=["事件1"],
            pre_state_data={"hp": 100, "gold": 50},  # S0
            pre_story_state={"chapter": "第一章", "progress": 1},
            pre_memory_log=["事件0"],
            created_at=datetime(2026, 1, 1, 12, 0, 1),
        )
        user2 = models.ChatMessage(
            archive_id=archive.id,
            role="user",
            content="再走",
            created_at=datetime(2026, 1, 1, 12, 0, 2),
        )
        ai2 = models.ChatMessage(
            archive_id=archive.id,
            role="assistant",
            content="第二章正文",
            state_snapshot={"hp": 10, "gold": 5},  # S2
            story_state={"chapter": "第十章", "progress": 9},
            memory_update=["事件2"],
            pre_state_data={"hp": 80, "gold": 40},  # S1
            pre_story_state={"chapter": "第二章", "progress": 2},
            pre_memory_log=["事件0", "事件1"],
            created_at=datetime(2026, 1, 1, 12, 0, 3),
        )
        db.add_all([user1, ai1, user2, ai2])
        db.commit()

        result = delete_last_ai_message(archive.id, db)
        assert result["deleted"] == 2

        db.refresh(archive)
        # 应恢复到 ai2.pre_*（= S1），而非 ai1.pre_*（= S0）
        assert archive.state_data == {"hp": 80, "gold": 40}
        assert archive.story_state == {"chapter": "第二章", "progress": 2}
        assert archive.memory_log == ["事件0", "事件1"]
    finally:
        db.close()


def test_recall_only_ai_no_pre_snapshot_uses_initial_defaults():
    """老数据（ChatMessage 无 pre_* 快照，pre_*=NULL）撤回唯一一轮 AI 时，
    archive 恢复到初始默认值（state_data={} / story_state={} / memory_log=[]）。"""
    from app.api.chat_router import delete_last_ai_message

    db = SessionLocal()
    try:
        story = models.Story(title="recall initial test", world_setting="")
        archive = models.Archive(
            story=story,
            name="ri archive",
            state_data={"hp": 5},
            story_state={"chapter": "尾章"},
            memory_log=["唯一事件"],
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)

        user_msg = models.ChatMessage(
            archive_id=archive.id,
            role="user",
            content="唯一输入",
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        ai_msg = models.ChatMessage(
            archive_id=archive.id,
            role="assistant",
            content="唯一正文",
            pre_state_data=None,
            pre_story_state=None,
            pre_memory_log=None,
            created_at=datetime(2026, 1, 1, 12, 0, 1),
        )
        db.add_all([user_msg, ai_msg])
        db.commit()

        delete_last_ai_message(archive.id, db)
        db.refresh(archive)
        assert archive.state_data in (None, {})
        assert archive.story_state in (None, {})
        assert archive.memory_log in (None, [])
    finally:
        db.close()


def test_recall_old_data_multi_exchange_fallback_to_remaining_ai_state():
    """老数据（ai2.pre_*=NULL）+ 存在 last_remaining_ai → state/story 从 ai1.state_snapshot/story_state
    精确回滚到 S1；memory_log 保留原值（追加式 FIFO 无法精确逆推减 delta，宁可保留不删错）。"""
    from app.api.chat_router import delete_last_ai_message

    db = SessionLocal()
    try:
        story = models.Story(title="recall old-data multi test", world_setting="")
        archive = models.Archive(
            story=story,
            name="rom archive",
            state_data={"hp": 5, "gold": 1},  # S2 polluted
            story_state={"chapter": "第十章", "progress": 9},
            memory_log=["历史A", "历史B", "历史C", "事件2"],  # 含 ai2 污染
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)

        user1 = models.ChatMessage(
            archive_id=archive.id,
            role="user",
            content="走",
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        ai1 = models.ChatMessage(
            archive_id=archive.id,
            role="assistant",
            content="第一章正文",
            state_snapshot={"hp": 80, "gold": 40},  # S1（fallback 源）
            story_state={"chapter": "第二章", "progress": 2},
            memory_update=["事件1"],
            pre_state_data=None,
            pre_story_state=None,
            pre_memory_log=None,
            created_at=datetime(2026, 1, 1, 12, 0, 1),
        )
        user2 = models.ChatMessage(
            archive_id=archive.id,
            role="user",
            content="再走",
            created_at=datetime(2026, 1, 1, 12, 0, 2),
        )
        ai2 = models.ChatMessage(
            archive_id=archive.id,
            role="assistant",
            content="第二章正文",
            state_snapshot={"hp": 5, "gold": 1},  # S2
            story_state={"chapter": "第十章", "progress": 9},
            memory_update=["事件2"],
            pre_state_data=None,  # 旧数据 → 触发 NULL fallback
            pre_story_state=None,
            pre_memory_log=None,
            created_at=datetime(2026, 1, 1, 12, 0, 3),
        )
        db.add_all([user1, ai1, user2, ai2])
        db.commit()

        delete_last_ai_message(archive.id, db)
        db.refresh(archive)
        # state/story 精确回滚到 ai1 的输出快照（S1）
        assert archive.state_data == {"hp": 80, "gold": 40}
        assert archive.story_state == {"chapter": "第二章", "progress": 2}
        # memory_log 保留原值（Important #1：无法精确逆推）
        assert archive.memory_log == ["历史A", "历史B", "历史C", "事件2"]
    finally:
        db.close()
