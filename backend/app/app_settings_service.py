from __future__ import annotations

from sqlalchemy.orm import Session

from . import models
from .prompts.defaults import (
    DEFAULT_SYSTEM_PROMPT_TEXT,
    DEFAULT_STATE_BROADCAST_PROMPT,
    infer_prompt_source,
)


def ensure_app_settings(db: Session) -> models.AppSettings:
    settings = db.query(models.AppSettings).first()
    if not settings:
        settings = models.AppSettings(
            default_system_prompt="",
            state_broadcast_prompt=DEFAULT_STATE_BROADCAST_PROMPT,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    changed = False

    if not (settings.default_system_prompt or "").strip() and DEFAULT_SYSTEM_PROMPT_TEXT:
        settings.default_system_prompt = DEFAULT_SYSTEM_PROMPT_TEXT
        changed = True

    if not (settings.state_broadcast_prompt or "").strip():
        settings.state_broadcast_prompt = DEFAULT_STATE_BROADCAST_PROMPT
        changed = True

    if changed:
        db.commit()
        db.refresh(settings)

    return settings
