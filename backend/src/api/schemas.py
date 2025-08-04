from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# User schemas
class UserCreate(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

# Analysis Version schema
class AnalysisVersion(BaseModel):
    id: str
    prompt_used: str
    created_at: datetime
    people_involved: Optional[str] = None

    class Config:
        from_attributes = True

# Analysis schemas
class AnalysisSummary(BaseModel):
    id: str
    status: str
    created_at: datetime
    filename: str

    class Config:
        from_attributes = True

class AnalysisDetail(AnalysisSummary):
    prompt: Optional[str]
    transcript: str
    latest_analysis: Optional[str]
    versions: list[AnalysisVersion]
    people_involved: Optional[str]

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None