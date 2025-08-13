from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    Text,
    text as sa_text,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.types import JSON
import uuid
import enum

from src.infrastructure.database import Base


class AnalysisStatus(enum.Enum):
    PENDING = "PENDING"
    TRANSCRIPTION_IN_PROGRESS = "TRANSCRIPTION_IN_PROGRESS"
    ANALYSIS_PENDING = (
        "ANALYSIS_PENDING"  # Transcription terminée, en attente d'analyse
    )
    ANALYSIS_IN_PROGRESS = "ANALYSIS_IN_PROGRESS"
    COMPLETED = "COMPLETED"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=sa_text("now()"), nullable=False
    )

    # Relationship
    analysis_records = relationship("Analysis", back_populates="owner_user")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(
        String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(AnalysisStatus), nullable=False
    )
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    filename = Column(String, nullable=False)
    # Nom du blob dans Azure Storage correspondant à la source
    source_blob_name = Column(String, nullable=False)
    normalized_blob_name: Mapped[str] = mapped_column(String, nullable=True)
    result_blob_name = Column(String, nullable=True)
    transcript_blob_name = Column(String, nullable=True)
    transcription_job_url: Mapped[str] = mapped_column(String, nullable=True)
    prompt_flow_id: Mapped[str] = mapped_column(
        String, ForeignKey("prompt_flows.id"), nullable=False
    )
    transcript_snippet: Mapped[str] = mapped_column(String(255), nullable=True)
    analysis_snippet: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=sa_text("now()"), nullable=False
    )

    # Relationship
    owner_user = relationship("User", back_populates="analysis_records")
    versions = relationship(
        "AnalysisVersion",
        back_populates="analysis_record",
        cascade="all, delete-orphan",
    )
    prompt_flow = relationship("PromptFlow")


class AnalysisVersion(Base):
    __tablename__ = "analysis_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("analyses.id"), nullable=False)
    prompt_used = Column(String, nullable=False)
    result_blob_name = Column(String, nullable=True)
    people_involved = Column(String, nullable=True)
    structured_plan = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("now()"))

    # Relationship
    analysis_record = relationship("Analysis", back_populates="versions")
    steps = relationship(
        "AnalysisStepResult",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="AnalysisStepResult.step_order",
    )


class PromptFlow(Base):
    __tablename__ = "prompt_flows"

    id = Column(
        String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False
    )
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship
    steps = relationship(
        "PromptStep",
        back_populates="flow",
        cascade="all, delete-orphan",
        order_by="PromptStep.step_order",
    )


class PromptStep(Base):
    __tablename__ = "prompt_steps"

    id = Column(
        String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False
    )
    flow_id = Column(String, ForeignKey("prompt_flows.id"), nullable=False)
    name = Column(String, nullable=False)
    content = Column(String, nullable=False)
    step_order = Column(Integer, nullable=False)

    # Relationship
    flow = relationship("PromptFlow", back_populates="steps")


class AnalysisStepStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalysisStepResult(Base):
    __tablename__ = "analysis_step_results"

    id = Column(
        String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False
    )
    analysis_version_id = Column(
        String, ForeignKey("analysis_versions.id"), nullable=False
    )
    step_name = Column(String, nullable=False)
    step_order = Column(Integer, nullable=False)
    status: Mapped[AnalysisStepStatus] = mapped_column(
        SAEnum(AnalysisStepStatus), nullable=False
    )
    content = Column(Text, nullable=True)

    # Relationship
    version = relationship("AnalysisVersion", back_populates="steps")
