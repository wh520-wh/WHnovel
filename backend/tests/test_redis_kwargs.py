"""Regression tests for Bug #8: redis.set must use ttl= not ex=.

The RedisClient.set wrapper signature is `set(key, value, ttl=300)`, not
`set(key, value, ex=...)`. Passing `ex=` raises TypeError at kwarg binding
time (before the wrapper's try/except), crashing every chat call once Redis
is enabled. These tests guard both call sites.
"""
from app.api import chat_storage, chat_models
from app import models
from app.database import SessionLocal


def _make_fake_redis():
    """Return a fake redis module with is_available()=True and a set() that
    raises TypeError if called with the `ex` kwarg."""

    class _FakeRedis:
        def is_available(self):
            return True

        def set(self, *args, **kwargs):
            if "ex" in kwargs:
                raise TypeError(
                    f"redis.set got unexpected keyword argument 'ex': {kwargs}"
                )
            return None

        def get(self, *args, **kwargs):
            return None

        def delete(self, *args, **kwargs):
            return None

    return _FakeRedis()


def test_chat_storage_uses_ttl_not_ex(monkeypatch):
    """Bug #8 regression: _get_story_characters must call redis.set with
    ttl=, not ex= (which RedisClient.set does not accept)."""
    fake = _make_fake_redis()
    monkeypatch.setattr(chat_storage, "get_redis", lambda: fake)

    db = SessionLocal()
    story = None
    try:
        story = models.Story(title="b8 storage test", world_setting="")
        db.add(story)
        db.commit()
        db.refresh(story)
        # Empty characters result still triggers the redis.set branch
        chat_storage._get_story_characters(db, story.id)  # must not raise
    finally:
        if story is not None:
            db.delete(story)
            db.commit()
        db.close()


def test_chat_models_uses_ttl_not_ex(monkeypatch):
    """Bug #8 regression: _get_enabled_models must call redis.set with
    ttl=, not ex= (which RedisClient.set does not accept)."""
    fake = _make_fake_redis()
    monkeypatch.setattr(chat_models, "get_redis", lambda: fake)

    db = SessionLocal()
    model = None
    try:
        model = models.ModelConfig(
            name="b8 model",
            model_id="m",
            api_base_url="https://fake.api",
            api_key="",
            api_mode="openai_chat_completions",
            model_type="chat",
            enabled=1,
            priority=1,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        # _get_enabled_models only caches when models_list is non-empty
        chat_models._get_enabled_models(db)  # must not raise
    finally:
        if model is not None:
            db.delete(model)
            db.commit()
        db.close()
