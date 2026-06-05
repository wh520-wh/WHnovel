"""API 日志记录模块"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models


def _log_call(
    db: Session,
    *,
    request_id: str,
    archive_id: int | None,
    story_id: int,
    model_cfg: models.ModelConfig,
    success: bool,
    error_code: str = "",
    error_message: str = "",
    latency_ms: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_estimate: float = 0.0,
    is_stream: bool = False,
    stream_emitted_delta: bool = False,
    ttfb_ms: int = 0,
    fallback_used: bool = False,
    tail_valid: bool = False,
    error_stage: str = "",
    plot_label_generated: bool = False,
):
    db.add(
        models.ApiCallLog(
            request_id=request_id,
            archive_id=archive_id,
            story_id=story_id,
            model_config_id=model_cfg.id,
            model_name=model_cfg.model_id,
            success=1 if success else 0,
            error_code=error_code,
            error_message=error_message,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_estimate=cost_estimate,
            is_stream=1 if is_stream else 0,
            stream_emitted_delta=1 if stream_emitted_delta else 0,
            ttfb_ms=ttfb_ms,
            fallback_used=1 if fallback_used else 0,
            tail_valid=1 if tail_valid else 0,
            error_stage=error_stage,
            plot_label_generated=1 if plot_label_generated else 0,
        )
    )
    db.commit()
