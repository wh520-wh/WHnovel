"""
Metrics aggregation service.
Aggregates api_call_logs into metrics_hourly table for fast metric queries.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Integer, case, func
from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal

logger = logging.getLogger(__name__)


def _get_previous_hour() -> str:
    """Return the previous hour in 'YYYY-MM-DD HH:00' format."""
    prev = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    return prev.strftime("%Y-%m-%d %H:00")


def aggregate_hourly_metrics(db: Session, hour: str | None = None) -> int:
    """
    Aggregate api_call_logs for the given hour (or previous hour if not specified)
    and upsert into metrics_hourly table.

    Returns the number of rows inserted/updated.
    """
    if hour is None:
        hour = _get_previous_hour()

    rows = (
        db.query(
            models.ApiCallLog.model_config_id.label("model_config_id"),
            func.count(models.ApiCallLog.id).label("total_calls"),
            func.sum(models.ApiCallLog.success).label("success_calls"),
            func.sum(models.ApiCallLog.latency_ms).label("total_latency_ms"),
            func.sum(models.ApiCallLog.total_tokens).label("total_tokens"),
            func.sum(models.ApiCallLog.cost_estimate).label("total_cost"),
            func.sum(func.cast(models.ApiCallLog.plot_label_generated, Integer)).label("plot_label_calls"),
            func.sum(
                case(
                    (models.ApiCallLog.plot_label_generated == 1, models.ApiCallLog.cost_estimate),
                    else_=0.0,
                )
            ).label("plot_label_cost"),
        )
        .filter(
            func.strftime("%Y-%m-%d %H:00", models.ApiCallLog.created_at) == hour
        )
        .group_by(models.ApiCallLog.model_config_id)
        .all()
    )

    if not rows:
        return 0

    count = 0
    for r in rows:
        existing = (
            db.query(models.MetricsHourly)
            .filter(
                models.MetricsHourly.hour == hour,
                models.MetricsHourly.model_config_id == r.model_config_id,
            )
            .first()
        )
        if existing:
            existing.total_calls = int(r.total_calls or 0)
            existing.success_calls = int(r.success_calls or 0)
            existing.total_latency_ms = int(r.total_latency_ms or 0)
            existing.total_tokens = int(r.total_tokens or 0)
            existing.total_cost = float(r.total_cost or 0.0)
            existing.plot_label_calls = int(r.plot_label_calls or 0)
            existing.plot_label_cost = float(r.plot_label_cost or 0.0)
        else:
            mh = models.MetricsHourly(
                hour=hour,
                model_config_id=r.model_config_id,
                total_calls=int(r.total_calls or 0),
                success_calls=int(r.success_calls or 0),
                total_latency_ms=int(r.total_latency_ms or 0),
                total_tokens=int(r.total_tokens or 0),
                total_cost=float(r.total_cost or 0.0),
                plot_label_calls=int(r.plot_label_calls or 0),
                plot_label_cost=float(r.plot_label_cost or 0.0),
            )
            db.add(mh)
        count += 1

    db.commit()
    logger.info(f"Aggregated metrics for {hour}: {count} model(s)")
    return count


def backfill_missing_hours(db: Session, max_hours: int = 168) -> int:
    """
    Backfill metrics for missing hours (up to max_hours, default 7 days).
    Returns total number of rows aggregated across all missing hours.
    """
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    existing_hours = set(
        r.hour for r in db.query(models.MetricsHourly.hour).distinct().all()
    )

    total_rows = 0
    for i in range(1, max_hours + 1):
        h = now - timedelta(hours=i)
        hour_str = h.strftime("%Y-%m-%d %H:00")
        if hour_str in existing_hours:
            continue
        count = aggregate_hourly_metrics(db, hour_str)
        total_rows += count

    if total_rows > 0:
        logger.info(f"Backfill complete: aggregated {total_rows} rows across missing hours")
    return total_rows


def _run_aggregation_cycle() -> None:
    """Run aggregation for the previous hour. Called by scheduler."""
    db = SessionLocal()
    try:
        aggregate_hourly_metrics(db)
    except Exception as e:
        logger.error(f"Metrics aggregation failed: {e}")
    finally:
        db.close()


class BackgroundScheduler:
    """
    Simple hourly scheduler using threading.Timer.
    Runs aggregation every hour (on the hour + small jitter).
    """
    _instance: Optional['BackgroundScheduler'] = None

    def __new__(cls):
        if cls._instance is not None:
            return cls._instance
        cls._instance = super().__new__(cls)
        cls._instance._started = False
        cls._instance._timer: Optional[threading.Timer] = None
        return cls._instance

    def _schedule_next(self):
        """Schedule next run at the top of the next hour + 30s jitter."""
        now = datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        delay = (next_hour - now).total_seconds() + 30  # 30s after the hour
        self._timer = threading.Timer(delay, self._run_and_reschedule)
        self._timer.daemon = True
        self._timer.start()

    def _run_and_reschedule(self):
        _run_aggregation_cycle()
        self._schedule_next()

    def start(self):
        if self._started:
            return
        self._started = True
        logger.info("Starting metrics aggregation scheduler")
        self._schedule_next()

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._started = False


_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler
