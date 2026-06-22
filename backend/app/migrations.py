from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .database import DB_PATH

SCHEMA_VERSION = 28


def _ensure_schema_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    row = conn.execute("SELECT version FROM schema_meta WHERE id = 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_meta (id, version) VALUES (1, 0)")
        conn.commit()


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_meta WHERE id = 1").fetchone()
    return int(row[0]) if row else 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "UPDATE schema_meta SET version = ?, updated_at = ? WHERE id = 1",
        (version, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if not _has_column(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _drop_column_if_exists(conn: sqlite3.Connection, table: str, column: str) -> None:
    if _has_column(conn, table, column):
        try:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        except Exception:
            pass


def _migrate_to_v9(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn,
        "stories",
        "opening_requirement",
        "opening_requirement TEXT NOT NULL DEFAULT ''",
    )
    conn.commit()


def _migrate_to_v10(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn,
        "chat_messages",
        "image_url",
        "image_url TEXT",
    )
    conn.commit()


def _migrate_to_v11(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn,
        "chat_messages",
        "idempotency_key",
        "idempotency_key TEXT",
    )
    conn.commit()


def _migrate_to_v12(conn: sqlite3.Connection) -> None:
    # 将现有 AppSettings 行启用图片生成（默认从 0 改为 1）
    conn.execute(
        "UPDATE app_settings SET enable_image_generation = 1 WHERE enable_image_generation = 0"
    )
    conn.commit()


def _migrate_to_v13(conn: sqlite3.Connection) -> None:
    # 唯一索引防止图片生成幂等竞态：同一 archive 内相同 idempotency_key 只能有一条记录
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_chat_messages_archive_idempotency ON chat_messages(archive_id, idempotency_key)"
    )
    conn.commit()


def _migrate_to_v14(conn: sqlite3.Connection) -> None:
    # chat_messages.plot_label: 剧情标签列，v1-v13 均未添加
    _add_column_if_missing(
        conn,
        "chat_messages",
        "plot_label",
        "plot_label VARCHAR(100)",
    )
    # metrics_hourly.plot_label_calls / plot_label_cost: v6 建表时漏掉
    _add_column_if_missing(
        conn,
        "metrics_hourly",
        "plot_label_calls",
        "plot_label_calls INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "metrics_hourly",
        "plot_label_cost",
        "plot_label_cost REAL NOT NULL DEFAULT 0.0",
    )
    conn.commit()


def _migrate_to_v15(conn: sqlite3.Connection) -> None:
    # chat_messages.model_name: 生成此消息的模型名称
    _add_column_if_missing(
        conn,
        "chat_messages",
        "model_name",
        "model_name VARCHAR(100) NOT NULL DEFAULT ''",
    )
    # 状态播报提示词迁移：旧格式（叙事格式）→ 新格式（键值对）
    new_prompt = (
        "请以紧凑的键值对格式输出角色状态面板，每行一个属性，格式为：属性名 | 属性值。\n\n"
        "必须包含的固定属性（若无数据则省略该项）：\n"
        "- 地点 | 当前所在地点\n"
        "- 时间 | 当前时间/轮次\n"
        "- 生命 | 生命值（如有）\n"
        "- 情绪 | 当前情绪/心理状态\n"
        "- 等级 | 角色等级（如有）\n"
        "- 技能 | 关键技能（如有）\n"
        "- 资源 | 携带资源/物品（如有）\n"
        "- 目标 | 当前剧情目标\n"
        "- 关系 | 关键NPC关系（最多3条）\n\n"
        "示例：\n"
        "地点 | 废弃神社后院\n"
        "时间 | 子夜\n"
        "生命 | 72/100\n"
        "情绪 | 警觉中带着不安\n"
        "关系 | 千夏 - 互相猜忌\n\n"
        "仅输出面板内容，不要任何解释或描述。"
    )
    row = conn.execute("SELECT state_broadcast_prompt FROM app_settings WHERE id = 1").fetchone()
    if row:
        old = (row[0] or "").strip()
        # 仅当包含旧格式特征关键词时才迁移
        if old and ("分区结构" in old or "每个分区" in old or "1-3条" in old):
            conn.execute(
                "UPDATE app_settings SET state_broadcast_prompt = ? WHERE id = 1",
                (new_prompt,),
            )
    conn.commit()


def _migrate_to_v16(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn,
        "user_settings",
        "disable_chat_bubble_elastic",
        "disable_chat_bubble_elastic INTEGER NOT NULL DEFAULT 0",
    )
    conn.commit()


def _migrate_to_v17(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn,
        "model_configs",
        "api_mode",
        "api_mode TEXT NOT NULL DEFAULT 'openai_chat_completions'",
    )
    _add_column_if_missing(
        conn,
        "model_configs",
        "image_api_mode",
        "image_api_mode TEXT NOT NULL DEFAULT 'openai_images'",
    )
    # 现有图片模型使用豆包原生接口，标记为 custom_image
    conn.execute(
        "UPDATE model_configs SET image_api_mode = 'custom_image' WHERE model_type = 'image'"
    )
    conn.commit()


def _migrate_to_v18(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn,
        "model_configs",
        "pricing_unit",
        "pricing_unit TEXT NOT NULL DEFAULT 'per_1k'",
    )
    # 存量行可能为 NULL（旧 SQLite 版本），统一回填
    conn.execute(
        "UPDATE model_configs SET pricing_unit = 'per_1k' WHERE pricing_unit IS NULL OR pricing_unit = ''"
    )
    conn.commit()


def _migrate_to_v19(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn,
        "model_configs",
        "temperature",
        "temperature REAL",
    )
    _add_column_if_missing(
        conn,
        "model_configs",
        "max_tokens",
        "max_tokens INTEGER",
    )
    _add_column_if_missing(
        conn,
        "app_settings",
        "style_skill_enabled",
        "style_skill_enabled INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "app_settings",
        "style_skill_content",
        "style_skill_content TEXT NOT NULL DEFAULT ''",
    )
    conn.commit()


def _migrate_to_v20(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(
        conn, "stories", "background_image", "background_image VARCHAR(500) NOT NULL DEFAULT ''"
    )
    conn.commit()


def _migrate_to_v21(conn: sqlite3.Connection) -> None:
    _drop_column_if_exists(conn, "model_configs", "is_default")
    _drop_column_if_exists(
        conn,
        "app_settings",
        "first_primary_model_id",
    )
    _drop_column_if_exists(
        conn,
        "app_settings",
        "first_backup_model_ids",
    )
    conn.commit()


def _migrate_to_v26(conn: sqlite3.Connection) -> None:
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_api_call_logs_created_at ON api_call_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_api_call_logs_archive_id ON api_call_logs(archive_id)",
        "CREATE INDEX IF NOT EXISTS ix_api_call_logs_story_id ON api_call_logs(story_id)",
        "CREATE INDEX IF NOT EXISTS ix_api_call_logs_model_config_id ON api_call_logs(model_config_id)",
        "CREATE INDEX IF NOT EXISTS ix_characters_story_id ON characters(story_id)",
        "CREATE INDEX IF NOT EXISTS ix_archives_story_id ON archives(story_id)",
        "CREATE INDEX IF NOT EXISTS ix_story_nodes_archive_id ON story_nodes(archive_id)",
        "CREATE INDEX IF NOT EXISTS ix_story_nodes_message_id ON story_nodes(message_id)",
    ]
    for ddl in indexes:
        conn.execute(ddl)
    conn.commit()


def _migrate_to_v8(conn: sqlite3.Connection) -> None:
    # Composite index on ChatMessage for archive_id + created_at queries
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_messages_archive_created ON chat_messages(archive_id, created_at)"
    )
    conn.commit()


def _migrate_to_v7(conn: sqlite3.Connection) -> None:
    # ModelConfig: model_type, image_api_key, image_api_base
    _add_column_if_missing(
        conn,
        "model_configs",
        "model_type",
        "model_type TEXT NOT NULL DEFAULT 'chat'",
    )
    _add_column_if_missing(
        conn,
        "model_configs",
        "image_api_key",
        "image_api_key TEXT NOT NULL DEFAULT ''",
    )
    _add_column_if_missing(
        conn,
        "model_configs",
        "image_api_base",
        "image_api_base TEXT NOT NULL DEFAULT ''",
    )
    # AppSettings: image generation fields
    _add_column_if_missing(
        conn,
        "app_settings",
        "enable_image_generation",
        "enable_image_generation INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "app_settings",
        "default_image_model_id",
        "default_image_model_id INTEGER",
    )
    _add_column_if_missing(
        conn,
        "app_settings",
        "image_size",
        "image_size TEXT NOT NULL DEFAULT '2K'",
    )
    _add_column_if_missing(
        conn,
        "app_settings",
        "image_watermark",
        "image_watermark INTEGER NOT NULL DEFAULT 1",
    )
    conn.commit()


def _migrate_to_v6(conn: sqlite3.Connection) -> None:
    # 1. ChatMessage.is_draft - marks partial/failed stream messages
    _add_column_if_missing(
        conn,
        "chat_messages",
        "is_draft",
        "is_draft INTEGER NOT NULL DEFAULT 0",
    )
    # 2. Archive.first_message - preview of first user message
    _add_column_if_missing(
        conn,
        "archives",
        "first_message",
        "first_message TEXT NOT NULL DEFAULT ''",
    )
    # 3. metrics_hourly - pre-aggregated hourly metrics
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics_hourly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour TEXT NOT NULL,           -- ISO format: 'YYYY-MM-DD HH:00'
            model_config_id INTEGER,
            total_calls INTEGER NOT NULL DEFAULT 0,
            success_calls INTEGER NOT NULL DEFAULT 0,
            total_latency_ms INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            total_cost REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(hour, model_config_id)
        )
        """
    )
    conn.commit()


def _migrate_to_v1(conn: sqlite3.Connection) -> None:
    # User-level toggle: automatic option generation
    _add_column_if_missing(
        conn,
        "user_settings",
        "auto_generate_options",
        "auto_generate_options INTEGER NOT NULL DEFAULT 1",
    )
    conn.commit()


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    # Stream observability fields for api_call_logs
    _add_column_if_missing(
        conn,
        "api_call_logs",
        "is_stream",
        "is_stream INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "api_call_logs",
        "stream_emitted_delta",
        "stream_emitted_delta INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "api_call_logs",
        "ttfb_ms",
        "ttfb_ms INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "api_call_logs",
        "fallback_used",
        "fallback_used INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "api_call_logs",
        "tail_valid",
        "tail_valid INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(
        conn,
        "api_call_logs",
        "error_stage",
        "error_stage TEXT NOT NULL DEFAULT ''",
    )
    conn.commit()


def _migrate_to_v27(conn: sqlite3.Connection) -> None:
    """v27: UserSettings 加 memory_inject_count 列（默认 50）。"""
    _add_column_if_missing(
        conn,
        "user_settings",
        "memory_inject_count",
        "memory_inject_count INTEGER NOT NULL DEFAULT 50",
    )
    conn.commit()


def _migrate_to_v28(conn: sqlite3.Connection) -> None:
    """v28: ChatMessage 加 pre_state_data / pre_story_state / pre_memory_log 三字段（撤回回滚用）。"""
    # SQLite JSON 列以 TEXT 存储，DEFAULT 用 JSON 字符串字面量；Python 端 Column default=dict/list 兜底。
    _add_column_if_missing(
        conn,
        "chat_messages",
        "pre_state_data",
        "pre_state_data JSON NOT NULL DEFAULT '{}'",
    )
    _add_column_if_missing(
        conn,
        "chat_messages",
        "pre_story_state",
        "pre_story_state JSON NOT NULL DEFAULT '{}'",
    )
    _add_column_if_missing(
        conn,
        "chat_messages",
        "pre_memory_log",
        "pre_memory_log JSON NOT NULL DEFAULT '[]'",
    )
    conn.commit()


def _backup_db_file(db_path: Path) -> Path | None:
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None
    backup_dir = db_path.parent / "db_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


def run_migrations() -> None:
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    probe_conn = sqlite3.connect(str(db_path))
    try:
        _ensure_schema_meta(probe_conn)
        if _current_version(probe_conn) >= SCHEMA_VERSION:
            return
    finally:
        probe_conn.close()

    backup_path = _backup_db_file(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_schema_meta(conn)
        version = _current_version(conn)
        if version < 1:
            _migrate_to_v1(conn)
            _set_version(conn, 1)
            version = 1
        if version < 2:
            _migrate_to_v2(conn)
            _set_version(conn, 2)
            version = 2
        if version < 3:
            _add_column_if_missing(
                conn,
                "app_settings",
                "state_broadcast_prompt",
                "state_broadcast_prompt TEXT NOT NULL DEFAULT ''",
            )
            conn.commit()
            _set_version(conn, 3)
        if version < 4:
            _add_column_if_missing(
                conn,
                "model_configs",
                "ssl_verify",
                "ssl_verify INTEGER NOT NULL DEFAULT 1",
            )
            conn.commit()
            _set_version(conn, 4)
        if version < 5:
            _add_column_if_missing(
                conn,
                "user_settings",
                "options_prompt",
                "options_prompt TEXT",
            )
            conn.commit()
            _set_version(conn, 5)
        if version < 6:
            _migrate_to_v6(conn)
            _set_version(conn, 6)
        if version < 7:
            _migrate_to_v7(conn)
            _set_version(conn, 7)
        if version < 8:
            _migrate_to_v8(conn)
            _set_version(conn, 8)
        if version < 9:
            _migrate_to_v9(conn)
            _set_version(conn, 9)
        if version < 10:
            _migrate_to_v10(conn)
            _set_version(conn, 10)
        if version < 11:
            _migrate_to_v11(conn)
            _set_version(conn, 11)
        if version < 12:
            _migrate_to_v12(conn)
            _set_version(conn, 12)
        if version < 13:
            _migrate_to_v13(conn)
            _set_version(conn, 13)
        if version < 14:
            _migrate_to_v14(conn)
            _set_version(conn, 14)
        if version < 15:
            _migrate_to_v15(conn)
            _set_version(conn, 15)
            version = 15
        if version < 16:
            _migrate_to_v16(conn)
            _set_version(conn, 16)
        if version < 17:
            _migrate_to_v17(conn)
            _set_version(conn, 17)
        if version < 18:
            _migrate_to_v18(conn)
            _set_version(conn, 18)
        if version < 19:
            _migrate_to_v19(conn)
            _set_version(conn, 19)
        if version < 20:
            _migrate_to_v20(conn)
            _set_version(conn, 20)
        if version < 21:
            _migrate_to_v21(conn)
            _set_version(conn, 21)
        if version < 22:
            _add_column_if_missing(
                conn,
                "model_configs",
                "image_workflow_template",
                "image_workflow_template TEXT",
            )
            conn.commit()
            _set_version(conn, 22)
        if version < 23:
            _add_column_if_missing(
                conn,
                "user_settings",
                "show_background_image",
                "show_background_image INTEGER NOT NULL DEFAULT 1",
            )
            conn.commit()
            _set_version(conn, 23)
        if version < 24:
            _add_column_if_missing(
                conn,
                "model_configs",
                "response_format_mode",
                "response_format_mode TEXT NOT NULL DEFAULT 'json_schema'",
            )
            conn.commit()
            _set_version(conn, 24)
        if version < 25:
            _add_column_if_missing(
                conn,
                "chat_messages",
                "is_state_broadcast",
                "is_state_broadcast INTEGER NOT NULL DEFAULT 0",
            )
            conn.commit()
            _set_version(conn, 25)
        if version < 26:
            _migrate_to_v26(conn)
            _set_version(conn, 26)
        if version < 27:
            _migrate_to_v27(conn)
            _set_version(conn, 27)
        if version < 28:
            _migrate_to_v28(conn)
            _set_version(conn, 28)
    except Exception:
        conn.close()
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, db_path)
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
