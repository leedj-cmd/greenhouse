from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import Field

seed_router = APIRouter()

# 기본 5개 밭 데이터
DEFAULT_FIELDS = [
    {"name": "1번 밭", "location": "구역 A - 북쪽"},
    {"name": "2번 밭", "location": "구역 B - 북동쪽"},
    {"name": "3번 밭", "location": "구역 C - 동쪽"},
    {"name": "4번 밭", "location": "구역 D - 남동쪽"},
    {"name": "5번 밭", "location": "구역 E - 남쪽"},
]

async def seed_fields(session: AsyncSession):
    """서버 시작 시 밭 데이터가 없으면 자동으로 5개 생성합니다."""
    result = await session.execute(select(Field))
    existing = result.scalars().all()

    if not existing:
        for f in DEFAULT_FIELDS:
            session.add(Field(name=f["name"], location=f["location"]))
        await session.commit()
        print("✅ 기본 밭 5개 데이터 생성 완료")
    else:
        print(f"✅ 밭 데이터 확인: {len(existing)}개 존재")


# 수동 시드 엔드포인트 (필요 시 호출)
@seed_router.post("/admin/seed", tags=["admin"])
async def manual_seed():
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await seed_fields(session)
    return {"message": "시드 완료"}
