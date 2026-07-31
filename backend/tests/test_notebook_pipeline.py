"""Tests for notebook schema migration and model fields.

Notebook pipeline tests: contract validation, tail messages, persistence.
"""
import sqlite3
from unittest.mock import MagicMock

from app import models, schemas
from app.api.ai_contracts import (
    ChatResponseContract,
    NotebookBootstrapContract,
)
from app.api.chat_router import _delete_last_ai_message
from app.api.chat_storage import _build_tail_messages, _persist_exchange
from app.main import app
from app.migrations import _migrate_to_v29
from fastapi.testclient import TestClient


def test_v29_adds_notebook_columns(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("CREATE TABLE archives (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE chat_messages (id INTEGER PRIMARY KEY)")
    conn.execute(
        "CREATE TABLE schema_meta (id INTEGER PRIMARY KEY CHECK (id=1), version INTEGER NOT NULL DEFAULT 0, updated_at TEXT)"
    )
    _migrate_to_v29(conn)
    cols_a = {r[1] for r in conn.execute("PRAGMA table_info(archives)").fetchall()}
    cols_m = {r[1] for r in conn.execute("PRAGMA table_info(chat_messages)").fetchall()}
    assert "notebook" in cols_a
    assert "pre_notebook" in cols_m
    # 幂等：再跑一遍不报错
    _migrate_to_v29(conn)
    conn.close()


def test_bootstrap_contract_accepts_three_lines():
    model = NotebookBootstrapContract(
        world_line=["魔教攻入皇城"],
        character_line=["主角获得玄铁剑"],
        relationship_line=["师徒反目"],
    )
    assert model.world_line == ["魔教攻入皇城"]


def test_bootstrap_contract_defaults_empty():
    model = NotebookBootstrapContract()
    assert model.world_line == []
    assert model.character_line == []
    assert model.relationship_line == []


def test_contract_accepts_notebook_update():
    payload = {
        "reply_text": "正文",
        "scene": "城外",
        "character_state": {"emotion": "平静", "fatigue": 10, "mood": "沉稳"},
        "story_state": {"chapter": "第一章", "progress": 5},
        "memory_update": [],
        "plot_label": "",
        "highlight_terms": [],
        "notebook_update": {
            "add_world": ["魔教攻入皇城"],
            "close_character": ["C2"],
        },
    }
    model = ChatResponseContract(**payload)
    assert model.notebook_update.add_world == ["魔教攻入皇城"]
    assert model.notebook_update.close_character == ["C2"]


def test_contract_notebook_update_defaults_empty():
    payload = {
        "reply_text": "正文",
        "scene": "城外",
        "character_state": {"emotion": "平静", "fatigue": 10, "mood": "沉稳"},
        "story_state": {"chapter": "第一章", "progress": 5},
    }
    model = ChatResponseContract(**payload)
    dumped = model.notebook_update.model_dump()
    assert all(dumped[k] == [] for k in ("add_world", "add_character", "add_relationship"))
    assert all(dumped[k] == [] for k in ("close_world", "close_character", "close_relationship"))


def test_to_public_schema_passes_notebook_update():
    """核心链路保护：契约→公开 schema 的转换必须透传 notebook_update（否则持久化永不生效）。"""
    from app.api.ai_contracts import TASK_CHAT_RESPONSE, to_public_schema

    contract = ChatResponseContract(
        reply_text="正文",
        scene="城外",
        character_state={"emotion": "平静", "fatigue": 10, "mood": "沉稳"},
        story_state={"chapter": "第一章", "progress": 5},
        notebook_update={"add_world": ["魔教攻入皇城"]},
    )
    schema = to_public_schema(TASK_CHAT_RESPONSE, contract)
    assert schema.notebook_update["add_world"] == ["魔教攻入皇城"]


def test_tail_messages_include_prev_notebook():
    nb = {
        "world_line": [{"text": "魔教攻入皇城", "status": "active"}],
        "character_line": [],
        "relationship_line": [],
    }
    msgs = _build_tail_messages("正文", {}, {"chapter": "第一章", "progress": 0}, [], nb)
    user_content = msgs[1]["content"]
    assert "[W1] 魔教攻入皇城" in user_content
    assert "notebook_update" in user_content


def _make_validated():
    contract = ChatResponseContract(
        reply_text="正文",
        scene="城外",
        character_state={"emotion": "平静", "fatigue": 10, "mood": "沉稳"},
        story_state={"chapter": "第一章", "progress": 5},
        memory_update=["主角进入皇城"],
        plot_label="进入皇城",
        highlight_terms=["皇城"],
        notebook_update={
            "add_world": ["魔教攻入皇城"],
            "close_character": ["C1"],
        },
    )
    return schemas.ChatResponse(**contract.model_dump())


def test_persist_exchange_applies_notebook_update():
    db = MagicMock()
    archive = MagicMock()
    archive.id = 1
    archive.notebook = {
        "world_line": [],
        "character_line": [{"text": "主角中毒", "status": "active"}],
        "relationship_line": [],
    }
    archive.memory_log = []
    archive.story_state = {"chapter": "第一章", "progress": 0}
    archive.state_data = {}
    archive.updated_at = None
    archive.first_message = ""
    validated = _make_validated()

    _persist_exchange(
        db, archive=archive, user_content="前进", validated=validated
    )

    # notebook 被应用：add_world 追加、close_character 按编号关闭
    assert archive.notebook["world_line"] == [
        {"text": "魔教攻入皇城", "status": "active"}
    ]
    assert archive.notebook["character_line"][0]["status"] == "closed"
    # pre_notebook 快照写入 ai_msg（撤回回滚用）——注意 _persist_exchange 先 add user_msg 再 add ai_msg，
    # 必须按 role 过滤取 ai_msg（ChatMessage 会被 add 两次，user_msg 无 pre_notebook）
    ai_msgs = [
        a.args[0]
        for a in db.add.call_args_list
        if isinstance(a.args[0], models.ChatMessage)
    ]
    ai = next(m for m in ai_msgs if m.role == "assistant")
    assert ai.pre_notebook["character_line"][0]["status"] == "active"


def test_recall_rolls_back_notebook():
    db = MagicMock()
    archive = MagicMock()
    archive.id = 1

    nb_before = {"world_line": [], "character_line": [], "relationship_line": []}
    ai_msg = MagicMock()
    ai_msg.role = "assistant"
    ai_msg.story_node = None
    ai_msg.pre_state_data = {}
    ai_msg.pre_story_state = {"chapter": "第一章", "progress": 1}
    ai_msg.pre_memory_log = []
    ai_msg.pre_notebook = nb_before

    user_msg = MagicMock()
    user_msg.role = "user"

    # _delete_last_ai_message 查询链：db.query(...).filter(...).order_by(...).all()（chat_router.py:523-528）
    # 两条查询共用 db.query().filter() 的 MagicMock：archive 走 with_for_update().first()，
    # messages 走 order_by().all()（chat_router.py:517-528）
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
        archive
    )
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        user_msg,
        ai_msg,
    ]
    db.delete = MagicMock()

    _delete_last_ai_message(db, archive.id)

    assert archive.notebook == nb_before


client = TestClient(app)


def _create_exam_archive() -> int:
    """建测试存档（依赖 seed 数据中的 story_id=1；若测试库无 seed 则先建故事）。"""
    payload = {
        "story_id": 1,
        "name": "笔记本测试存档",
        "story_state": {"chapter": "第一章", "progress": 0},
        "memory_log": [],
        "notebook": {
            "world_line": [{"text": "魔教攻入皇城", "status": "active"}],
            "character_line": [],
            "relationship_line": [],
        },
    }
    resp = client.post("/api/archives", json=payload)
    if resp.status_code == 404:
        # seed 缺失时先建最小故事，换 story_id 后复用同一 payload 重试（保证 notebook 也被持久化）
        story = client.post(
            "/api/stories",
            json={"title": "笔记本测试故事", "description": "", "category": "其他", "tags": []},
        )
        assert story.status_code == 200, story.text
        payload["story_id"] = story.json()["id"]
        resp = client.post("/api/archives", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_export_includes_notebook():
    archive_id = _create_exam_archive()
    try:
        resp = client.get(f"/api/archives/{archive_id}/export")
        assert resp.status_code == 200
        nb = resp.json()["archive"]["notebook"]
        assert nb["world_line"][0]["text"] == "魔教攻入皇城"
    finally:
        client.delete(f"/api/archives/{archive_id}")


def test_import_accepts_notebook_roundtrip():
    resp = client.post(
        "/api/archives/import",
        json={
            "archive": {
                "story_id": 1,
                "name": "导入笔记本存档",
                "story_state": {"chapter": "第一章", "progress": 0},
                "notebook": {
                    "world_line": [{"text": "魔教攻入皇城", "status": "active"}],
                    "character_line": [],
                    "relationship_line": [],
                },
            },
            "messages": [],
        },
    )
    assert resp.status_code == 200, resp.text
    archive_id = resp.json()["id"]
    try:
        resp2 = client.get(f"/api/archives/{archive_id}")
        assert resp2.json()["notebook"]["world_line"][0]["text"] == "魔教攻入皇城"
    finally:
        client.delete(f"/api/archives/{archive_id}")


def test_import_notebook_garbage_ignored():
    resp = client.post(
        "/api/archives/import",
        json={
            "archive": {"story_id": 1, "notebook": "garbage-string", "name": "坏笔记本"},
            "messages": [],
        },
    )
    # Bug #49 风格：不 500（校验失败也接受 400/404，但绝不能 500）
    assert resp.status_code != 500
    # 若校验通过创建了存档，try/finally 清理避免测试残留
    if resp.status_code == 200:
        archive_id = resp.json()["id"]
        try:
            assert client.get(f"/api/archives/{archive_id}").status_code == 200
        finally:
            client.delete(f"/api/archives/{archive_id}")
