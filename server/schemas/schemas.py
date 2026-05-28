from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ─── 최신 분석 결과 (Field 안에 포함) ─────────────────
class LatestAnalysis(BaseModel):
    id: UUID
    disease_type: str
    confidence: float
    analyzed_at: datetime
    image_path: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Field ───────────────────────────────────────────
class FieldResponse(BaseModel):
    id: UUID
    name: str                                          # a1, b1, c1, d1, e1
    location: Optional[str]
    status: str                                        # NORMAL / WARNING / DANGER
    created_at: datetime
    latest_analysis: Optional[LatestAnalysis] = None  # Farm 화면 구역 상태용

    class Config:
        from_attributes = True


# ─── Analyze 요청/응답 ────────────────────────────────
class AnalyzeResponse(BaseModel):
    id: UUID
    field_id: UUID
    image_id: UUID
    disease_type: str
    confidence: float
    analyzed_at: datetime
    notification_sent: bool

    class Config:
        from_attributes = True


# ─── 히스토리 ─────────────────────────────────────────
class HistoryItem(BaseModel):
    id: UUID
    field_id: UUID
    disease_type: str
    confidence: float
    analyzed_at: datetime
    image_path: str

    class Config:
        from_attributes = True


# ─── 이미지 갤러리 (Image 화면용) ─────────────────────
class ImageItem(BaseModel):
    id: UUID
    field_id: UUID
    field_name: str          # a1, b1 ...
    file_path: str
    file_size_kb: Optional[int] = None
    captured_at: datetime
    disease_type: Optional[str] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


# ─── Notification ─────────────────────────────────────
class NotificationResponse(BaseModel):
    id: UUID
    field_id: UUID
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
