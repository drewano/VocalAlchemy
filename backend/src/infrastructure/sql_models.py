from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
import uuid
import enum

from src.infrastructure.database import Base


class AnalysisStatus(enum.Enum):
    PENDING = "PENDING"
    TRANSCRIPTION_IN_PROGRESS = "TRANSCRIPTION_IN_PROGRESS"
    ANALYSIS_PENDING = "ANALYSIS_PENDING"  # Transcription terminée, en attente d'analyse
    ANALYSIS_IN_PROGRESS = "ANALYSIS_IN_PROGRESS"
    COMPLETED = "COMPLETED"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    analysis_records = relationship("Analysis", back_populates="owner_user")
    prompts = relationship("UserPrompt", back_populates="owner_user", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(SAEnum(AnalysisStatus), nullable=False)
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    filename = Column(String, nullable=False)
    # Nom du blob dans Azure Storage correspondant à la source
    source_blob_name = Column(String, nullable=False)
    result_blob_name = Column(String, nullable=True)
    transcript_blob_name = Column(String, nullable=True)
    transcription_job_url: Mapped[str] = mapped_column(String, nullable=True)
    prompt = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    owner_user = relationship("User", back_populates="analysis_records")
    versions = relationship("AnalysisVersion", back_populates="analysis_record", cascade="all, delete-orphan")


class AnalysisVersion(Base):
    __tablename__ = "analysis_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("analyses.id"), nullable=False)
    prompt_used = Column(String, nullable=False)
    result_blob_name = Column(String, nullable=False)
    people_involved = Column(String, nullable=True)
    structured_plan = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    analysis_record = relationship("Analysis", back_populates="versions")


class UserPrompt(Base):
    __tablename__ = "user_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    content = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    owner_user = relationship("User", back_populates="prompts")