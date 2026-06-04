from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
from uuid import UUID

from core.database import get_db
from models.models import AnalysisResult, Image, Field, Notification
from schemas.schemas import (
    AnalyzeResponse, HistoryItem, HistoryListResponse, FieldResponse,
    NotificationResponse, ImageItem, LatestAnalysis
)
from services.analysis_service import run_analysis

router = APIRouter()


# ── POST /analyze ─────────────────────────────────────────────────────────────
# 구역 ID + 이미지를 받아 AI 분석 후 결과 저장
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_image(
    field_id: UUID = Form(...),
    file: UploadFile = File(...),
    disease_type: Optional[str] = Form(None),   # 앱 TFLite 결과 (있으면 서버 추론 생략)
    confidence:   Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    field = await db.get(Field, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="구역을 찾을 수 없습니다.")

    image_bytes = await file.read()
    outcome = await run_analysis(
        db, field, image_bytes, file.filename or "upload.jpg",
        disease_type=disease_type, confidence=confidence,
    )

    return AnalyzeResponse(
        id=outcome.result.id,
        field_id=outcome.result.field_id,
        image_id=outcome.result.image_id,
        disease_type=outcome.result.disease_type,
        confidence=outcome.result.confidence,
        analyzed_at=outcome.result.analyzed_at,
        notification_sent=outcome.notification_sent,
        message=outcome.message,
        field_status=outcome.field_status,
        inference_source=outcome.inference_source,
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
# 분석 히스토리 (구역 필터 + 질병만 필터 + 페이지네이션)
@router.get("/history", response_model=HistoryListResponse)
async def get_history(
    field_id: Optional[UUID] = None,
    limit: int = 20,
    offset: int = 0,
    disease_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    safe_limit  = max(1, min(limit, 100))
    safe_offset = max(0, offset)

    base = select(AnalysisResult).join(Image, AnalysisResult.image_id == Image.id)
    if field_id:
        base = base.where(AnalysisResult.field_id == field_id)
    if disease_only:
        base = base.where(AnalysisResult.disease_type != "NORMAL")

    # 전체 건수
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # 데이터
    data_q = (
        select(AnalysisResult, Image.file_path)
        .join(Image, AnalysisResult.image_id == Image.id)
        .order_by(desc(AnalysisResult.analyzed_at))
        .limit(safe_limit)
        .offset(safe_offset)
    )
    if field_id:
        data_q = data_q.where(AnalysisResult.field_id == field_id)
    if disease_only:
        data_q = data_q.where(AnalysisResult.disease_type != "NORMAL")

    rows = (await db.execute(data_q)).all()
    items = [
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
    return HistoryListResponse(data=items, total=total, limit=safe_limit, offset=safe_offset)


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


