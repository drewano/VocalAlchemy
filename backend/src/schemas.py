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

# Analysis schemas
class Analysis(BaseModel):
    id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None