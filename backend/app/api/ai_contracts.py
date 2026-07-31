"""Unified AI output contracts and strict schema helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .. import schemas
from ..prompts import (
    _OPTIONS_RULE_PROMPT,
    _PRESET_OPENINGS_RULE_PROMPT,
    _STATE_BROADCAST_RULE_PROMPT,
    _STORY_GENERATE_RULE_PROMPT,
    JSON_RULE_PROMPT,
)

ContractTask = Literal[
    "chat_response",
    "options_generate",
    "state_broadcast",
    "story_generate",
    "preset_openings",
    "notebook_bootstrap",
]

TASK_CHAT_RESPONSE: ContractTask = "chat_response"
TASK_OPTIONS_GENERATE: ContractTask = "options_generate"
TASK_STATE_BROADCAST: ContractTask = "state_broadcast"
TASK_STORY_GENERATE: ContractTask = "story_generate"
TASK_PRESET_OPENINGS: ContractTask = "preset_openings"
TASK_NOTEBOOK_BOOTSTRAP: ContractTask = "notebook_bootstrap"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatCharacterStateContract(_StrictModel):
    emotion: str = ""
    fatigue: int = 0
    mood: str = ""


class ChatStoryStateContract(_StrictModel):
    chapter: str = ""
    progress: int = 0
    current_goal: str = ""
    current_conflict: str = ""


class NotebookUpdateContract(_StrictModel):
    """一轮 tail 对故事笔记本的更新：add 追加 active 条目，close 按注入编号置 closed。"""

    add_world: list[str] = Field(default_factory=list)
    add_character: list[str] = Field(default_factory=list)
    add_relationship: list[str] = Field(default_factory=list)
    close_world: list[str] = Field(default_factory=list)
    close_character: list[str] = Field(default_factory=list)
    close_relationship: list[str] = Field(default_factory=list)


class NotebookBootstrapContract(_StrictModel):
    """旧存档升级：把流水账/剧情状态整理成三线笔记本（每条均为 active 条目）。"""

    world_line: list[str] = Field(default_factory=list)
    character_line: list[str] = Field(default_factory=list)
    relationship_line: list[str] = Field(default_factory=list)


class ChatResponseContract(_StrictModel):
    reply_text: str = ""
    scene: str = ""
    character_state: ChatCharacterStateContract = Field(default_factory=ChatCharacterStateContract)
    story_state: ChatStoryStateContract = Field(default_factory=ChatStoryStateContract)
    memory_update: list[str] = Field(default_factory=list)
    plot_label: str = ""
    highlight_terms: list[str] = Field(default_factory=list)
    notebook_update: NotebookUpdateContract = Field(
        default_factory=NotebookUpdateContract
    )


class OptionsGenerateContract(_StrictModel):
    options: list[str] = Field(default_factory=list)


class StateBroadcastContract(_StrictModel):
    content: str


class StoryGenerateContract(_StrictModel):
    title: str
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    cover_url: str = ""
    description: str
    world_setting: str
    image_style: str = ""


class PresetOpeningContract(_StrictModel):
    label: str
    value: str


class PresetOpeningsContract(_StrictModel):
    openings: list[PresetOpeningContract] = Field(default_factory=list, min_length=5, max_length=5)


@dataclass(frozen=True)
class ContractSpec:
    task: ContractTask
    schema_name: str
    strict_model: type[_StrictModel]
    output_rule_prompt: str
    allow_legacy_text_fallback: bool = False


_SPECS: dict[ContractTask, ContractSpec] = {
    TASK_CHAT_RESPONSE: ContractSpec(
        task=TASK_CHAT_RESPONSE,
        schema_name="chat_response",
        strict_model=ChatResponseContract,
        output_rule_prompt=JSON_RULE_PROMPT,
    ),
    TASK_OPTIONS_GENERATE: ContractSpec(
        task=TASK_OPTIONS_GENERATE,
        schema_name="options_generate",
        strict_model=OptionsGenerateContract,
        output_rule_prompt=_OPTIONS_RULE_PROMPT,
        allow_legacy_text_fallback=True,
    ),
    TASK_STATE_BROADCAST: ContractSpec(
        task=TASK_STATE_BROADCAST,
        schema_name="state_broadcast",
        strict_model=StateBroadcastContract,
        output_rule_prompt=_STATE_BROADCAST_RULE_PROMPT,
    ),
    TASK_STORY_GENERATE: ContractSpec(
        task=TASK_STORY_GENERATE,
        schema_name="story_generate",
        strict_model=StoryGenerateContract,
        output_rule_prompt=_STORY_GENERATE_RULE_PROMPT,
    ),
    TASK_PRESET_OPENINGS: ContractSpec(
        task=TASK_PRESET_OPENINGS,
        schema_name="preset_openings",
        strict_model=PresetOpeningsContract,
        output_rule_prompt=_PRESET_OPENINGS_RULE_PROMPT,
    ),
    TASK_NOTEBOOK_BOOTSTRAP: ContractSpec(
        task=TASK_NOTEBOOK_BOOTSTRAP,
        schema_name="notebook_bootstrap",
        strict_model=NotebookBootstrapContract,
        output_rule_prompt=JSON_RULE_PROMPT,
    ),
}


def get_contract_spec(task: ContractTask) -> ContractSpec:
    return _SPECS[task]


def get_contract_output_rule(task: ContractTask) -> str:
    return get_contract_spec(task).output_rule_prompt


def contract_allows_legacy_text_fallback(task: ContractTask) -> bool:
    return get_contract_spec(task).allow_legacy_text_fallback


def build_contract_response_format(task: ContractTask) -> dict:
    spec = get_contract_spec(task)
    schema = spec.strict_model.model_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {
            "name": spec.schema_name,
            "strict": True,
            "schema": schema,
        },
    }


def _unique_trimmed(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in items:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


_PLOT_LABEL_FORBIDDEN_CHARS = re.compile(r"[\r\n`{}\[\]\":]")


def _normalize_plot_label(value: str) -> str:
    label = value.strip()
    if not label:
        return ""
    if len(label) < 2 or len(label) > 20:
        return ""
    if _PLOT_LABEL_FORBIDDEN_CHARS.search(label):
        return ""
    if any(term in label.lower() for term in ("response_format", "json", "schema")):
        return ""
    if any(term in label for term in ("系统提示", "以下是输出", "输出格式", "用户输入")):
        return ""
    return label


def _normalize_chat_contract(contract: ChatResponseContract) -> ChatResponseContract:
    return contract.model_copy(
        update={
            "reply_text": contract.reply_text.strip(),
            "scene": contract.scene.strip(),
            "memory_update": _unique_trimmed(contract.memory_update),
            "plot_label": _normalize_plot_label(contract.plot_label),
            "highlight_terms": _unique_trimmed(contract.highlight_terms),
            "character_state": contract.character_state.model_copy(
                update={
                    "emotion": contract.character_state.emotion.strip(),
                    "mood": contract.character_state.mood.strip(),
                }
            ),
            "story_state": contract.story_state.model_copy(
                update={
                    "chapter": contract.story_state.chapter.strip(),
                    "current_goal": contract.story_state.current_goal.strip(),
                    "current_conflict": contract.story_state.current_conflict.strip(),
                }
            ),
        }
    )


def _normalize_options_contract(contract: OptionsGenerateContract) -> OptionsGenerateContract:
    return contract.model_copy(update={"options": _unique_trimmed(contract.options)})


def _normalize_state_broadcast_contract(contract: StateBroadcastContract) -> StateBroadcastContract:
    return contract.model_copy(update={"content": contract.content.strip()})


def _normalize_story_generate_contract(contract: StoryGenerateContract) -> StoryGenerateContract:
    return contract.model_copy(
        update={
            "title": contract.title.strip(),
            "category": contract.category.strip(),
            "tags": _unique_trimmed(contract.tags),
            "cover_url": contract.cover_url.strip(),
            "description": contract.description.strip(),
            "world_setting": contract.world_setting.strip(),
            "image_style": contract.image_style.strip(),
        }
    )


def _normalize_preset_openings_contract(contract: PresetOpeningsContract) -> PresetOpeningsContract:
    normalized = [
        opening.model_copy(
            update={
                "label": opening.label.strip()[:10],
                "value": opening.value.strip()[:100],
            }
        )
        for opening in contract.openings
        if opening.label.strip() and opening.value.strip()
    ]
    if len(normalized) != 5:
        raise ValueError("预设开场必须严格返回 5 条")
    return contract.model_copy(update={"openings": normalized[:5]})


def validate_contract_payload(task: ContractTask, payload: dict) -> _StrictModel:
    spec = get_contract_spec(task)
    validated = spec.strict_model.model_validate(payload)

    if task == TASK_CHAT_RESPONSE:
        return _normalize_chat_contract(validated)
    if task == TASK_OPTIONS_GENERATE:
        return _normalize_options_contract(validated)
    if task == TASK_STATE_BROADCAST:
        return _normalize_state_broadcast_contract(validated)
    if task == TASK_STORY_GENERATE:
        return _normalize_story_generate_contract(validated)
    if task == TASK_PRESET_OPENINGS:
        return _normalize_preset_openings_contract(validated)
    return validated


def to_public_schema(task: ContractTask, validated: _StrictModel):
    if task == TASK_CHAT_RESPONSE:
        item = validated
        return schemas.ChatResponse(
            reply_text=item.reply_text,
            scene=item.scene,
            character_state=item.character_state.model_dump(),
            story_state=item.story_state.model_dump(),
            memory_update=item.memory_update,
            plot_label=item.plot_label or None,
            highlight_terms=item.highlight_terms,
            notebook_update=item.notebook_update.model_dump(),
        )

    if task == TASK_OPTIONS_GENERATE:
        item = validated
        return schemas.OptionsGenerateOut(options=item.options)

    if task == TASK_STATE_BROADCAST:
        item = validated
        return schemas.StateBroadcastOut(content=item.content)

    if task == TASK_STORY_GENERATE:
        item = validated
        return schemas.StoryGenerateOut(**item.model_dump())

    if task == TASK_PRESET_OPENINGS:
        item = validated
        return schemas.PresetOpeningsResponse(
            openings=[
                schemas.PresetOpeningItem(id=index + 1, label=opening.label, value=opening.value)
                for index, opening in enumerate(item.openings[:5])
            ]
        )

    raise KeyError(f"Unknown contract task: {task}")


def validate_and_convert_contract(task: ContractTask, payload: dict):
    return to_public_schema(task, validate_contract_payload(task, payload))
