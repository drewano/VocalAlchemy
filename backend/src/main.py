from fastapi import (
    FastAPI,
    APIRouter,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

from src.api.endpoints import users, analysis
from src.api.endpoints import prompt_flows as prompt_flows
from src.api.endpoints import admin
from src.api.endpoints import setup

import logging
import litellm
from src.config import settings
from src.rate_limiter import limiter
from slowapi.errors import RateLimitExceeded


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

app = FastAPI(title="POC Audio Analysis Pipeline")

# Add rate limiter to app state
app.state.limiter = limiter

# Add exception handler for rate limiting
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request, exc):
    return PlainTextResponse(str(exc), status_code=429)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utiliser un APIRouter et include_router, puis le monter avec prefix /api
api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(setup.router, prefix="/setup", tags=["setup"])

api_router.include_router(
    prompt_flows.router, prefix="/prompt-flows", tags=["prompt-flows"]
)

app.include_router(api_router, prefix="/api")

# Route pour servir les fichiers statiques et gérer le routing React
@app.get("/{full_path:path}", response_class=FileResponse)
async def serve_react_app(request: Request, full_path: str):
    # Chemin vers le fichier statique demandé
    static_file_path = os.path.join("static", full_path)
    
    # Si le fichier existe, le servir directement
    if os.path.isfile(static_file_path):
        return FileResponse(static_file_path)
    
    # Pour toutes les autres routes (y compris les routes React), servir index.html
    return FileResponse("static/index.html")
