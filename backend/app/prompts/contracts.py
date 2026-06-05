"""Structured output contract prompt rules and options validation."""

from __future__ import annotations

# ============================================================
# Output contract rule prompts (from ai_contracts.py)
# ============================================================

_OPTIONS_RULE_PROMPT = """
你必须仅返回一个合法 JSON 对象，不要输出额外文字、解释或 markdown 代码块。

只允许以下字段：
- options: string[]，后续可点击剧情选项列表

规则：
- 仅生成 options，不要生成 reply_text / scene / story_state / 其他字段
- 每个选项简洁明确、可直接点击
- 优先保证差异化，不要重复表达
- 若没有合适选项，也必须返回 {"options": []}
""".strip()

_STATE_BROADCAST_RULE_PROMPT = """
你必须仅返回一个合法 JSON 对象，不要输出额外文字、解释或 markdown 代码块。

只允许以下字段：
- content: string，状态播报正文（键值对列表，格式为：属性名 | 属性值，每行一个属性）

规则：
- content 字段内只放键值对，每行一个属性
- 根据小说世界观和上下文自行判断应展示哪些属性，不要用固定字段列表
- 至少生成 5-8 个属性（不少于 5 个），尽量丰富
- 属性类别参考（不限于这些）：角色状态（生命值/精神值/体力等）、场景环境、章节进度、当前目标、装备物品、同伴关系、时间天气、特殊效果等
- 空值显示"无"，不省略
- 不推进剧情、不做文字描写
- 不要生成 reply_text / scene / options / 其他字段
""".strip()

_STORY_GENERATE_RULE_PROMPT = """
你必须仅返回一个合法 JSON 对象，不要输出额外文字、解释或 markdown 代码块。

必须包含以下字段：
- title: string
- category: string
- tags: string[]
- cover_url: string
- description: string
- world_setting: string
- image_style: string

规则：
- cover_url 固定返回空字符串
- 只返回这 7 个字段，不要新增字段
""".strip()

_PRESET_OPENINGS_RULE_PROMPT = """
你必须仅返回一个合法 JSON 对象，不要输出额外文字、解释或 markdown 代码块。

必须包含以下字段：
- openings: { label: string, value: string }[]

规则：
- openings 固定返回 5 条
- 不要返回 id，id 由后端补齐
- 不要返回其他字段
""".strip()

# ============================================================
# Options validation constants (from chat_options_validator.py)
# ============================================================

OPTIONS_FORBIDDEN_WORDS = ["或", "随机应变", "视情况而定", "先看看再说", "想想再说"]
OPTIONS_MIN_LENGTH = 8
OPTIONS_MAX_LENGTH = 25
