from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from uuid import UUID
import os, shutil, uuid, random

from core.database import get_db
from models.models import AnalysisResult, Image, Field, Notification
from schemas.schemas import (
    AnalyzeResponse, HistoryItem, FieldResponse,
    NotificationResponse, ImageItem, LatestAnalysis
)

router = APIRouter()

UPLOAD_DIR = os.getenv("IMAGE_UPLOAD_DIR", "./uploaded_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── POST /analyze ─────────────────────────────────────────────────────────────
# 구역 ID + 이미지를 받아 AI 분석 후 결과 저장
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_image(
    field_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. 구역 존재 확인
    field = await db.get(Field, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="구역을 찾을 수 없습니다.")

    # 2. 이미지 저장
    ext = os.path.splitext(file.filename)[-1] or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    file_size_kb = os.path.getsize(file_path) // 1024

    # 3. images 테이블에 저장
    image = Image(file_path=f"/images/{filename}", file_size_kb=file_size_kb)
    db.add(image)
    await db.flush()

    # 4. AI 분석
    # TODO: ML팀 TFLite 모델 완성 시 _mock_analyze() 함수를 교체하세요
    disease_type, confidence = _mock_analyze()

    # 5. analysis_results 저장
    result = AnalysisResult(
        field_id=field_id,
        image_id=image.id,
        disease_type=disease_type,
        confidence=confidence,
    )
    db.add(result)
    await db.flush()

    # 6. 질병 감지 시 알림 생성 + 구역 상태 업데이트
    notification_sent = False
    if disease_type != "NORMAL":
        notif = Notification(
            field_id=field_id,
            analysis_id=result.id,
            message=f"[{field.name}] {disease_type} 감지됨 (신뢰도: {confidence:.0%})",
        )
        db.add(notif)
        field.status = "DANGER" if confidence > 0.8 else "WARNING"
        notification_sent = True
    else:
        field.status = "NORMAL"

    await db.commit()
    await db.refresh(result)

    return AnalyzeResponse(
        id=result.id,
        field_id=result.field_id,
        image_id=result.image_id,
        disease_type=result.disease_type,
        confidence=result.confidence,
        analyzed_at=result.analyzed_at,
        notification_sent=notification_sent,
    )


# ── GET /fields ───────────────────────────────────────────────────────────────
# 전체 구역 목록 + 각 구역의 최신 분석 결과 포함 (Farm 화면 메인)
@router.get("/fields", response_model=List[FieldResponse])
async def get_all_fields(db: AsyncSession = Depends(get_db)):
    fields_result = await db.execute(select(Field).order_by(Field.name))
    fields = fields_result.scalars().all()

    response = []
    for field in fields:
        # 해당 구역의 최신 분석 결과 1건 조회
        latest_result = await db.execute(
            select(AnalysisResult, Image.file_path)
            .join(Image, AnalysisResult.image_id == Image.id)
            .where(AnalysisResult.field_id == field.id)
            .order_by(desc(AnalysisResult.analyzed_at))
            .limit(1)
        )
        latest_row = latest_result.first()

        latest_analysis = None
        if latest_row:
            ar = latest_row.AnalysisResult
            latest_analysis = LatestAnalysis(
                id=ar.id,
                disease_type=ar.disease_type,
                confidence=ar.confidence,
                analyzed_at=ar.analyzed_at,
                image_path=latest_row.file_path,
            )

        response.append(FieldResponse(
            id=field.id,
            name=field.name,
            location=field.location,
            status=field.status,
            created_at=field.created_at,
            latest_analysis=latest_analysis,
        ))

    return response


# ── GET /status/{field_id} ────────────────────────────────────────────────────
# 특정 구역 상태 조회
@router.get("/status/{field_id}", response_model=FieldResponse)
async def get_field_status(field_id: UUID, db: AsyncSession = Depends(get_db)):
    field = await db.get(Field, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="구역을 찾을 수 없습니다.")

    latest_result = await db.execute(
        select(AnalysisResult, Image.file_path)
        .join(Image, AnalysisResult.image_id == Image.id)
        .where(AnalysisResult.field_id == field_id)
        .order_by(desc(AnalysisResult.analyzed_at))
        .limit(1)
    )
    latest_row = latest_result.first()

    latest_analysis = None
    if latest_row:
        ar = latest_row.AnalysisResult
        latest_analysis = LatestAnalysis(
            id=ar.id,
            disease_type=ar.disease_type,
            confidence=ar.confidence,
            analyzed_at=ar.analyzed_at,
            image_path=latest_row.file_path,
        )

    return FieldResponse(
        id=field.id,
        name=field.name,
        location=field.location,
        status=field.status,
        created_at=field.created_at,
        latest_analysis=latest_analysis,
    )


# ── GET /images ───────────────────────────────────────────────────────────────
# 전체 이미지 갤러리 (Image 화면용) — 구역 필터, 페이지네이션
@router.get("/images", response_model=List[ImageItem])
async def get_images(
    field_id: Optional[UUID] = None,
    limit: int = 30,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Image, Field.name.label("field_name"), Field.id.label("fid"),
               AnalysisResult.disease_type, AnalysisResult.confidence)
        .join(AnalysisResult, AnalysisResult.image_id == Image.id, isouter=True)
        .join(Field, AnalysisResult.field_id == Field.id, isouter=True)
        .order_by(desc(Image.captured_at))
        .limit(limit)
        .offset(offset)
    )
    if field_id:
        query = query.where(AnalysisResult.field_id == field_id)

    rows = (await db.execute(query)).all()

    return [
        ImageItem(
            id=row.Image.id,
            field_id=row.fid,
            field_name=row.field_name or "",
            file_path=row.Image.file_path,
            file_size_kb=row.Image.file_size_kb,
            captured_at=row.Image.captured_at,
            disease_type=row.disease_type,
            confidence=row.confidence,
        )
        for row in rows
    ]


# ── GET /history ──────────────────────────────────────────────────────────────
# 분석 히스토리 (구역 필터 가능)
@router.get("/history", response_model=List[HistoryItem])
async def get_history(
    field_id: Optional[UUID] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(AnalysisResult, Image.file_path)
        .join(Image, AnalysisResult.image_id == Image.id)
        .order_by(desc(AnalysisResult.analyzed_at))
        .limit(limit)
    )
    if field_id:
        query = query.where(AnalysisResult.field_id == field_id)

    rows = (await db.execute(query)).all()
    return [
        HistoryItem(
            id=r.AnalysisResult.id,
            field_id=r.AnalysisResult.field_id,
            disease_type=r.AnalysisResult.disease_type,
            confidence=r.AnalysisResult.confidence,
            analyzed_at=r.AnalysisResult.analyzed_at,
            image_path=r.file_path,
        )
        for r in rows
    ]


# ── GET /notifications ────────────────────────────────────────────────────────
# 미확인 알림 목록
@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Notification)
        .where(Notification.is_read == False)
        .order_by(desc(Notification.created_at))
    )
    return result.scalars().all()


# ── PATCH /notifications/{id}/read ───────────────────────────────────────────
# 알림 읽음 처리
@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: UUID, db: AsyncSession = Depends(get_db)):
    notif = await db.get(Notification, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    notif.is_read = True
    await db.commit()
    return {"message": "읽음 처리 완료"}


# ── Mock AI 분석 (ML팀 TFLite 모델 연동 전까지 사용) ─────────────────────────
def _mock_analyze() -> tuple[str, float]:
    diseases = ["NORMAL", "NORMAL", "NORMAL", "BLIGHT", "RUST"]
    disease_type = random.choice(diseases)
    confidence   = round(random.uniform(0.75, 0.99), 2)
    return disease_type, confidence
