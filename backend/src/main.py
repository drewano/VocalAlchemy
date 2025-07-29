import os
import uuid
from functools import partial
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from src.core.pipeline import run_full_pipeline

# Initialize FastAPI app
app = FastAPI(title="POC Audio Analysis Pipeline")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global dictionary to store task states
TASKS = {}


def update_status(task_id: str, status: str, result_path: str = None):
    """
    Update the status of a task in the TASKS dictionary.
    
    Args:
        task_id (str): The unique identifier for the task
        status (str): The new status of the task
        result_path (str, optional): Path to the result file if task is completed
    """
    if task_id in TASKS:
        TASKS[task_id]["status"] = status
        if result_path:
            TASKS[task_id]["result_path"] = result_path


@app.post("/process-audio/")
async def process_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Process an uploaded audio file through the full pipeline.
    
    Args:
        background_tasks (BackgroundTasks): FastAPI background tasks handler
        file (UploadFile): The uploaded audio file
        
    Returns:
        dict: Contains the task_id for tracking the processing status
    """
    try:
        # Validate that a file was provided
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task directory
        task_dir = os.path.join("uploads", task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # Get the filename and create a safe version
        filename = file.filename or "uploaded_file"
        # Replace any path separators to prevent directory traversal
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        file_path = os.path.join(task_dir, safe_filename)
        
        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Initialize task state
        TASKS[task_id] = {"status": "Démarré", "result_path": None}
        
        # Add the pipeline to background tasks
        background_tasks.add_task(
            run_full_pipeline,
            source_path=file_path,
            base_output_dir=task_dir,
            update_status_callback=partial(update_status, task_id)
        )
        
        # Return task ID immediately
        return {"task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """
    Get the status of a processing task.
    
    Args:
        task_id (str): The unique identifier for the task
        
    Returns:
        dict: Contains the status of the task
        
    Raises:
        HTTPException: If the task_id is not found
    """
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TASKS[task_id]


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """
    Get the result file for a completed task.
    
    Args:
        task_id (str): The unique identifier for the task
        
    Returns:
        FileResponse: The analysis report file
        
    Raises:
        HTTPException: If the task is not found or not completed
    """
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = TASKS[task_id]
    if task["status"] != "Terminé":
        raise HTTPException(status_code=422, detail="Task not completed yet")
    
    result_path = task.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(result_path, media_type='text/plain', filename="report.txt")