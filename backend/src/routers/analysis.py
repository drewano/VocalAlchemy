from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import FileResponse, PlainTextResponse
import os
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..core.pipeline import run_full_pipeline, rerun_analysis_from_transcript

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


@router.post("/rerun/{analysis_id}")
async def rerun_analysis(
    analysis_id: str,
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Verify analysis exists and belongs to user
    analysis = db.query(models.Analysis).filter(models.Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Get transcript path
    transcript_path = analysis.transcript_path
    if not transcript_path or not os.path.exists(transcript_path):
        raise HTTPException(status_code=404, detail="Transcript not available for rerun")

    # 3. Read transcript content
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read transcript: {str(e)}")

    # Prepare output dir
    task_dir = os.path.dirname(transcript_path) or os.path.join("uploads", analysis_id)
    os.makedirs(task_dir, exist_ok=True)

    # 4. Launch background task to rerun analysis
    background_tasks.add_task(
        rerun_analysis_from_transcript,
        analysis_id=analysis_id,
        transcript=transcript,
        new_prompt=prompt,
        base_output_dir=task_dir,
    )

    # 5. Return success
    return {"message": "Rerun started", "task_id": analysis_id}


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


@router.get("/result/version/{version_id}")
async def get_version_result(
    version_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    version = db.query(models.AnalysisVersion).filter(models.AnalysisVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    # Check ownership via the parent analysis
    analysis = db.query(models.Analysis).filter(models.Analysis.id == version.analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Parent analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if not version.result_path or not os.path.exists(version.result_path):
        raise HTTPException(status_code=404, detail="Version result file not found")

    try:
        with open(version.result_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read version result: {str(e)}")

    return PlainTextResponse(content)


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
) -> schemas.AnalysisDetail:
    a = (
        db.query(models.Analysis)
        .options(joinedload(models.Analysis.versions))
        .filter(models.Analysis.id == task_id)
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if a.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Sort versions by created_at desc
    versions_sorted = sorted(a.versions or [], key=lambda v: v.created_at or 0, reverse=True)

    # Read transcript content
    transcript_content = ""
    if a.transcript_path and os.path.exists(a.transcript_path):
        try:
            with open(a.transcript_path, "r", encoding="utf-8") as f:
                transcript_content = f.read()
        except Exception:
            transcript_content = ""

    # Latest analysis content and people involved
    latest_analysis_content = ""
    people_involved = None
    if versions_sorted:
        latest_version = versions_sorted[0]
        if latest_version.result_path and os.path.exists(latest_version.result_path):
            try:
                with open(latest_version.result_path, "r", encoding="utf-8") as f:
                    latest_analysis_content = f.read()
            except Exception:
                latest_analysis_content = ""
        people_involved = latest_version.people_involved

    return schemas.AnalysisDetail(
        id=a.id,
        status=a.status,
        created_at=a.created_at,
        filename=os.path.basename(a.source_file_path) if a.source_file_path else "",
        prompt=a.prompt,
        transcript=transcript_content,
        latest_analysis=latest_analysis_content or "",
        people_involved=people_involved,
        versions=[
            schemas.AnalysisVersion(
                id=v.id,
                prompt_used=v.prompt_used,
                created_at=v.created_at,
                people_involved=v.people_involved,
            )
            for v in versions_sorted
        ],
    )
