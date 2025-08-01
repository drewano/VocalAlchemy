import os
import uuid
from functools import partial
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
# NOUVEAU: Importer StaticFiles
from fastapi.staticfiles import StaticFiles 
from src.core.pipeline import run_full_pipeline
from src.core.prompts import PREDEFINED_PROMPTS

# Initialize FastAPI app
app = FastAPI(title="POC Audio Analysis Pipeline")

# La configuration CORS est bonne pour le développement, mais en production avec
# ce Dockerfile, le frontend et le backend sont sur la même origine, donc elle est moins critique.
# On la garde pour la flexibilité.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global dictionary to store task states
TASKS = {}


def update_status(task_id: str, status: str, result_path: str = None, transcript_path: str = None):
    """
    Update the status of a task in the TASKS dictionary.
    ...
    """
    if task_id in TASKS:
        TASKS[task_id]["status"] = status
        if result_path:
            TASKS[task_id]["result_path"] = result_path
        if transcript_path:
            TASKS[task_id]["transcript_path"] = transcript_path

# On déplace les routes API sous un préfixe pour éviter les conflits
# avec les fichiers statiques.
api_router = FastAPI()

@api_router.post("/process-audio/")
async def process_audio(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    prompt: str = Form(...)
):
    # ... (le reste de votre fonction process_audio reste INCHANGÉ) ...
    try:
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        os.makedirs("uploads", exist_ok=True)
        task_id = str(uuid.uuid4())
        task_dir = os.path.join("uploads", task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        filename = file.filename or "uploaded_file"
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        file_path = os.path.join(task_dir, safe_filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        TASKS[task_id] = {"status": "Démarré", "result_path": None, "transcript_path": None}
        
        background_tasks.add_task(
            run_full_pipeline,
            source_path=file_path,
            base_output_dir=task_dir,
            update_status_callback=partial(update_status, task_id),
            user_prompt=prompt
        )
        
        return {"task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@api_router.get("/status/{task_id}")
async def get_status(task_id: str):
    # ... (le reste de votre fonction get_status reste INCHANGÉ) ...
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TASKS[task_id]


@api_router.get("/result/{task_id}")
async def get_result(task_id: str):
    # ... (le reste de votre fonction get_result reste INCHANGÉ) ...
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = TASKS[task_id]
    if task["status"] != "Terminé":
        raise HTTPException(status_code=422, detail="Task not completed yet")
    
    result_path = task.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(result_path, media_type='text/plain', filename="report.txt")


@api_router.get("/transcript/{task_id}")
async def get_transcript(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = TASKS[task_id]
    if task["status"] != "Terminé":
        raise HTTPException(status_code=422, detail="Task not completed yet")
    
    transcript_path = task.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        raise HTTPException(status_code=404, detail="Transcript file not found")
    
    return FileResponse(transcript_path, media_type='text/plain', filename="transcription.txt")


@api_router.get("/prompts")
async def get_prompts():
    return PREDEFINED_PROMPTS

# NOUVEAU: Monter le routeur API sous le préfixe /api
# Cela correspond à la configuration du proxy Vite et des appels `axios`.
app.mount("/api", api_router)

# NOUVEAU: Monter le répertoire statique pour servir le frontend
# Le chemin "/" servira le fichier index.html du frontend.
app.mount("/", StaticFiles(directory="static", html=True), name="static")