from sqlalchemy import Column, String, Float, Boolean, Integer, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from core.database import Base

class Field(Base):
    __tablename__ = "fields"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(100), nullable=False)
    location   = Column(String(200))
    status     = Column(String(20), nullable=False, default="NORMAL")  # NORMAL / WARNING / DANGER
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    analysis_results = relationship("AnalysisResult", back_populates="field")
    notifications    = relationship("Notification", back_populates="field")
    devices          = relationship("Device", back_populates="field")


class Device(Base):
    __tablename__ = "devices"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id          = Column(UUID(as_uuid=True), ForeignKey("fields.id", ondelete="SET NULL"), nullable=True)
    name              = Column(String(100), nullable=False)
    bluetooth_mac     = Column(String(17), unique=True, nullable=False)
    last_connected_at = Column(TIMESTAMP, nullable=True)
    created_at        = Column(TIMESTAMP, server_default=func.now())

    field  = relationship("Field", back_populates="devices")
    images = relationship("Image", back_populates="device")


class Image(Base):
    __tablename__ = "images"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id    = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    file_path    = Column(String(500), nullable=False)
    file_size_kb = Column(Integer)
    captured_at  = Column(TIMESTAMP, server_default=func.now())
    created_at   = Column(TIMESTAMP, server_default=func.now())

    device          = relationship("Device", back_populates="images")
    analysis_result = relationship("AnalysisResult", back_populates="image", uselist=False)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id     = Column(UUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    image_id     = Column(UUID(as_uuid=True), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    disease_type = Column(String(100), nullable=False)  # NORMAL / BLIGHT / RUST / MOSAIC / UNKNOWN
    confidence   = Column(Float, nullable=False)
    analyzed_at  = Column(TIMESTAMP, server_default=func.now())

    field         = relationship("Field", back_populates="analysis_results")
    image         = relationship("Image", back_populates="analysis_result")
    notifications = relationship("Notification", back_populates="analysis")


class Notification(Base):
    __tablename__ = "notifications"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id    = Column(UUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="SET NULL"), nullable=True)
    message     = Column(Text, nullable=False)
    is_read     = Column(Boolean, nullable=False, default=False)
    created_at  = Column(TIMESTAMP, server_default=func.now())

    field    = relationship("Field", back_populates="notifications")
    analysis = relationship("AnalysisResult", back_populates="notifications")
