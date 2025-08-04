from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import FileResponse
import os
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import get_current_user
from ..core.pipeline import run_full_pipeline

router = APIRouter()

# Alias direct pour compat: POST /api/process-audio/
@router.post("/process-audio/", tags=["alias"])  # réel: /api/analysis/process-audio/
async def process_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    prompt: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")

        analysis = models.Analysis(
            user_id=current_user.id,
            status="Démarré",
            source_file_path="",
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        os.makedirs("uploads", exist_ok=True)
        task_dir = os.path.join("uploads", analysis.id)
        os.makedirs(task_dir, exist_ok=True)

        filename = file.filename or "uploaded_file"
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        file_path = os.path.join(task_dir, safe_filename)

        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        analysis.source_file_path = file_path
        db.commit()

        background_tasks.add_task(
            run_full_pipeline,
            analysis_id=analysis.id,
            source_path=file_path,
            base_output_dir=task_dir,
            user_prompt=prompt
        )

        return {"task_id": analysis.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("/status/{task_id}")
async def get_status(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == task_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "status": analysis.status,
        "has_result": bool(analysis.result_path and os.path.exists(analysis.result_path)),
        "has_transcript": bool(analysis.transcript_path and os.path.exists(analysis.transcript_path)),
    }


@router.get("/result/{task_id}")
async def get_result(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == task_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if analysis.status != "Terminé":
        raise HTTPException(status_code=422, detail="Task not completed yet")
    if not analysis.result_path or not os.path.exists(analysis.result_path):
        raise HTTPException(status_code=404, detail="Result file not found")

    return FileResponse(analysis.result_path, media_type='text/plain', filename="report.txt")


@router.get("/transcript/{task_id}")
async def get_transcript(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == task_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if analysis.status != "Terminé":
        raise HTTPException(status_code=422, detail="Task not completed yet")
    if not analysis.transcript_path or not os.path.exists(analysis.transcript_path):
        raise HTTPException(status_code=404, detail="Transcript file not found")

    return FileResponse(analysis.transcript_path, media_type='text/plain', filename="transcription.txt")


@router.get("/list")
async def list_analyses(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = (
        db.query(models.Analysis)
        .filter(models.Analysis.user_id == current_user.id)
        .order_by(models.Analysis.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "status": a.status,
            "created_at": a.created_at,
            "filename": os.path.basename(a.source_file_path) if a.source_file_path else "",
        }
        for a in items
    ]


@router.get("/{task_id}")
async def get_analysis_detail(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    a = db.query(models.Analysis).filter(models.Analysis.id == task_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if a.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {
        "id": a.id,
        "status": a.status,
        "created_at": a.created_at,
        "filename": os.path.basename(a.source_file_path) if a.source_file_path else "",
        "has_result": bool(a.result_path and os.path.exists(a.result_path)),
        "has_transcript": bool(a.transcript_path and os.path.exists(a.transcript_path)),
    }