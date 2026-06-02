"""Tail metadata extraction prompts (second-pass structured call)."""
from __future__ import annotations

_TAIL_META_PROMPT = """【当前正文】
{body_text}

【当前角色状态】
{prev_character_state}

【当前故事状态】
{prev_story_state}

【记忆日志（最近5条）】
{recent_memory}

请基于以上正文和历史状态，生成JSON元数据。你必须且仅返回一个合法JSON对象，不得添加任何其他文字。

JSON字段：
- reply_text: string，固定返回空字符串 ""
- scene: string，当前场景描述（30字以内，包含地点+环境+氛围）
- character_state: object，包含emotion(情绪3-6字), fatigue(0-100整数), mood(心情3字内)。状态应基于上一轮自然演变，emotion/mood不应突变或重置，fatigue应渐进变化
- story_state: object，包含chapter(章节名), progress(0-100整数，只能增加或不变), current_goal(当前目标), current_conflict(当前冲突)。chapter仅在场景显著切换时更改
- memory_update: string[]，本轮需要记忆更新的关键事件
- plot_label: string，剧情标签（4-10字，无重大事件时为空字符串）
- highlight_terms: string[]，需要高亮的关键词列表
""".strip()

TAIL_SYSTEM_PROMPT = (
    "你是一个互动小说的结构化数据提取器。"
    "根据给定的故事正文和历史上下文，提取信息生成JSON元数据。"
    "你必须且仅能返回一个合法JSON对象，不得添加任何其他文字。"
)
