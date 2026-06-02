from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    cover_image = Column(String(500), default="")
    background_image = Column(String(500), default="", server_default="")
    description = Column(Text, default="")
    tags = Column(JSON, default=list)  # ["恋爱", "校园"]
    category = Column(String(50), default="其他")
    world_setting = Column(Text, default="")
    system_prompt = Column(Text, default="")
    state_config = Column(JSON, default=list)
    opening_requirement = Column(Text, default="")
    image_style = Column(String(500), default="")  # 图片风格描述，AI生成或用户填写
    # state_config 格式: [{"key": "hp", "label": "生命值", "type": "number", "default": 100, "max": 100}, ...]
    created_at = Column(DateTime, default=datetime.now)

    characters = relationship("Character", back_populates="story", cascade="all, delete-orphan")
    archives = relationship("Archive", back_populates="story", cascade="all, delete-orphan")


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
        Index("ix_characters_story_id", "story_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    name = Column(String(50), nullable=False)
    personality = Column(Text, default="")
    background = Column(Text, default="")
    avatar = Column(String(500), default="")

    story = relationship("Story", back_populates="characters")


class Archive(Base):
    __tablename__ = "archives"
    __table_args__ = (
        Index("ix_archives_story_id", "story_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    name = Column(String(100), default="自动存档")
    state_data = Column(JSON, default=dict)  # 当前状态快照
    story_state = Column(JSON, default=dict)  # 剧情结构化状态
    memory_log = Column(JSON, default=list)  # 记忆更新日志（按时间追加）
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    first_message = Column(Text, default="")  # 首条用户消息预览

    story = relationship("Story", back_populates="archives")
    messages = relationship("ChatMessage", back_populates="archive", cascade="all, delete-orphan")
    nodes = relationship("StoryNode", back_populates="archive", cascade="all, delete-orphan")


class StoryNode(Base):
    """剧情节点表 - 存储 AI 生成的剧情标签节点"""
    __tablename__ = "story_nodes"
    __table_args__ = (
        Index("ix_story_nodes_archive_id", "archive_id"),
        Index("ix_story_nodes_message_id", "message_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    archive_id = Column(Integer, ForeignKey("archives.id"), nullable=False)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    plot_label = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    archive = relationship("Archive", back_populates="nodes")
    message = relationship("ChatMessage")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index('ix_chat_messages_archive_created', 'archive_id', 'created_at'),
        Index('ix_chat_messages_archive_idempotency', 'archive_id', 'idempotency_key', unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    archive_id = Column(Integer, ForeignKey("archives.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    state_snapshot = Column(JSON, default=dict)
    story_state = Column(JSON, default=dict)
    options = Column(JSON, default=list)  # AI返回的快捷选项
    memory_update = Column(JSON, default=list)
    image_url = Column(String(500), nullable=True)  # 对话内生成的图片URL
    is_draft = Column(Integer, default=0)  # 1=草稿（流式失败的部分内容）
    idempotency_key = Column(String(64), nullable=True)  # 图片生成幂等去重
    plot_label = Column(String(100), nullable=True)  # 剧情标签（如"获得洪荒之力"）
    is_state_broadcast = Column(Integer, default=0)  # 1=状态播报消息
    model_name = Column(String(100), default="")  # 生成此消息的模型名称/ID
    created_at = Column(DateTime, default=datetime.now)

    archive = relationship("Archive", back_populates="messages")
    story_node = relationship("StoryNode", back_populates="message", uselist=False)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), default="gpt-3.5-turbo")
    api_base_url = Column(String(500), default="https://api.openai.com/v1")
    api_key = Column(String(500), default="")
    context_length = Column(Integer, default=10)
    reply_style = Column(String(50), default="detailed")  # detailed/concise/creative
    primary_model_id = Column(Integer, ForeignKey("model_configs.id"), nullable=True)
    backup_model_ids = Column(JSON, default=list)
    auto_generate_options = Column(Integer, default=1)
    theme = Column(String(20), default="dark")
    options_prompt = Column(Text, nullable=True)
    copy_image_format = Column(String(20), default="url")
    disable_chat_bubble_elastic = Column(Integer, default=0)
    show_background_image = Column(Integer, default=1)


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # 显示名称
    model_id = Column(String(100), nullable=False)  # 模型ID
    api_base_url = Column(String(500), nullable=False)
    api_key = Column(String(500), default="")
    enabled = Column(Integer, default=1)
    priority = Column(Integer, default=100)
    price_input_per_1k = Column(Float, default=0.0)
    price_output_per_1k = Column(Float, default=0.0)
    pricing_unit = Column(String(10), default="per_1k")  # "per_1k" | "per_1m"
    model_type = Column(String(20), default="chat")  # "chat" | "image"
    image_api_key = Column(String(500), default="")  # 图片模型专用 API Key（加密存储）
    image_api_base = Column(String(500), default="")  # 图片模型 API Base URL
    ssl_verify = Column(Boolean, default=True, nullable=False)
    api_mode = Column(String(50), default="openai_chat_completions")
    image_api_mode = Column(String(50), default="openai_images")
    image_workflow_template = Column(Text, nullable=True)  # ComfyUI workflow JSON template
    temperature = Column(Float, nullable=True)  # None = use style-based default
    max_tokens = Column(Integer, nullable=True)  # None = no limit
    response_format_mode = Column(String(20), default="json_schema")  # "json_schema" | "json_object"


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    default_system_prompt = Column(Text, default="")
    state_broadcast_prompt = Column(Text, default="")
    enable_image_generation = Column(Integer, default=1)  # 全局开关，默认开启
    default_image_model_id = Column(Integer, ForeignKey("model_configs.id"), nullable=True)
    image_size = Column(String(10), default="2K")  # "1K" | "2K"
    image_watermark = Column(Integer, default=0)  # 水印开关，默认关闭
    style_skill_enabled = Column(Integer, default=0)  # 0=off, 1=on
    style_skill_content = Column(Text, default="")  # Skill prompt content
    default_image_style = Column(String(500), default="唯美、氛围感强，适合作为小说封面")  # 全局默认画风
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ApiCallLog(Base):
    __tablename__ = "api_call_logs"
    __table_args__ = (
        Index("ix_api_call_logs_created_at", "created_at"),
        Index("ix_api_call_logs_archive_id", "archive_id"),
        Index("ix_api_call_logs_story_id", "story_id"),
        Index("ix_api_call_logs_model_config_id", "model_config_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(64), nullable=False, index=True)
    archive_id = Column(Integer, ForeignKey("archives.id"), nullable=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=True)
    model_config_id = Column(Integer, ForeignKey("model_configs.id"), nullable=True)
    model_name = Column(String(100), default="")
    success = Column(Integer, default=0)
    error_code = Column(String(100), default="")
    error_message = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_estimate = Column(Float, default=0.0)
    is_stream = Column(Integer, default=0)
    stream_emitted_delta = Column(Integer, default=0)
    ttfb_ms = Column(Integer, default=0)
    fallback_used = Column(Integer, default=0)
    tail_valid = Column(Integer, default=0)
    error_stage = Column(String(64), default="")
    plot_label_generated = Column(Integer, default=0)  # 1=本次响应生成了剧情标签
    created_at = Column(DateTime, default=datetime.now)


class MetricsHourly(Base):
    __tablename__ = "metrics_hourly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hour = Column(String(16), nullable=False)  # 'YYYY-MM-DD HH:00'
    model_config_id = Column(Integer, ForeignKey("model_configs.id"), nullable=True)
    total_calls = Column(Integer, default=0)
    success_calls = Column(Integer, default=0)
    total_latency_ms = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    plot_label_calls = Column(Integer, default=0)  # 产生剧情标签的调用次数
    plot_label_cost = Column(Float, default=0.0)  # 剧情标签调用总费用
    created_at = Column(DateTime, default=datetime.now)
