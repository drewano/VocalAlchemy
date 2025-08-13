import os
from fastapi import (
    FastAPI,
    APIRouter,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from src.api.endpoints import users, analysis
from src.api.endpoints import prompt_flows as prompt_flows

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

api_router.include_router(
    prompt_flows.router, prefix="/prompt-flows", tags=["prompt-flows"]
)

app.include_router(api_router, prefix="/api")

# Route catch-all pour servir le SPA React et les fichiers statiques



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
