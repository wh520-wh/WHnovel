"""
JSON 备份文件读写模块。

当前运行时以数据库为唯一真相源；本模块仅用于显式备份/导出场景，
例如将当前 DB 配置导出到 `backend/config/user_config.json`。
pytest 等场景可通过环境变量切到独立备份文件，避免污染正式备份。
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

_DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "user_config.json"
_CONFIG_FILE = Path(os.environ.get("WHAINOEL_CONFIG_FILE") or _DEFAULT_CONFIG_FILE).resolve()
_CONFIG_DIR = _CONFIG_FILE.parent
_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

_cached_config: Optional[dict[str, Any]] = None


def _load_raw() -> dict[str, Any]:
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            bak = _CONFIG_FILE.with_suffix(".bak")
            shutil.copy2(_CONFIG_FILE, bak)
    return {}


def load_config() -> dict[str, Any]:
    global _cached_config
    if _cached_config is None:
        _cached_config = _load_raw()
    return _cached_config


def save_config(data: dict[str, Any]) -> None:
    global _cached_config
    tmp = _CONFIG_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(_CONFIG_FILE)
    finally:
        if tmp.exists():
            tmp.unlink()
    _cached_config = data


def get_model_configs() -> list[dict[str, Any]]:
    return load_config().get("models", [])


def set_model_configs(models: list[dict[str, Any]]) -> None:
    data = load_config()
    data["models"] = models
    save_config(data)


def get_app_settings() -> dict[str, Any]:
    return load_config().get("app_settings", {})


def set_app_settings(settings: dict[str, Any]) -> None:
    data = load_config()
    data["app_settings"] = settings
    data.setdefault("migration_version", 1)
    save_config(data)


def get_user_settings() -> dict[str, Any]:
    return load_config().get("user_settings", {})


def set_user_settings(settings: dict[str, Any]) -> None:
    data = load_config()
    data["user_settings"] = settings
    save_config(data)


def clear_cache() -> None:
    global _cached_config
    _cached_config = None
