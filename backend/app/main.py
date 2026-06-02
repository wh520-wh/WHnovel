from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import admin, archives, chat_router, images, settings, stories
from .database import Base, SessionLocal, engine
from .migrations import run_migrations
from .metrics_service import backfill_missing_hours, get_scheduler
from .seed_data import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化（替代模块导入时执行）
    Base.metadata.create_all(bind=engine)
    run_migrations()
    init_db()
    # Backfill any missed hourly metrics (up to 7 days)
    db = SessionLocal()
    try:
        backfill_missing_hours(db)
    finally:
        db.close()
    get_scheduler().start()
    yield
    # 关闭时清理
    get_scheduler().stop()


app = FastAPI(title='AI 情景互动小说平台 API', lifespan=lifespan)

# CORS：credentials=True 时不能使用 '*'
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5174',
        'http://127.0.0.1:5174',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={'detail': '服务器内部错误，请稍后重试'},
    )


app.include_router(stories.router)
app.include_router(chat_router.router)
app.include_router(archives.router)
app.include_router(settings.router)
app.include_router(admin.router)
app.include_router(images.router)


@app.get('/')
def root():
    return {'message': 'AI 情景互动小说平台 API', 'docs': '/docs'}
