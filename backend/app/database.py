import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# 默认使用固定绝对路径，防止不同工作目录启动时连到不同 DB。
# pytest 等场景可通过环境变量切到独立测试库，避免污染正式数据。
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data.db"
DB_PATH = Path(os.environ.get("WHAINOEL_DB_PATH") or _DEFAULT_DB_PATH).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
