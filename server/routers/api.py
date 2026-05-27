from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from uuid import UUID
import os, shutil, uuid
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

from core.database import get_db
from models.models import AnalysisResult, Image, Field, Notification
from schemas.schemas import AnalyzeResponse, HistoryItem, FieldResponse, NotificationResponse

# Gemini 초기화
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
if _GEMINI_KEY:
    genai.configure(api_key=_GEMINI_KEY)
    _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    _gemini_model = None

router = APIRouter()

UPLOAD_DIR = os.getenv("IMAGE_UPLOAD_DIR", "./uploaded_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── POST /analyze ─────────────────────────────────────────────────────────────
# Android 앱에서 이미지 + 구역 ID를 보내면 AI 분석 후 결과 저장
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
    ext = os.path.splitext(file.filename)[-1]
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    file_size_kb = os.path.getsize(file_path) // 1024

    # 3. images 테이블에 저장
    image = Image(file_path=file_path, file_size_kb=file_size_kb)
    db.add(image)
    await db.flush()

    # 4. AI 모델 분석 (Gemini Vision)
    disease_type, confidence = await _analyze_with_gemini(file_path)

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


# ── GET /history ──────────────────────────────────────────────────────────────
# 분석 히스토리 목록 (최신순, 선택적으로 구역 필터)
@router.get("/history", response_model=List[HistoryItem])
async def get_history(
    field_id: UUID = None,
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


# ── GET /status/{field_id} ────────────────────────────────────────────────────
# 특정 구역의 현재 상태 조회
@router.get("/status/{field_id}", response_model=FieldResponse)
async def get_field_status(field_id: UUID, db: AsyncSession = Depends(get_db)):
    field = await db.get(Field, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="구역을 찾을 수 없습니다.")
    return field


# ── GET /fields ───────────────────────────────────────────────────────────────
# 전체 구역 목록 (앱 메인 화면용)
@router.get("/fields", response_model=List[FieldResponse])
async def get_all_fields(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Field).order_by(Field.name))
    return result.scalars().all()


# ── GET /notifications ────────────────────────────────────────────────────────
# 읽지 않은 알림 목록
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


# ── AI 분석 함수 ──────────────────────────────────────────────────────────────
async def _analyze_with_gemini(image_path: str) -> tuple[str, float]:
    """
    Gemini Vision으로 이미지를 분석합니다.
    GEMINI_API_KEY가 없으면 mock 결과를 반환합니다.

    ML팀 TFLite 모델 완성 시 이 함수를 교체하세요:
        interpreter.set_tensor(input_index, image_tensor)
        interpreter.invoke()
        output = interpreter.get_tensor(output_index)
    """
    if _gemini_model is None:
        # API Key 없을 때 fallback
        import random
        diseases = ["NORMAL", "NORMAL", "NORMAL", "BLIGHT", "RUST"]
        return random.choice(diseases), round(random.uniform(0.75, 0.99), 2)

    import PIL.Image as PILImage
    import json

    prompt = """
You are a plant pathology expert. Analyze the provided plant leaf image.
Identify whether the plant is healthy or diseased.

Return ONLY a JSON object in this exact format (no markdown, no extra text):
{
  "disease_type": "NORMAL or BLIGHT or RUST or MOSAIC or POWDERY_MILDEW or LEAF_SPOT or UNKNOWN",
  "confidence": 0.00
}

Rules:
- disease_type must be one of: NORMAL, BLIGHT, RUST, MOSAIC, POWDERY_MILDEW, LEAF_SPOT, UNKNOWN
- confidence must be a float between 0.0 and 1.0
- If the image is not a plant leaf, return UNKNOWN with confidence 0.5
"""

    try:
        img = PILImage.open(image_path)
        response = _gemini_model.generate_content([prompt, img])
        text = response.text.strip()

        # 마크다운 코드블록 제거
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        disease_type = data.get("disease_type", "UNKNOWN").upper()
        confidence   = float(data.get("confidence", 0.8))
        return disease_type, round(confidence, 2)

    except Exception as e:
        print(f"Gemini 분석 오류: {e}")
        return "UNKNOWN", 0.5
