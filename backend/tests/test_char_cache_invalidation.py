"""Bug #23 核查回归测试：角色缓存失效防护已存在，本测试锁定该行为。

核查结论：角色增/改/删端点（stories.py:121/136/148）自首个公开提交起
即调用 _invalidate_char_cache 删除 CHAR_CACHE_KEY，#23 所述"无失效逻辑"
不成立。本测试锁定该防护，防止未来回归。
"""

from app import models
from app.api import chat_storage, stories
from app.database import SessionLocal
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class _DictFakeRedis:
    def __init__(self):
        self.store = {}

    def is_available(self):
        return True

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=300):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)


def _setup_fake_redis(monkeypatch):
    fake = _DictFakeRedis()
    monkeypatch.setattr(chat_storage, "get_redis", lambda: fake)
    monkeypatch.setattr(stories, "get_redis", lambda: fake)
    return fake


def test_update_character_invalidates_char_cache(monkeypatch):
    fake = _setup_fake_redis(monkeypatch)
    db = SessionLocal()
    story = character = None
    try:
        story = models.Story(title="b23 cache test")
        db.add(story)
        db.commit()
        db.refresh(story)
        character = models.Character(story_id=story.id, name="旧名字")
        db.add(character)
        db.commit()
        db.refresh(character)

        cache_key = stories.CHAR_CACHE_KEY.format(story_id=story.id)
        # 预热缓存
        assert chat_storage._get_story_characters(db, story.id)[0]["name"] == "旧名字"
        assert cache_key in fake.store

        resp = client.put(
            f"/api/stories/characters/{character.id}",
            json={"name": "新名字", "personality": "", "background": "", "avatar": ""},
        )
        resp.raise_for_status()

        assert cache_key not in fake.store  # 失效已发生
        db.expire_all()
        assert chat_storage._get_story_characters(db, story.id)[0]["name"] == "新名字"
    finally:
        if character is not None:
            db.delete(character)
        if story is not None:
            db.delete(story)
        db.commit()
        db.close()


def test_delete_character_invalidates_char_cache(monkeypatch):
    fake = _setup_fake_redis(monkeypatch)
    db = SessionLocal()
    story = character = None
    try:
        story = models.Story(title="b23 cache test 2")
        db.add(story)
        db.commit()
        db.refresh(story)
        character = models.Character(story_id=story.id, name="将被删除")
        db.add(character)
        db.commit()
        db.refresh(character)

        cache_key = stories.CHAR_CACHE_KEY.format(story_id=story.id)
        chat_storage._get_story_characters(db, story.id)
        assert cache_key in fake.store

        resp = client.delete(f"/api/stories/characters/{character.id}")
        resp.raise_for_status()
        assert cache_key not in fake.store
        character = None  # 已被端点删除
    finally:
        if character is not None:
            db.delete(character)
        if story is not None:
            db.delete(story)
        db.commit()
        db.close()
