"""Main chat body generation prompts and delimiter helpers."""
from __future__ import annotations

import secrets
import string

from .plot import PLOT_LABEL_RULES, STORY_STATE_RULES

STREAM_TAIL_DELIMITER = "<<<STRUCTURED_TAIL>>>"  # kept for backwards compat

_TAIL_DELIMITER_ALPHABET = string.ascii_letters + string.digits


def _make_tail_delimiter() -> str:
    """Generate a per-request opaque delimiter token."""
    nonce = ''.join(secrets.choice(_TAIL_DELIMITER_ALPHABET) for _ in range(32))
    return f"<<<TAIL_{nonce}>>>"


def _escape_tail_delimiter(text: str, delimiter: str = STREAM_TAIL_DELIMITER) -> str:
    """Escape the delimiter in user-controlled text to prevent prompt injection."""
    return text.replace(delimiter, f"<ESCAPED_{delimiter}>")


def _restore_tail_escape(text: str, delimiter: str = STREAM_TAIL_DELIMITER) -> str:
    """Restore escaped delimiter in received text."""
    return text.replace(f"<ESCAPED_{delimiter}>", delimiter)


JSON_RULE_PROMPT = """
只返回一个 JSON 对象，不输出额外文字或 markdown 代码块。

示例：
用户输入：你缓缓推开古庙的斑驳木门，一股混杂着尘土与檀香的气息扑面而来。月光从破败的窗棂间洒落，照亮了布满灰尘的地面。你隐约听到深处传来细微的脚步声，像是有什么东西在缓慢移动。
期望输出：
{
  "reply_text": "你屏住呼吸。身形压低，贴向倾颓的木柱。月光只照到庭院石板路的半边——另一半隐在暗处。空气中那股古旧的气息让心跳更快了。脚步声停了。又重新响起，比刚才近了一些。（是风，还是……）短剑的握柄贴着手心，凉得发腻。",
  "scene": "古庙残殿，月色清冷，氛围诡异紧张",
  "character_state": {"emotion": "紧张警觉", "fatigue": 25, "mood": "戒备"},
  "story_state": {"chapter": "古庙探秘", "progress": 15, "current_goal": "查明脚步声来源", "current_conflict": "未知威胁潜伏"},
  "memory_update": ["古庙内有人活动"],
  "plot_label": ""
}

示例：
用户输入：你成功挡下黑衣人的第一波攻势，趁他收刀的间隙猛然反击。你的剑锋划破他的衣袖，一道寒光闪过，一枚古朴的玉佩从对方腰间掉落，散发着微微荧光。黑衣人面色骤变，厉喝一声再次扑来。
期望输出：
{
  "reply_text": "剑尖一挑。玉佩落入掌心。温润的触感让你一怔——玉佩内部似有气流涌动。黑衣人的眼神变了，从凌厉到恐慌。\"把玉佩交出来！\"刀芒裹着杀意劈面而来，你侧身闪过。掌心的玉佩明灭不定，把虎口的血照得忽明忽暗。",
  "scene": "月下激战，刀光剑影，局势紧张",
  "character_state": {"emotion": "兴奋紧张", "fatigue": 45, "mood": "激动"},
  "story_state": {"chapter": "玉佩之谜", "progress": 28, "current_goal": "击退黑衣人并逃离", "current_conflict": "玉佩引发多方觊觎"},
  "memory_update": ["获得神秘玉佩", "黑衣人意图抢夺玉佩"],
  "plot_label": "获得神秘玉佩"
}

字段（全部必填）：
- reply_text: string，正文，包含动作描写和心理或环境细节
- scene: string，30字以内，地点+环境+氛围
- character_state: {emotion(string 3-6字), fatigue(int 0-100), mood(string 3字内)}
- story_state: {chapter(string), progress(int 0-100只增不减), current_goal(string), current_conflict(string)}
- memory_update: string[]
- plot_label: string，4-10个汉字（本轮有重大事件时生成，否则""）
""" + PLOT_LABEL_RULES + """
""".strip()

STREAM_ERROR_STAGE_UPSTREAM = "upstream"
STREAM_ERROR_STAGE_PRE_DELTA = "pre_delta"
STREAM_ERROR_STAGE_POST_DELTA = "post_delta"
STREAM_ERROR_STAGE_TAIL_DELIMITER = "tail_delimiter"
STREAM_ERROR_STAGE_TAIL_JSON = "tail_json"
STREAM_ERROR_STAGE_TAIL_SCHEMA = "tail_schema"


def make_stream_rule_prompt(delimiter: str) -> str:
    return """
正文第一句直接开始叙述。不在开头说"好的""我将""根据设定""以下是""请看"。

正文结束后换行输出分隔符，然后是 JSON。正文与 JSON 之间没有过渡语。

分隔符：""" + f"{delimiter.strip()}" + """
正文：[你的小说内容]
分隔符（单独一行）
JSON：[你的JSON对象]

示例：
正文：你推开石门，阴冷的气息扑面而来。月光从穹顶裂缝中洒落，照亮了布满青苔的地面。前方有一座古老的石碑，刻满了模糊的文字。
分隔符
JSON：{"reply_text":"你缓步走向石碑，指尖拂过冰凉的石面。月尘在光柱中飞舞，空气中弥漫着千年沉睡的霉味。那些古老的文字似乎记载着某段被遗忘的历史","scene":"地下石室，古碑林立，月光幽微","character_state":{"emotion":"好奇平静","fatigue":20,"mood":"思索"},"story_state":{"chapter":"古碑之秘","progress":12,"current_goal":"解读石碑文字","current_conflict":"未知危险潜伏"},"memory_update":["发现古老石碑"],"plot_label":""}

JSON字段（全部必填）：reply_text, scene, character_state(emotion/fatigue/mood), story_state, memory_update, plot_label
""".strip()
