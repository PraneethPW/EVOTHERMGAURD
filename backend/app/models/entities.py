import enum, uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Float, Boolean, Text, JSON, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def uid(): return str(uuid.uuid4())
def now(): return datetime.utcnow()
class Base(DeclarativeBase): pass
class RiskLevel(str, enum.Enum): NORMAL="NORMAL"; WARNING="WARNING"; HIGH_RISK="HIGH_RISK"; CRITICAL="CRITICAL"
class ImageType(str, enum.Enum): RGB="RGB"; THERMAL="THERMAL"; FUSED="FUSED"; GRADCAM="GRADCAM"
class User(Base):
    __tablename__="users"; id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid); name: Mapped[str]=mapped_column(String(120)); email: Mapped[str]=mapped_column(String(255), unique=True, index=True); password_hash: Mapped[str]=mapped_column(String(255)); created_at: Mapped[datetime]=mapped_column(DateTime, default=now); updated_at: Mapped[datetime]=mapped_column(DateTime, default=now, onupdate=now)
class Equipment(Base):
    __tablename__="equipment"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True); equipment_name: Mapped[str]=mapped_column(String(150)); equipment_type: Mapped[str]=mapped_column(String(100)); asset_code: Mapped[Optional[str]]=mapped_column(String(100),nullable=True); location_label: Mapped[Optional[str]]=mapped_column(String(150),nullable=True); manufacturer: Mapped[Optional[str]]=mapped_column(String(120),nullable=True); notes: Mapped[Optional[str]]=mapped_column(Text,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
class Inspection(Base):
    __tablename__="inspections"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True); equipment_id: Mapped[str]=mapped_column(ForeignKey("equipment.id")); status: Mapped[str]=mapped_column(String(40),default="DRAFT"); created_at: Mapped[datetime]=mapped_column(DateTime,default=now); completed_at: Mapped[Optional[datetime]]=mapped_column(DateTime,nullable=True); model_version: Mapped[Optional[str]]=mapped_column(String(100),nullable=True); equipment: Mapped[Equipment]=relationship(lazy="selectin")
class InspectionEnvironment(Base):
    __tablename__="inspection_environments"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); inspection_id: Mapped[str]=mapped_column(ForeignKey("inspections.id"),unique=True); ambient_temperature: Mapped[float]=mapped_column(Float); humidity: Mapped[float]=mapped_column(Float); weather: Mapped[str]=mapped_column(String(50)); season: Mapped[str]=mapped_column(String(50)); time_of_day: Mapped[str]=mapped_column(String(50)); sun_exposure: Mapped[Optional[str]]=mapped_column(String(50),nullable=True); notes: Mapped[Optional[str]]=mapped_column(Text,nullable=True)
class InspectionImage(Base):
    __tablename__="inspection_images"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); inspection_id: Mapped[str]=mapped_column(ForeignKey("inspections.id"),index=True); image_type: Mapped[ImageType]=mapped_column(Enum(ImageType)); file_path: Mapped[str]=mapped_column(String(500)); width: Mapped[Optional[int]]=mapped_column(nullable=True); height: Mapped[Optional[int]]=mapped_column(nullable=True); metadata_json: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
class Prediction(Base):
    __tablename__="predictions"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); inspection_id: Mapped[str]=mapped_column(ForeignKey("inspections.id"),unique=True); risk_level: Mapped[RiskLevel]=mapped_column(Enum(RiskLevel)); confidence: Mapped[float]=mapped_column(Float); probabilities: Mapped[dict]=mapped_column(JSON); explanation_metadata: Mapped[dict]=mapped_column(JSON,default=dict); model_version: Mapped[str]=mapped_column(String(100)); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
class Alert(Base):
    __tablename__="alerts"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); inspection_id: Mapped[str]=mapped_column(ForeignKey("inspections.id")); severity: Mapped[RiskLevel]=mapped_column(Enum(RiskLevel)); status: Mapped[str]=mapped_column(String(40),default="OPEN"); message: Mapped[str]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime,default=now); acknowledged_at: Mapped[Optional[datetime]]=mapped_column(DateTime,nullable=True)
class MaintenanceFeedback(Base):
    __tablename__="maintenance_feedback"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); inspection_id: Mapped[str]=mapped_column(ForeignKey("inspections.id"),index=True); operator_status: Mapped[str]=mapped_column(String(50)); actual_issue: Mapped[Optional[str]]=mapped_column(Text,nullable=True); action_taken: Mapped[str]=mapped_column(Text); notes: Mapped[Optional[str]]=mapped_column(Text,nullable=True); verified: Mapped[bool]=mapped_column(Boolean,default=False); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
class AIAnalysis(Base):
    __tablename__="ai_analyses"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); inspection_id: Mapped[str]=mapped_column(ForeignKey("inspections.id"),index=True); prompt_type: Mapped[str]=mapped_column(String(50)); response: Mapped[str]=mapped_column(Text); model_used: Mapped[str]=mapped_column(String(100)); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
