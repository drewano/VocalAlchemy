
import os
import uuid
from datetime import timedelta
from fastapi import FastAPI, HTTPException, APIRouter, Depends, File, UploadFile, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles 
from src.services.prompts import PREDEFINED_PROMPTS
from src.api.endpoints import users, analysis
from src.api.endpoints import user_prompts as user_prompts
import logging
import litellm
from src.config import settings

from src.infrastructure.database import engine
from src.infrastructure import sql_models as models

# Configuration centralisée du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
    force=True,
)

# Active le mode verbeux de LiteLLM si activé dans la configuration
if settings.LITELLM_DEBUG:
    litellm.set_verbose = True
    logging.info("LiteLLM verbose mode is enabled.")

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

# Route catch-all pour servir le SPA React et les fichiers statiques
from fastapi.responses import FileResponse

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    """
    Sert les fichiers statiques ou l'application React.
    - Si le chemin correspond à un fichier existant dans /static, le sert.
    - Sinon, renvoie index.html pour que React Router gère la route.
    """
    static_file_path = os.path.join("static", full_path)
    if os.path.isfile(static_file_path):
        return FileResponse(static_file_path)

    # Si le chemin est un répertoire (ex: /), cherche index.html
    if os.path.isdir(static_file_path):
        index_path = os.path.join(static_file_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

    # Pour toutes les autres routes, c'est le SPA qui gère
    return FileResponse("static/index.html")