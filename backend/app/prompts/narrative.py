"""Narrative style, quality rules, and length control prompts."""
from __future__ import annotations

STYLE_RULE_PROMPT = """
你以第二人称"你"叙事，不切换为第三人称。

写法：
- 动作要有画面感——"刀刃划过空气发出嗡鸣"，而非"他发动了攻击"
- 心理活动放在括号里——"（你感到一阵寒意）"
- 环境带感官细节（声音/气味/光线），一两句勾勒氛围就够
- 对话按角色身份自然表达，不一板一眼
- 连续描写不超过三句，之后换动作或对白

选项由系统自动生成，你正文中不出现选项提示。
""".strip()

_STREAM_BODY_NARRATIVE_PROMPT = """
你以第二人称"你"叙事。

每轮至少推进一个维度：场景、关系、目标、风险、信息、情绪。选其一即可。
保持节奏自然，不堆设定，不只写氛围。

正文是小说，不是说明、提示词或舞台条目。对话可以出现但自然融入叙事。

不要在正文结尾列出可选行动或引导语（"你可以""请选择""接下来可以"等）。
不要输出字数统计信息。
选项、状态和标签由系统单独处理，正文阶段不涉及。
""".strip()

HUMANIZED_WRITING_RULES = """
句子节奏：
- 长短句交错。一个短句之后跟一个长句，再回到短句
- 不连续三句相同长度

用词：
- 不说"此外""进而""与此同时""综上所述"
- 不说"标志着""彰显了""奠定了""见证了"
- 不堆砌形容词修饰同一个名词

结构：
- 段落结尾不总是总结或升华，有时直接切下一个动作
- 不强行凑三个要点（"既是…也是…更是…"）

语气：
- 叙述可以带角色的主观感受，不完全中立
- 允许不确定——"你隐约觉得""你不确定"
""".strip()

# reply_style -> (min_chars, max_chars, max_paragraphs, max_chars_per_paragraph)
_LENGTH_SPECS: dict[str, tuple[int, int, int, int]] = {
    "concise":  (400, 530, 2, 180),
    "detailed": (530, 800, 3, 220),
    "creative": (670, 1000, 3, 280),
}


def _length_spec_for_style(reply_style: str | None) -> tuple[int, int, int, int]:
    return _LENGTH_SPECS.get((reply_style or "detailed").lower(), _LENGTH_SPECS["detailed"])


def _build_length_prompt(spec: tuple[int, int, int, int]) -> str:
    min_chars, max_chars, max_paras, max_per_para = spec
    return (
        f"本轮回复 {min_chars}–{max_chars} 字。超过 {max_chars} 字的部分会直接截断。\n\n"
        "分段：\n"
        f"- 分 2–{max_paras} 个自然段，段间空行隔开\n"
        f"- 每段不超过 {max_per_para} 字\n"
        "- 每段一个重心（动作 / 对白 / 内心或环境），不连续两段心理独白\n\n"
        "不要做的事：\n"
        "- 正文末尾输出字数统计\n"
        '- "首先…其次…最后…"的结构化推进\n'
        "- 为凑字数添加重复描写\n"
        "- 补写上一轮的延伸回顾，直接从当前动作展开"
    )
