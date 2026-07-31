"""记忆考试：验收"故事笔记本"对长对话一致性的提升。

流程：
1. 内置一个测试故事（固定世界观+角色），创建临时存档
2. 用固定玩家脚本（预置 50 轮行动/对话）与 AI 对话 50 轮（走 send-stream 全流程，笔记本自动记录）
3. 考试官读完整对话出 5 题（涉及早期事件的角色名/关系/事件）
4. 每题两次作答：题干 + 最近 5 轮对话（对照组） vs 题干 + 最近 5 轮对话 + 笔记本（实验组）
5. 考试官判卷（正确/部分/错误），输出分数对比表

退出码：0 正常完成（无论分数）；--fail-below N 时得分低于 N 退出 1。

用法：
    python scripts/memory_exam.py              # 全流程（约 250+ 次模型调用）
    python scripts/memory_exam.py --rounds 20  # 缩短轮数快速冒烟
    python scripts/memory_exam.py --fail-below 60
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import models  # noqa: E402
from app.api.chat_models import (  # noqa: E402
    _call_model_once,
    _extract_json_payload,
    _get_normal_model_candidates,
)
from app.api.chat_storage import _get_or_create_settings, _query_dialogue_history  # noqa: E402
from app.database import SessionLocal  # noqa: E402

EXAM_WORLD = (
    "架空古代武侠世界。主角阿澈是青云门弟子，师兄云霁，师妹林晓。"
    "师父白眉道长。门派被魔教血洗后，阿澈与云霁、林晓三人流亡，"
    "寻找传说中的神器玄铁剑为门派复仇。"
)

PLAYER_SCRIPT = [
    "我们今晚在哪过夜？",
    "云霁，你的伤怎么样了？",
    "林晓，别怕，有我在。",
    "前面有座破庙，进去躲雨。",
    "听说魔教在悬赏我们的人头。",
    "我要练功到天亮。",
    "云霁教了我一招新的剑法。",
    "林晓做了一顿饭。",
    "我梦到师父了。",
    "魔教的人追上来了！",
    "快跑，我断后！",
    "我们甩掉他们了吗？",
    "林晓中箭了！",
    "我去采药救她。",
    "林晓醒过来了。",
    "云霁说他知道玄铁剑的下落。",
    "那我们明天就出发。",
    "山里有条河，怎么过河？",
    "云霁背林晓过河。",
    "我捡到了一块奇怪的石头。",
    "前面是魔教的分坛。",
    "我们绕过去，不要打草惊蛇。",
    "夜里有人跟踪我们。",
    "是我大意了，差点被发现。",
    "林晓提议扮成商人混进城。",
    "我们成功混进了城。",
    "城里在庆祝魔教的胜利。",
    "我气得发抖。",
    "云霁让我冷静。",
    "我们在客栈住下。",
    "客栈掌柜认识我们？！",
    "他是师父的旧友。",
    "掌柜告诉了我们玄铁剑的线索。",
    "玄铁剑在城主府地牢。",
    "我们决定夜探城主府。",
    "林晓会开锁。",
    "我们潜入了城主府。",
    "地牢里有个神秘老者。",
    "老者说他是被魔教囚禁的铁匠。",
    "铁匠愿意帮我们打造玄铁剑。",
    "我们救出了铁匠。",
    "魔教守卫发现了我们！",
    "一场恶战。",
    "云霁受伤了。",
    "我们带着铁匠逃了出来。",
    "铁匠说玄铁剑还差最后一道工序。",
    "我们需要千年寒铁。",
    "千年寒铁在雪山之巅。",
    "我们向雪山进发。",
    "雪山到了，林晓说她的老家就在山脚。",
]

EXAM_SYSTEM = "你是互动小说剧情考试官。严格根据提供的剧情事实作答，不要编造。"


def _ask(candidates, messages: list[dict], temperature: float = 0.3) -> str:
    content, _ = _call_model_once(
        candidates[0], messages, temperature, timeout=60.0
    )
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description="记忆考试验收脚本")
    parser.add_argument("--rounds", type=int, default=50, help="对话轮数（默认 50）")
    parser.add_argument("--fail-below", type=int, default=0, help="实验组得分低于该值退出 1")
    args = parser.parse_args()

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    db = SessionLocal()
    try:
        story_id: int | None = None
        story = models.Story(
            title="记忆考试临时故事",
            description="自动生成的验收故事",
            world_setting=EXAM_WORLD,
            system_prompt=EXAM_WORLD,
            state_config=[],
        )
        db.add(story)
        db.commit()
        story_id = story.id
        db.refresh(story)

        archive = models.Archive(
            story_id=story.id,
            name="考试存档",
            story_state={"chapter": "第一章", "progress": 0},
            memory_log=[],
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)

        script = PLAYER_SCRIPT[: args.rounds]
        for i, player_input in enumerate(script):
            with client.stream(
                "POST", "/api/chat/send-stream",
                json={"archive_id": archive.id, "message": player_input},
            ) as resp:
                if resp.status_code != 200:
                    print(f"第 {i + 1} 轮请求失败：HTTP {resp.status_code}")
                    raise SystemExit(1)
                # SSE 格式（chat_sse.py）："event: <name>\ndata: <json>\n\n"
                event_name = None
                for line in resp.iter_lines():
                    if not line:
                        continue
                    if line.startswith("event: "):
                        event_name = line[7:]
                    elif line.startswith("data: ") and event_name == "error":
                        data = json.loads(line[6:])
                        print(f"第 {i + 1} 轮失败：{data.get('message', '')}")
                        raise SystemExit(1)

        # 出题：考试官读全部消息（_query_dialogue_history 上限 200 条，50 轮=100 条足够；
        # 若加大轮数需分页读取，本脚本注释明示）
        all_msgs = _query_dialogue_history(db, archive.id, 200)
        transcript = "\n".join(
            f"{'玩家' if m.role == 'user' else 'AI'}: {m.content}" for m in all_msgs
        )
        questions_raw = _ask(
            _get_normal_model_candidates(db, _get_or_create_settings(db)),
            [
                {"role": "system", "content": EXAM_SYSTEM},
                {
                    "role": "user",
                    "content": f"以下是完整对话。出 5 道关于早期剧情的事实题（如：主角叫什么名字？林晓受了什么伤？谁愿意帮我们打造玄铁剑？），只返回 JSON 对象，格式 {{\"questions\": [{{\"question\": str, \"answer\": str}}]}}：\n\n{transcript[-20000:]}",
                },
            ],
            0.2,
        )
        questions = _extract_json_payload(questions_raw).get("questions", [])
        if not questions:
            print("考试官未生成有效题目，退出")
            raise SystemExit(1)

        # 判卷：每题 有/无 笔记本两组作答
        candidates = _get_normal_model_candidates(db, _get_or_create_settings(db))
        recent = "\n".join(f"{m.content}" for m in all_msgs[-5:])
        # expire_on_commit=False（Bug #47）下本会话 identity map 永不过期，
        # archive 仍是创建时的缓存（notebook=None）；refresh 拿到端点会话（get_db）
        # 在 50 轮对话中写入并 commit 的真实笔记本，否则实验组注入恒为空、验收静默失效
        db.refresh(archive)
        notebook = json.dumps(archive.notebook or {}, ensure_ascii=False)

        def answer(include_notebook: bool, q: dict) -> str:
            extra = (
                f"\n\n【故事笔记本】\n{notebook}" if include_notebook else ""
            )
            return _ask(
                candidates,
                [
                    {"role": "system", "content": EXAM_SYSTEM},
                    {
                        "role": "user",
                        "content": f"【最近 5 轮对话】\n{recent}{extra}\n\n问题：{q['question']}\n直接给出答案（30 字内）：",
                    },
                ],
                0.2,
            )

        def grade(q: dict, ans: str) -> int:
            verdict = _ask(
                candidates,
                [
                    {"role": "system", "content": EXAM_SYSTEM},
                    {
                        "role": "user",
                        "content": f"标准答案：{q['answer']}\n考生回答：{ans}\n判定：正确(2分)/部分正确(1分)/错误(0分)，只输出一个数字：",
                    },
                ],
                0.1,
            ).strip()
            for ch in verdict:
                if ch in "012":
                    return int(ch)
            return 0

        control_total = 0
        exam_total = 0
        print("\n题号 | 对照组(无笔记本) | 实验组(有笔记本) | 标准答案")
        for i, q in enumerate(questions[:5], 1):
            ctrl = answer(False, q)
            exp = answer(True, q)
            c_score = grade(q, ctrl)
            e_score = grade(q, exp)
            control_total += c_score
            exam_total += e_score
            print(f"{i} | {c_score} | {e_score} | {q['answer']}")

        print(f"\n对照组总分：{control_total}/10，实验组总分：{exam_total}/10")
        print(f"笔记本提升：+{exam_total - control_total} 分")
        if args.fail_below and exam_total < args.fail_below:
            sys.exit(1)
    finally:
        if story_id is not None:
            # bulk delete 不触发 ORM cascade，且 SQLite 默认关外键（database.py 未设 PRAGMA
            # foreign_keys）→ 删 Archive 前必须先把该 story 名下所有存档的消息与节点删干净，
            # 否则每次运行留 ~100+ 孤儿 chat_messages（story_nodes 同理）指向已删存档，重复运行累积
            archive_ids = [
                r[0]
                for r in db.query(models.Archive.id)
                .filter(models.Archive.story_id == story_id)
                .all()
            ]
            if archive_ids:
                db.query(models.ChatMessage).filter(
                    models.ChatMessage.archive_id.in_(archive_ids)
                ).delete()
                db.query(models.StoryNode).filter(
                    models.StoryNode.archive_id.in_(archive_ids)
                ).delete()
            db.query(models.Archive).filter(models.Archive.story_id == story_id).delete()
            db.query(models.Story).filter(models.Story.id == story_id).delete()
            db.commit()
        db.close()


if __name__ == "__main__":
    main()
