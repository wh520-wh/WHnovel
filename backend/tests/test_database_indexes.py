"""Tests for database indexes used by hot query paths."""

from __future__ import annotations

from app.database import engine


def _indexed_columns(table: str) -> set[tuple[str, ...]]:
    with engine.connect() as conn:
        raw = conn.connection.driver_connection
        columns: set[tuple[str, ...]] = set()
        for row in raw.execute(f"PRAGMA index_list({table})").fetchall():
            index_name = row[1]
            info = raw.execute(f"PRAGMA index_info({index_name})").fetchall()
            columns.add(tuple(item[2] for item in info))
        return columns


def test_hot_path_foreign_keys_and_metric_filters_are_indexed():
    expected = {
        "api_call_logs": {("created_at",), ("archive_id",), ("story_id",), ("model_config_id",)},
        "characters": {("story_id",)},
        "archives": {("story_id",)},
        "story_nodes": {("archive_id",), ("message_id",)},
    }

    for table, required_indexes in expected.items():
        assert required_indexes <= _indexed_columns(table)
