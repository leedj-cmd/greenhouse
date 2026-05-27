from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.database import engine, Base, AsyncSessionLocal
from routers.api import router
from routers.seed import seed_router
import models.models  # 모델 임포트해야 테이블 인식됨

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 테이블 자동 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 밭 초기 데이터 자동 시드
    from routers.seed import seed_fields
    async with AsyncSessionLocal() as session:
        await seed_fields(session)

    yield

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

# 실행: uvicorn main:app --reload
