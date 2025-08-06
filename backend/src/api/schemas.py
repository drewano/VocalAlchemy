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

# User Prompt schemas
class UserPromptBase(BaseModel):
    name: str
    content: str

class UserPromptCreate(UserPromptBase):
    pass

class UserPrompt(UserPromptBase):
    id: int
    user_id: int

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
    transcript_snippet: Optional[str] = None
    analysis_snippet: Optional[str] = None

    class Config:
        from_attributes = True

class AnalysisDetail(AnalysisSummary):
    prompt: Optional[str]
    transcript: str
    latest_analysis: Optional[str]
    versions: list[AnalysisVersion]
    people_involved: Optional[str]
    action_plan: Optional[list] = None

class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummary]
    total: int

class AnalysisRename(BaseModel):
    filename: str

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class TokenData(BaseModel):
    email: Optional[str] = None