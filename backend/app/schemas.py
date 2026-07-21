from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_BASE_CONFIG = ConfigDict(protected_namespaces=())

# 合法图片尺寸——写入校验（本文件 Literal）与消费侧防线（image_generation）
# 共用此单一事实源；改动时需同步下方 Literal。
VALID_IMAGE_SIZES = ("1K", "2K", "3K")


# ---- Story ----
class StoryBase(BaseModel):
    title: str = Field(max_length=100)
    cover_image: str = Field(default="", max_length=500)
    background_image: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list)
    category: str = Field(default="其他", max_length=50)
    world_setting: str = Field(default="", max_length=5000)
    system_prompt: str = Field(default="", max_length=5000)
    state_config: list[dict] = Field(default_factory=list)
    opening_requirement: str = Field(default="", max_length=2000)
    image_style: str = Field(default="", max_length=500)  # 图片风格描述


class StoryCreate(StoryBase):
    pass


class StoryUpdate(StoryBase):
    title: str | None = Field(default=None, max_length=100)


class StoryOut(StoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Character ----
class CharacterBase(BaseModel):
    name: str
    personality: str = ""
    background: str = ""
    avatar: str = ""


class CharacterCreate(CharacterBase):
    story_id: int


class CharacterOut(CharacterBase):
    id: int
    story_id: int

    class Config:
        from_attributes = True


# ---- Archive ----
class ArchiveBase(BaseModel):
    name: str = "自动存档"


class ArchiveCreate(ArchiveBase):
    story_id: int
    state_data: dict = Field(default_factory=dict)
    story_state: dict = Field(default_factory=lambda: {"chapter": "第一章", "progress": 0})
    memory_log: list[str] = Field(default_factory=list)
    opening_requirement: str = ""  # 内部字段，用于存储 first_message


class ArchiveOut(ArchiveBase):
    id: int
    story_id: int
    state_data: dict
    story_state: dict
    memory_log: list[str]
    first_message: str = ""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- StoryNode ----
class StoryNodeOut(BaseModel):
    id: int
    archive_id: int
    message_id: int
    plot_label: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Chat ----
class ChatMessageOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    id: int
    archive_id: int
    role: str
    content: str
    state_snapshot: dict
    story_state: dict
    options: list[str]
    memory_update: list[str]
    image_url: str | None = None
    is_draft: bool = False
    plot_label: str | None = None
    model_name: str = ""
    is_state_broadcast: bool = False
    created_at: datetime


class ChatInput(BaseModel):
    archive_id: int
    message: str


class ChatStartInput(BaseModel):
    story_id: int
    opening_requirement: str = Field(min_length=1, max_length=2000)
    archive_id: int | None = None


class PresetOpeningItem(BaseModel):
    id: int
    label: str
    value: str


class PresetOpeningsRequest(BaseModel):
    """仅 story_id，不要求 opening_requirement（preset-openings 由前端单独调用）"""

    story_id: int


class PresetOpeningsResponse(BaseModel):
    openings: list[PresetOpeningItem]


class CharacterState(BaseModel):
    """角色状态快照"""

    name: str = ""
    location: str = ""
    mood: str = ""
    relationship: str = ""
    health: int = 100
    extra: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class StoryState(BaseModel):
    """故事状态快照"""

    chapter: str = ""
    progress: int = 0
    current_goal: str = ""
    current_conflict: str = ""
    extra: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ChatResponse(BaseModel):
    reply_text: str
    scene: str
    character_state: CharacterState = Field(default_factory=CharacterState)
    story_state: StoryState = Field(default_factory=StoryState)
    memory_update: list[str] = []
    plot_label: str | None = None  # 剧情标签，非流式响应时由AI直接生成
    highlight_terms: list[str] = []  # 需要高亮的关键词列表


class OptionsGenerateIn(BaseModel):
    archive_id: int
    count: int = 3
    guidance: str = ""


class OptionsGenerateOut(BaseModel):
    options: list[str]


# ---- State Broadcast ----
class StateBroadcastIn(BaseModel):
    archive_id: int


class StateBroadcastOut(BaseModel):
    role: str = "assistant"
    content: str


# ---- UserSettings ----
class UserSettingsOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)
    id: int
    model_name: str
    api_base_url: str
    context_length: int
    reply_style: str
    primary_model_id: int | None = None
    backup_model_ids: list[int] = []
    auto_generate_options: bool = True
    theme: str
    options_prompt: str | None = None
    copy_image_format: str = "url"
    disable_chat_bubble_elastic: bool = False
    show_background_image: bool = True
    memory_inject_count: int = 50


class UserSettingsUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_name: str | None = None
    api_base_url: str | None = None
    api_key: str | None = None
    context_length: int | None = None
    reply_style: str | None = None
    primary_model_id: int | None = None
    backup_model_ids: list[int] | None = None
    auto_generate_options: bool | None = None
    theme: str | None = None
    options_prompt: str | None = None
    copy_image_format: str | None = None
    disable_chat_bubble_elastic: bool | None = None
    show_background_image: bool | None = None
    memory_inject_count: int | None = None


# ---- ModelConfig ----
class ModelConfigIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: str | None = None
    model_id: str | None = None
    api_base_url: str | None = None
    api_key: str = ""
    enabled: int = 1
    priority: int = 100
    price_input_per_1k: float | None = None
    price_output_per_1k: float | None = None
    pricing_unit: str = "per_1k"  # "per_1k" | "per_1m"
    model_type: str = "chat"
    image_api_key: str = ""
    image_api_base: str = ""
    api_mode: str = "openai_chat_completions"
    image_api_mode: str = "openai_images"
    image_workflow_template: str | None = None
    temperature: float | None = None  # 0~1, None = use style-based default
    max_tokens: int | None = None  # 512~8192, None = no limit
    response_format_mode: str = "json_schema"  # "json_schema" | "json_object"


class ModelConfigOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: int
    name: str
    model_id: str
    api_base_url: str
    enabled: int
    priority: int
    price_input_per_1k: float | None = None
    price_output_per_1k: float | None = None
    pricing_unit: str = "per_1k"
    has_api_key: bool
    model_type: str = "chat"
    image_api_base: str = ""
    api_mode: str
    image_api_mode: str
    image_workflow_template: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    response_format_mode: str = "json_schema"


class AppSettingsOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)
    id: int
    default_system_prompt: str
    default_system_prompt_source: str = "custom"
    state_broadcast_prompt: str = ""
    enable_image_generation: bool = False
    default_image_model_id: int | None = None
    image_size: str = "2K"
    image_watermark: bool = False
    default_image_style: str = "唯美、氛围感强，适合作为小说封面"
    style_skill_enabled: int = 0
    style_skill_content: str = ""


class AppSettingsUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    default_system_prompt: str | None = None
    state_broadcast_prompt: str | None = None
    enable_image_generation: bool | None = None
    default_image_model_id: int | None = None
    image_size: Literal["1K", "2K", "3K"] | None = None  # 与 VALID_IMAGE_SIZES 同步
    image_watermark: bool | None = None
    default_image_style: str | None = None
    style_skill_enabled: int | None = None
    style_skill_content: str | None = None


class SystemShutdownOut(BaseModel):
    ok: bool = True
    message: str
    scheduled_at: datetime
    backend_delay_ms: int
    frontend_delay_ms: int


# ---- Metrics ----
class MetricsSummaryOut(BaseModel):
    total_calls: int
    success_calls: int
    success_rate: float
    avg_latency_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float
    plot_label_calls: int = 0  # 产生剧情标签的调用次数
    plot_label_cost: float = 0.0  # 剧情标签调用总费用


class MetricsByModelItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_config_id: int | None = None
    model_name: str
    total_calls: int
    success_calls: int
    success_rate: float
    avg_latency_ms: float
    total_tokens: int
    total_cost: float
    plot_label_calls: int = 0
    plot_label_cost: float = 0.0


class MetricsTimeseriesItem(BaseModel):
    day: str
    total_calls: int
    success_calls: int
    success_rate: float
    total_tokens: int
    total_cost: float


class MetricsResetIn(BaseModel):
    confirm_text: str


class StreamRequestLogItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: int
    request_id: str
    created_at: datetime
    archive_id: int | None = None
    story_id: int | None = None
    model_name: str
    success: bool
    error_code: str
    error_stage: str
    stream_emitted_delta: bool
    ttfb_ms: int
    fallback_used: bool
    tail_valid: bool
    latency_ms: int
    plot_label_generated: bool = False


# ---- Story Generate ----
class StoryGenerateIn(BaseModel):
    model_config = {"protected_namespaces": ()}

    category: str = Field(default="", max_length=50)
    title_hint: str = Field(default="", max_length=100)
    tags_hint: str = Field(default="", max_length=200)
    model_id: int | None = None
    image_model_id: int | None = None  # 旧字段，保留向后兼容
    image_style: str = Field(default="", max_length=500)  # 用户预填的风格，留空则AI自动生成
    preference: str = Field(default="", max_length=500)  # 用户对故事的偏好要求
    generate_cover: bool = False  # 是否生成封面图
    cover_image_model_id: int | None = None  # 封面图模型ID
    generate_background: bool = False  # 是否生成背景图
    background_image_model_id: int | None = None  # 背景图模型ID


class StoryGenerateOut(BaseModel):
    title: str
    category: str
    tags: list[str]
    cover_url: str = ""
    background_url: str = ""
    description: str
    world_setting: str
    image_style: str = ""  # 同步产出的图片风格描述


class GenerateCoverIn(BaseModel):
    model_config = {"protected_namespaces": ()}

    world_setting: str = Field(max_length=5000)
    title: str = Field(max_length=100)
    image_style: str = Field(default="", max_length=500)
    image_model_id: int | None = None


class GenerateCoverOut(BaseModel):
    cover_url: str


class GenerateCoverForStoryIn(BaseModel):
    image_model_id: int


class GenerateBackgroundForStoryIn(BaseModel):
    image_model_id: int


class GenerateBackgroundOut(BaseModel):
    background_image: str


class UploadImageOut(BaseModel):
    field: str
    path: str


class GenerateImageIn(BaseModel):
    archive_id: int
    size: Literal["1K", "2K", "3K"] = "2K"
    watermark: bool = False
    idempotency_key: str | None = None  # 客户端生成的 UUID，用于幂等去重


class GenerateImageOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    image_url: str
    message_id: int
    model_name: str = ""


# ---- Bulk Delete ----
class BulkDeleteRequest(BaseModel):
    message_ids: list[int]


class BulkDeleteResponse(BaseModel):
    deleted: int
