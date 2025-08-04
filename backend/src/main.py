
import os
import uuid
from datetime import timedelta
from fastapi import FastAPI, HTTPException, APIRouter, Depends, File, UploadFile, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles 
from src.services.prompts import PREDEFINED_PROMPTS
from src.api.endpoints import users, analysis

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

@api_router.get("/prompts")
async def get_prompts():
    return PREDEFINED_PROMPTS

app.include_router(api_router, prefix="/api")

app.mount("/", StaticFiles(directory="static", html=True), name="static")