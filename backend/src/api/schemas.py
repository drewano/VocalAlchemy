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

# Action Plan schemas
class ActionPlanItemAttributes(BaseModel):
    topic: Optional[str] = None
    responsible: Optional[str] = None
    assigned_by: Optional[str] = None
    participants: Optional[list[str]] = None
    deadline: Optional[str] = None

class ActionPlanItem(BaseModel):
    extraction_class: str
    extraction_text: str
    attributes: ActionPlanItemAttributes
    char_interval: Optional[dict] = None

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
    action_plan: Optional[list[ActionPlanItem]] = None

class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummary]
    total: int

class AnalysisRename(BaseModel):
    filename: str

class AnalysisStatusResponse(BaseModel):
    id: str
    status: str

# Upload schemas
class InitiateUploadRequest(BaseModel):
    filename: str

class InitiateUploadResponse(BaseModel):
    sas_url: str
    blob_name: str
    analysis_id: str

class FinalizeUploadRequest(BaseModel):
    analysis_id: str
    prompt: str

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class TokenData(BaseModel):
    email: Optional[str] = None
