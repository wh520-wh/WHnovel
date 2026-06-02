"""
pytest fixtures：每个测试后自动清理，保持 DB 干净。
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import pytest
from sqlalchemy import text
from uuid import uuid4


TEST_RUNTIME_PARENT = Path(__file__).resolve().parent.parent / ".pytest_runtime"
TEST_RUNTIME_ROOT = TEST_RUNTIME_PARENT / f"session_{uuid4().hex}"


def _prepare_isolated_test_runtime() -> None:
    """
    为 pytest 准备独立运行目录，避免测试污染正式数据库与 JSON 配置备份。
    必须在导入 app.database / app.config 之前执行。
    """
    TEST_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

    os.environ["WHAINOEL_DB_PATH"] = str((TEST_RUNTIME_ROOT / "data.db").resolve())
    os.environ["WHAINOEL_CONFIG_FILE"] = str((TEST_RUNTIME_ROOT / "user_config.json").resolve())
    os.environ["WHAINOEL_DATA_DIR"] = str((TEST_RUNTIME_ROOT / "data").resolve())
    os.environ["REDIS_PORT"] = "0"


_prepare_isolated_test_runtime()

from app.database import Base, SessionLocal, engine
from app.migrations import run_migrations
from app.seed_data import init_db


@pytest.fixture(scope="session", autouse=True)
def _ensure_migrations():
    """确保 DB 迁移到最新版本（测试与生产 schema 同步）。"""
    # 先创建所有表，再执行增量迁移
    Base.metadata.create_all(bind=engine)
    run_migrations()
    init_db()
    yield
    shutil.rmtree(TEST_RUNTIME_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def _cleanup_test_data():
    """每个测试函数执行后自动清理，避免用例之间相互污染。"""
    yield

    db = SessionLocal()
    try:
        with db.begin():
            db.execute(text("DELETE FROM model_configs"))
            db.execute(text("UPDATE user_settings SET primary_model_id = NULL, backup_model_ids = '[]'"))
    finally:
        db.close()
