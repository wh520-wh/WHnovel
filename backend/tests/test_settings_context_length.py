"""Bug #17 回归测试：context_length 无上下界。

- 写入侧：PUT /api/settings 钳制到 [1, 200]；
- 读取侧：_query_dialogue_history 对越界 limit 钳制（防存量脏数据把全量历史塞进 prompt）。
"""

from app import models
from app.api.chat_storage import _query_dialogue_history
from app.database import SessionLocal
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_update_settings_clamps_context_length_to_bounds():
    resp = client.put("/api/settings", json={"context_length": -5})
    resp.raise_for_status()
    assert resp.json()["context_length"] == 1

    resp = client.put("/api/settings", json={"context_length": 99999})
    resp.raise_for_status()
    assert resp.json()["context_length"] == 200

    resp = client.put("/api/settings", json={"context_length": 18})
    resp.raise_for_status()
    assert resp.json()["context_length"] == 18


def test_query_dialogue_history_clamps_out_of_range_limit():
    db = SessionLocal()
    story = models.Story(title="context length clamp test")
    archive = models.Archive(story=story, name="clamp archive")
    db.add(archive)
    db.commit()
    db.refresh(archive)
    db.add_all(
        [models.ChatMessage(archive_id=archive.id, role="user", content=f"u{i}") for i in range(3)]
    )
    db.commit()

    try:
        # 负数 limit：SQLite 的 .limit(-1) 等同全量；钳制后只取最近 1 条
        result = _query_dialogue_history(db, archive.id, -1)
        assert [m.content for m in result] == ["u2"]

        # 极大值 limit：钳制到 200，3 条消息正常全返回、不报错
        result = _query_dialogue_history(db, archive.id, 10**9)
        assert [m.content for m in result] == ["u0", "u1", "u2"]
    finally:
        db.delete(archive)
        db.delete(story)
        db.commit()
        db.close()
