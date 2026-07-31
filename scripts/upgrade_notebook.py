"""旧存档一键升级：把老式流水账/剧情状态整理进故事笔记本三线。

用法：
    python scripts/upgrade_notebook.py                # 全部升级
    python scripts/upgrade_notebook.py --dry-run      # 只统计需要升级的存档，不调 AI
    python scripts/upgrade_notebook.py --limit 5      # 只升级前 5 个

规则：
- 只处理 notebook 为 NULL/空 且 (memory_log 非空 或 story_state 非空) 的存档
- 每个存档调用一次模型（NotebookBootstrapContract），失败跳过并记录，不中断
- 旧数据原样保留（memory_log/story_state 不动），只补 notebook
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
from app.database import SessionLocal  # noqa: E402
from fastapi import HTTPException  # noqa: E402

BOOTSTRAP_SYSTEM = (
    "你是互动小说的剧情整理员。根据故事世界观、剧情状态和记忆日志，"
    "把已经发生且影响后续的重要信息分类整理成三本分册。"
    "你必须且仅能返回一个合法 JSON 对象，不得添加任何其他文字。"
    "JSON 字段：world_line(string[]，世界正在发生/已发生的大事)、"
    "character_line(string[]，角色的重要处境变化)、"
    "relationship_line(string[]，角色之间关系的变化)。"
    "每条 30 字以内、一句话、用小说中的人名。无对应内容返回空数组。"
)

USER_TEMPLATE = """【故事世界观】
{world_setting}

【当前剧情状态】
{story_state}

【记忆日志（已发生事件流水）】
{memory_log}

请分类整理成三线笔记本。"""


def _needs_upgrade(archive: models.Archive) -> bool:
    if archive.notebook:
        return False
    return bool(archive.memory_log) or bool(archive.story_state)


def upgrade_one(db, archive: models.Archive, candidates) -> bool:
    memory_log = "\n".join(f"- {m}" for m in (archive.memory_log or [])[-200:]) or "（无）"
    story_state = json.dumps(archive.story_state or {}, ensure_ascii=False)
    world_setting = (archive.story.system_prompt or "") or "（无）"
    messages = [
        {"role": "system", "content": BOOTSTRAP_SYSTEM},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                world_setting=world_setting,
                story_state=story_state,
                memory_log=memory_log,
            ),
        },
    ]
    from app.api.ai_contracts import (
        TASK_NOTEBOOK_BOOTSTRAP,
        build_contract_response_format,
    )
    content, _ = _call_model_once(
        candidates[0],
        messages,
        0.2,
        response_format=build_contract_response_format(TASK_NOTEBOOK_BOOTSTRAP),
        timeout=60.0,
    )
    # 用既有 _extract_json_payload 抗代码围栏/多余文字（chat_models.py:280）
    parsed = _extract_json_payload(content)
    # 类型防御：模型偶发把数组字段返回成字符串（如 "world_line": "阿澈受伤"）时，
    # 按 list 迭代会逐字符拆成单字条目落库；非 list 一律按空处理
    notebook = {}
    for line in ("world_line", "character_line", "relationship_line"):
        raw = parsed.get(line, [])
        items = raw if isinstance(raw, list) else []
        notebook[line] = [
            {"text": str(s).strip()[:200], "status": "active"}
            for s in items
            if isinstance(s, str) and s.strip()
        ]
    if not any(notebook.values()):
        return False
    archive.notebook = notebook
    db.commit()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="旧存档笔记本批量升级")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不调 AI")
    parser.add_argument("--limit", type=int, default=0, help="最多升级 N 个（0=全部）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        archives = (
            db.query(models.Archive)
            .order_by(models.Archive.id.asc())
            .all()
        )
        todo = [a for a in archives if _needs_upgrade(a)]
        if args.limit > 0:
            todo = todo[: args.limit]
        if not todo:
            print("没有需要升级的存档")
            return
        print(f"共 {len(todo)} 个存档需要升级")
        if args.dry_run:
            print("dry-run：以上为待升级清单，未调用模型")
            return

        try:
            candidates = _get_normal_model_candidates(db, models.UserSettings())
        except HTTPException as exc:
            # 只有 503（未配置可用模型）才按"未配置模型"提示；上游其他错误（如 500）
            # 原样抛出，避免把服务端故障误报成配置问题
            if exc.status_code != 503:
                raise
            print("未配置可用的聊天模型，请在管理面板配置后重试")
            sys.exit(1)
        if not candidates:
            print("未配置可用的聊天模型，请在管理面板配置后重试")
            sys.exit(1)

        ok = 0
        failed: list[int] = []
        for archive in todo:
            try:
                if upgrade_one(db, archive, candidates):
                    ok += 1
                    print(f"✓ 存档 {archive.id}（{archive.name}）升级完成")
                else:
                    failed.append(archive.id)
                    print(f"✗ 存档 {archive.id} 整理结果为空，跳过")
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed.append(archive.id)
                print(f"✗ 存档 {archive.id} 失败：{exc}")
        print(f"\n完成：成功 {ok}，失败 {len(failed)}" + (f"，失败存档 {failed}" if failed else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
