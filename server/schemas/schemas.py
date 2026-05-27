from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

# ─── Field ───────────────────────────────────────────
class FieldResponse(BaseModel):
    id: UUID
    name: str
    location: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Analysis ────────────────────────────────────────
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

class HistoryItem(BaseModel):
    id: UUID
    field_id: UUID
    disease_type: str
    confidence: float
    analyzed_at: datetime
    image_path: str

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
