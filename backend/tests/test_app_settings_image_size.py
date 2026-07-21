"""Bug #18 回归测试：image_size 写入校验 + 读取侧兜底。

- 写入侧：PUT /api/admin/app-settings 对非法 image_size 返回 422，不再落库；
- 读取侧：resolve_image_size 对存量脏数据（空串/非法值/None）回退 "2K"。
"""

from app.api.image_generation import resolve_image_size
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_update_app_settings_rejects_invalid_image_size():
    resp = client.put("/api/admin/app-settings", json={"image_size": "5K"})
    assert resp.status_code == 422

    resp = client.put("/api/admin/app-settings", json={"image_size": ""})
    assert resp.status_code == 422

    # 非法值不应落库：当前值仍是合法尺寸
    got = client.get("/api/admin/app-settings")
    got.raise_for_status()
    assert got.json()["image_size"] in ("1K", "2K", "3K")


def test_update_app_settings_accepts_valid_image_size():
    resp = client.put("/api/admin/app-settings", json={"image_size": "3K"})
    resp.raise_for_status()
    assert resp.json()["image_size"] == "3K"

    resp = client.put("/api/admin/app-settings", json={"image_size": "2K"})
    resp.raise_for_status()
    assert resp.json()["image_size"] == "2K"


def test_resolve_image_size_falls_back_for_dirty_values():
    assert resolve_image_size(None) == "2K"
    assert resolve_image_size("") == "2K"
    assert resolve_image_size("5K") == "2K"
    assert resolve_image_size("1K") == "1K"
    assert resolve_image_size("3K") == "3K"
