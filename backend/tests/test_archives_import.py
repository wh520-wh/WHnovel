"""Bug #49 回归：存档导入 payload 须类型校验，损坏数据返 400 而非 500。

根因：import_archive 接收裸 dict，messages 非 list / 项非 dict / story_id 非整数
时直接抛 500，用户看到通用服务器错误而非明确提示；合法导入行为不变。
"""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _first_story_id() -> int:
    resp = client.get("/api/stories")
    resp.raise_for_status()
    return resp.json()[0]["id"]


def test_import_rejects_non_list_messages():
    # Bug #49：messages 非 list 应返 400 而非 500
    story_id = _first_story_id()
    resp = client.post(
        "/api/archives/import",
        json={"archive": {"story_id": story_id, "name": "测试"}, "messages": "not a list"},
    )
    assert resp.status_code == 400
    assert "messages" in resp.json()["detail"]


def test_import_rejects_non_dict_message_item():
    story_id = _first_story_id()
    resp = client.post(
        "/api/archives/import",
        json={"archive": {"story_id": story_id}, "messages": ["not a dict"]},
    )
    assert resp.status_code == 400


def test_import_rejects_non_int_story_id():
    resp = client.post(
        "/api/archives/import",
        json={"archive": {"story_id": "abc"}, "messages": []},
    )
    assert resp.status_code == 400


def test_import_rejects_missing_archive():
    resp = client.post("/api/archives/import", json={"messages": []})
    assert resp.status_code == 400


def test_import_valid_payload_still_works():
    # 合法导入不被校验破坏：返回 200 + id
    story_id = _first_story_id()
    resp = client.post(
        "/api/archives/import",
        json={
            "archive": {"story_id": story_id, "name": "合法导入测试"},
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好啊"},
            ],
        },
    )
    assert resp.status_code == 200
    assert "id" in resp.json()
