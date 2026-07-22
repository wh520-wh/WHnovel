import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

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
# expire_on_commit=False：流式响应（StreamingResponse）生成器迭代时路由 session 已关闭，
# commit 后对象不再 expire，避免生成器访问 story/settings 等属性时 DetachedInstanceError（Bug #47）。
# 单请求内 commit 后对象属性即为刚写入值，无需 expire 重读；跨请求不共享 session，无 stale 风险。
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
