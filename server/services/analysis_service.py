"""
이미지 분석 핵심 로직.

`/analyze` 엔드포인트와 일일 자동 캡처 스케줄러가 공유한다.
"""
import os
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.models import AnalysisResult, Field, Image, Notification
from ai_inference import analyze as ai_analyze


UPLOAD_DIR = os.getenv("IMAGE_UPLOAD_DIR", "./uploaded_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── 질병 유형 → 한국어 메시지 ─────────────────────────────────────────────────
DISEASE_MESSAGES = {
    "NORMAL":  "정상입니다",
    "BLIGHT":  "역병이 감지되었습니다",
    "RUST":    "녹병이 감지되었습니다",
    "SPOT":    "점무늬병이 감지되었습니다",
    "MOSAIC":  "모자이크바이러스가 감지되었습니다",
    "MOLD":    "잎곰팡이병이 감지되었습니다",
    "ROT":     "검은썩음병이 감지되었습니다",
    "PEST":    "응애 피해가 감지되었습니다",
    "UNKNOWN": "판별 불가",
}


def disease_message(disease_type: str) -> str:
    return DISEASE_MESSAGES.get(disease_type, "질병이 감지되었습니다")


def compute_field_status(disease_type: str, confidence: float) -> str:
    if disease_type == "NORMAL":
        return "NORMAL"
    if confidence >= 0.9:
        return "DANGER"
    return "WARNING"


@dataclass
class AnalysisOutcome:
    result: AnalysisResult
    notification_sent: bool
    inference_source: str       # "ondevice" | "server"
    field_status: str           # NORMAL | WARNING | DANGER
    message: str                # 한국어 메시지


async def run_analysis(
    db: AsyncSession,
    field: Field,
    image_bytes: bytes,
    original_filename: str,
    *,
    disease_type: Optional[str] = None,
    confidence:   Optional[float] = None,
) -> AnalysisOutcome:
    """
    이미지를 저장하고 추론·DB 작성·알림 생성을 한 트랜잭션으로 수행한다.

    disease_type/confidence 가 주어지면 앱 TFLite 결과로 간주하고 서버 추론을 생략한다.
    """
    # 1. 이미지 파일 저장
    ext = os.path.splitext(original_filename)[-1] or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    file_size_kb = os.path.getsize(file_path) // 1024

    # 2. images 행
    image = Image(file_path=f"/images/{filename}", file_size_kb=file_size_kb)
    db.add(image)
    await db.flush()

    # 3. 추론 (앱 결과가 있으면 사용)
    if disease_type is not None and confidence is not None:
        inference_source = "ondevice"
        disease_type = disease_type.upper()
        confidence = round(float(confidence), 2)
    else:
        inference_source = "server"
        disease_type, confidence = ai_analyze(file_path)

    # 4. analysis_results
    result = AnalysisResult(
        field_id=field.id,
        image_id=image.id,
        disease_type=disease_type,
        confidence=confidence,
    )
    db.add(result)
    await db.flush()

    # 5. 구역 상태 + 알림
    new_status = compute_field_status(disease_type, confidence)
    field.status = new_status
    msg = disease_message(disease_type)

    notification_sent = False
    if disease_type != "NORMAL":
        notif = Notification(
            field_id=field.id,
            analysis_id=result.id,
            message=f"[{field.name}] {msg} (신뢰도 {confidence:.0%})",
        )
        db.add(notif)
        notification_sent = True

    await db.commit()
    await db.refresh(result)

    return AnalysisOutcome(
        result=result,
        notification_sent=notification_sent,
        inference_source=inference_source,
        field_status=new_status,
        message=msg,
    )
