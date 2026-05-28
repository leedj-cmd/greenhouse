from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import Field

seed_router = APIRouter()

# 기본 구역 데이터 (a1~e4, 총 20개)
DEFAULT_FIELDS = [
    {"name": f"{row}{col}", "location": f"구역 {row.upper()}-{col}"}
    for row in ["a", "b", "c", "d", "e"]
    for col in [1, 2, 3, 4]
]

async def seed_fields(session: AsyncSession):
    """서버 시작 시 구역 데이터가 없으면 자동으로 생성합니다."""
    result = await session.execute(select(Field))
    existing = result.scalars().all()

    if not existing:
        for f in DEFAULT_FIELDS:
            session.add(Field(name=f["name"], location=f["location"]))
        await session.commit()
        print("✅ 기본 구역 데이터 생성 완료 (a1 ~ e1)")
    else:
        print(f"✅ 구역 데이터 확인: {len(existing)}개 존재")


# 수동 시드 엔드포인트
@seed_router.post("/admin/seed", tags=["admin"])
async def manual_seed():
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await seed_fields(session)
    return {"message": "시드 완료"}
