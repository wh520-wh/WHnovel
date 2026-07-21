"""Bug #15 回归测试：模型缓存命中分支必须过滤 enabled。

缓存命中分支只按 id 列表查库、不带 enabled==1 过滤，导致已禁用模型
在缓存 TTL（300s）内仍被选为对话候选。
"""

import json

from app import models
from app.api import chat_models
from app.database import SessionLocal


def _make_fake_redis(cached_ids):
    class _FakeRedis:
        def is_available(self):
            return True

        def get(self, key):
            if key == chat_models.MODEL_CACHE_KEY:
                return json.dumps(cached_ids)
            return None

        def set(self, *args, **kwargs):
            return None

        def delete(self, *args, **kwargs):
            return None

    return _FakeRedis()


def test_cache_hit_branch_excludes_disabled_models(monkeypatch):
    db = SessionLocal()
    enabled_model = None
    disabled_model = None
    try:
        enabled_model = models.ModelConfig(
            name="b15 enabled",
            model_id="m-on",
            api_base_url="https://fake.api",
            api_key="",
            model_type="chat",
            enabled=1,
            priority=1,
        )
        disabled_model = models.ModelConfig(
            name="b15 disabled",
            model_id="m-off",
            api_base_url="https://fake.api",
            api_key="",
            model_type="chat",
            enabled=0,
            priority=2,
        )
        db.add_all([enabled_model, disabled_model])
        db.commit()
        db.refresh(enabled_model)
        db.refresh(disabled_model)

        # 模拟缓存里仍残留已禁用模型的 id（禁用发生在缓存写入之后）
        fake = _make_fake_redis([enabled_model.id, disabled_model.id])
        monkeypatch.setattr(chat_models, "get_redis", lambda: fake)

        result = chat_models._get_enabled_models(db)
        assert [m.id for m in result] == [enabled_model.id]
    finally:
        for m in (enabled_model, disabled_model):
            if m is not None:
                db.delete(m)
        db.commit()
        db.close()
