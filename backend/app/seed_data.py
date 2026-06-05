"""预置示例数据"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from . import models
from .app_settings_service import ensure_app_settings
from .database import Base, SessionLocal, engine
from .prompts.seed import SEED_STORY_SYSTEM_PROMPTS

_SEED_PROMPT_MAP = {s["title"]: s["system_prompt"] for s in SEED_STORY_SYSTEM_PROMPTS}

_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR = Path(os.environ.get("WHAINOEL_DATA_DIR") or _DEFAULT_DATA_DIR).resolve()
SEED_FLAG_FILE = DATA_DIR / ".seed_done"


def _read_seed_flag() -> dict | None:
    """Read seed flag file. Returns None if missing or invalid."""
    if not SEED_FLAG_FILE.exists():
        return None
    try:
        return json.loads(SEED_FLAG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_seed_flag(story_count: int) -> None:
    """Write seed flag file with current timestamp and story count."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEED_FLAG_FILE.write_text(
        json.dumps(
            {"timestamp": datetime.now().isoformat(), "story_count": story_count},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


JUJUTSU_WORLD_TEXT = "现代咒术世界观。"


SAMPLE_STORIES = [
    {
        "title": "樱花树下的约定",
        "cover_image": "https://picsum.photos/seed/love1/400/240",
        "description": "你与青梅竹马在校园春日里重逢，一段细腻又克制的情感故事即将展开。",
        "tags": ["恋爱", "校园", "治愈"],
        "category": "恋爱",
        "world_setting": "现代校园，平静日常中藏着微妙情绪与成长命题。四月樱花盛开，阳光温暖而柔软，教室里粉笔沙沙作响，操场上篮球撞击地面的声音随风飘远。这是关于青春、悸动与选择的故事。",
        "system_prompt": _SEED_PROMPT_MAP["樱花树下的约定"],
        "state_config": [
            {
                "key": "好感度",
                "label": "好感度",
                "type": "number",
                "default": 30,
                "max": 100,
                "min": 0,
            },
            {
                "key": "亲密度",
                "label": "亲密度",
                "type": "number",
                "default": 10,
                "max": 100,
                "min": 0,
            },
            {
                "key": "信任值",
                "label": "信任值",
                "type": "number",
                "default": 50,
                "max": 100,
                "min": 0,
            },
            {"key": "scene", "label": "当前场景", "type": "text", "default": "教学楼走廊"},
        ],
        "characters": [
            {
                "name": "小樱",
                "personality": "温柔、细腻、偶尔嘴硬",
                "background": "你多年未见的青梅竹马，喜欢音乐和散步。",
                "avatar": "",
            }
        ],
    },
    {
        "title": "失落遗迹的探险者",
        "cover_image": "https://picsum.photos/seed/adv1/400/240",
        "description": "你将深入未知遗迹，穿过机关与谎言，寻找被尘封的真相。",
        "tags": ["冒险", "奇幻", "解谜"],
        "category": "冒险",
        "world_setting": "古老文明遗迹遍布大陆，传说中的核心遗物能够改写命运。遗迹中布满机关陷阱、神秘符文与未知生物。探险者需要谨慎行事，资源有限，每一次选择都可能关乎生死。",
        "system_prompt": _SEED_PROMPT_MAP["失落遗迹的探险者"],
        "state_config": [
            {
                "key": "HP",
                "label": "生命值",
                "type": "number",
                "default": 100,
                "max": 100,
                "min": 0,
            },
            {"key": "MP", "label": "魔力值", "type": "number", "default": 50, "max": 100, "min": 0},
            {
                "key": "金币",
                "label": "金币",
                "type": "number",
                "default": 100,
                "max": 9999,
                "min": 0,
            },
            {"key": "scene", "label": "当前位置", "type": "text", "default": "遗迹入口"},
        ],
        "characters": [
            {
                "name": "向导",
                "personality": "谨慎、务实、经验老到",
                "background": "熟悉遗迹周边地形，曾多次协助探险队。",
                "avatar": "",
            }
        ],
    },
    {
        "title": "咒术世界观",
        "cover_image": "https://picsum.photos/seed/jujutsu/400/240",
        "description": "在诅咒与咒术交错的都市中，直面危险，守护与你并肩的同伴。",
        "tags": ["咒术", "热血", "战斗", "成长"],
        "category": "冒险",
        "world_setting": JUJUTSU_WORLD_TEXT,
        "system_prompt": _SEED_PROMPT_MAP["咒术世界观"],
        "state_config": [
            {"key": "咒力", "label": "咒力", "type": "number", "default": 80, "max": 100, "min": 0},
            {"key": "精神", "label": "精神", "type": "number", "default": 70, "max": 100, "min": 0},
            {"key": "scene", "label": "当前场景", "type": "text", "default": "东京都市区"},
        ],
        "characters": [
            {
                "name": "夜行导师",
                "personality": "冷静、严谨、实战派",
                "background": "负责引导新咒术师执行高风险任务。",
                "avatar": "",
            }
        ],
    },
    {
        "title": "庄园谋杀案",
        "cover_image": "https://picsum.photos/seed/mystery1/400/240",
        "description": "一场风雨夜聚会后，庄园主人离奇身亡，你需要在谎言中拼凑真相。",
        "tags": ["悬疑", "推理", "本格"],
        "category": "悬疑",
        "world_setting": "封闭庄园环境，所有来客都有动机与秘密。暴风雨夜，古老庄园，闪烁的烛光中隐藏着真相。每个人都有不在场证明，每个人都有嫌疑。你是唯一的局外人。",
        "system_prompt": _SEED_PROMPT_MAP["庄园谋杀案"],
        "state_config": [
            {
                "key": "线索数",
                "label": "已收集线索",
                "type": "number",
                "default": 0,
                "max": 20,
                "min": 0,
            },
            {
                "key": "信任度",
                "label": "嫌疑人信任度",
                "type": "number",
                "default": 50,
                "max": 100,
                "min": 0,
            },
            {
                "key": "真相进度",
                "label": "真相接近度",
                "type": "number",
                "default": 0,
                "max": 100,
                "min": 0,
            },
            {"key": "scene", "label": "当前位置", "type": "text", "default": "庄园大厅"},
        ],
        "characters": [
            {
                "name": "管家詹姆斯",
                "personality": "沉稳、克制、表情管理极强",
                "background": "在庄园服务多年，熟悉每一条隐秘通道。",
                "avatar": "",
            }
        ],
    },
    {
        "title": "仙途问鼎",
        "cover_image": "https://picsum.photos/seed/xianxia/400/240",
        "description": "踏入修仙之路，炼气、筑基、金丹...一步步迈向长生大道。",
        "tags": ["修仙", "玄幻", "境界", "修炼"],
        "category": "修仙",
        "world_setting": "修仙界分为炼气、筑基、金丹、元婴、化神等境界，灵根决定修仙资质。天地灵气分布不均，洞天福地乃必争之物。宗门林立，弱肉强食，机缘与危机并存。",
        "system_prompt": _SEED_PROMPT_MAP["仙途问鼎"],
        "state_config": [
            {"key": "境界", "label": "境界", "type": "text", "default": "炼气期"},
            {"key": "灵气", "label": "灵气", "type": "number", "default": 50, "max": 100, "min": 0},
            {"key": "灵根资质", "label": "灵根资质", "type": "text", "default": "中等"},
            {"key": "scene", "label": "当前位置", "type": "text", "default": "山门"},
        ],
        "characters": [
            {
                "name": "掌门",
                "personality": "威严、深不可测、惜才",
                "background": "一派掌门，修为深不可测，轻易不问世事。",
                "avatar": "",
            }
        ],
    },
    {
        "title": "星际漂泊者",
        "cover_image": "https://picsum.photos/seed/scifi/400/240",
        "description": "驾驶飞船穿越星海，在不同星球间探索、交易、生存。",
        "tags": ["科幻", "星际", "探索", "飞船"],
        "category": "科幻",
        "world_setting": "人类已掌握超光速航行，星际联邦与独立星球并存。飞船是主要交通工具，燃料、补给、航道信息是稀缺资源。太空站是补给枢纽，星际海盗是常见威胁，机遇与危险并存于每颗未知星球。",
        "system_prompt": _SEED_PROMPT_MAP["星际漂泊者"],
        "state_config": [
            {
                "key": "星币",
                "label": "星币",
                "type": "number",
                "default": 1000,
                "max": 99999,
                "min": 0,
            },
            {"key": "燃料", "label": "燃料", "type": "number", "default": 60, "max": 100, "min": 0},
            {"key": "飞船状态", "label": "飞船状态", "type": "text", "default": "正常"},
            {"key": "scene", "label": "当前位置", "type": "text", "default": "太空站"},
        ],
        "characters": [
            {
                "name": "导航员",
                "personality": "机智、幽默、熟悉各星球局势",
                "background": "在星际航道混迹多年，熟悉各种捷径和生存技巧。",
                "avatar": "",
            }
        ],
    },
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_app_settings(db)

        flag = _read_seed_flag()
        story_count = db.query(models.Story).count()

        if flag is not None and story_count > 0:
            print("数据库已有故事数据，跳过预置故事。")
            return

        if flag is not None and story_count == 0:
            print("检测到预置标记但数据为空，重新预置...")

        for sample in SAMPLE_STORIES:
            story_data = {k: v for k, v in sample.items() if k != "characters"}
            chars = sample.get("characters", [])
            story = models.Story(**story_data)
            db.add(story)
            db.flush()
            for c in chars:
                db.add(models.Character(story_id=story.id, **c))

        db.commit()
        actual_count = db.query(models.Story).count()
        _write_seed_flag(actual_count)
        print(f"已预置 {actual_count} 个示例故事。")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
