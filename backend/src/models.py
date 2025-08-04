from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    analysis_records = relationship("Analysis", back_populates="owner_user")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False)
    source_file_path = Column(String, nullable=False)
    result_path = Column(String, nullable=True)
    transcript_path = Column(String, nullable=True)
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
    result_path = Column(String, nullable=False)
    people_involved = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    analysis_record = relationship("Analysis", back_populates="versions")