from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

from core.database import engine, Base, AsyncSessionLocal
from routers.api import router
from routers.seed import seed_router
from schemas.schemas import HealthResponse
import models.models  # 모델 임포트해야 테이블 인식됨
import scheduler as _scheduler

UPLOAD_DIR = os.getenv("IMAGE_UPLOAD_DIR", "./uploaded_images")
ADMIN_DIR = Path(__file__).resolve().parent.parent / "admin"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 테이블 자동 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 밭 초기 데이터 자동 시드
    from routers.seed import seed_fields
    async with AsyncSessionLocal() as session:
        await seed_fields(session)

    # 일일 자동 캡처 스케줄러 시작
    _scheduler.start()

    yield

    # 종료 시 스케줄러 정리
    _scheduler.shutdown()

app = FastAPI(
    title="비닐하우스 질병감지 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — Flutter 앱(Android/iOS 에뮬레이터 포함) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(seed_router)


# ── 헬스체크 ──────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health():
    return HealthResponse(status="ok", timestamp=datetime.now(timezone.utc))


# ── 일일 캡처 수동 트리거 (테스트용) ─────────────────────────────────────────
@app.post("/admin/run-daily-capture", tags=["admin"])
async def trigger_daily_capture():
    """매일 14:00 KST에 자동 실행되는 캡처 작업을 즉시 수행."""
    return await _scheduler.run_daily_capture()


# ── 정적 파일 서빙 ────────────────────────────────────────────────────────────
# 업로드된 분석 이미지 (/images/<uuid>.jpg)
app.mount("/images", StaticFiles(directory=UPLOAD_DIR), name="images")

# 관리자 대시보드 (admin/index.html → http://host/admin)
if ADMIN_DIR.is_dir():
    app.mount("/admin", StaticFiles(directory=str(ADMIN_DIR), html=True), name="admin")


# ── 루트 → 관리자 대시보드로 리다이렉트 ─────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/admin/")


# 실행: uvicorn main:app --reload
