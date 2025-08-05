
import os
import uuid
from datetime import timedelta
from fastapi import FastAPI, HTTPException, APIRouter, Depends, File, UploadFile, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles 
from src.services.prompts import PREDEFINED_PROMPTS
from src.api.endpoints import users, analysis
from src.api.endpoints import user_prompts as user_prompts

from src.infrastructure.database import engine
from src.infrastructure import sql_models as models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="POC Audio Analysis Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utiliser un APIRouter et include_router, puis le monter avec prefix /api
api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"]) 
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"]) 
api_router.include_router(user_prompts.router, prefix="/user-prompts", tags=["user-prompts"])

from src.infrastructure.database import get_db
from src.infrastructure.repositories.user_prompt_repository import UserPromptRepository
from src import auth


@api_router.get("/prompts")
async def get_prompts(db=Depends(get_db), user=Depends(auth.get_current_user)):
    repo = UserPromptRepository(db)
    user_prompts = repo.list_by_user(user.id)

    # Merge: user prompts override predefined on name conflicts
    merged: dict[str, str] = {**PREDEFINED_PROMPTS}
    for p in user_prompts:
        merged[p.name] = p.content
    return merged

app.include_router(api_router, prefix="/api")

app.mount("/", StaticFiles(directory="static", html=True), name="static")