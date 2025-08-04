from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import FileResponse, PlainTextResponse
import os
import uuid
import aiofiles
from sqlalchemy.orm import Session, joinedload

from src.infrastructure import sql_models as models
from src.api import schemas
from src.infrastructure.database import get_db
from src.auth import get_current_user
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.analysis_service import AnalysisService, AnalysisNotFoundException
from src.services.audio_splitter import split_audio
from src.services.external_apis.gladia_client import GladiaClient
from src.services.external_apis.ai_processor import GoogleAIProcessor
from src.config import settings

router = APIRouter()

def get_analysis_repository(db: Session = Depends(get_db)) -> AnalysisRepository:
    return AnalysisRepository(db)

# External clients dependencies

def get_transcriber() -> GladiaClient:
    return GladiaClient(api_key=settings.GLADIA_API_KEY)


def get_ai_analyzer() -> GoogleAIProcessor:
    return GoogleAIProcessor(api_key=settings.GOOGLE_API_KEY)


def get_analysis_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    transcriber: GladiaClient = Depends(get_transcriber),
    ai_analyzer: GoogleAIProcessor = Depends(get_ai_analyzer),
) -> AnalysisService:
    return AnalysisService(
        analysis_repo,
        audio_splitter=split_audio,
        transcriber=transcriber,
        ai_analyzer=ai_analyzer,
    )

# Alias direct pour compat: POST /api/process-audio/
@router.post("/process-audio/", tags=["alias"])  # réel: /api/analysis/process-audio/
async def process_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    prompt: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
):
    # 1. Create analysis row with temporary path
    analysis = analysis_repo.create(
        user_id=current_user.id,
        status=models.AnalysisStatus.PENDING,
        source_file_path=file.filename or "uploaded_audio",
        prompt=prompt,
    )

    analysis_id = analysis.id

    # 3. Prepare output dir and destination path
    base_output_dir = os.path.join("uploads", analysis_id)
    source_path = os.path.join(base_output_dir, file.filename)

    # 5. Ensure directories
    os.makedirs(base_output_dir, exist_ok=True)

    # 6. Update record now that we know the final source path
    try:
        # Save uploaded file asynchronously
        async with aiofiles.open(source_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)

        # Background task to run full pipeline
        background_tasks.add_task(
            analysis_service.run_full_pipeline,
            analysis_id,
            source_path,
            base_output_dir,
            prompt,
        )

        # Persist the correct source_file_path after successful save
        # Reuse update_paths_and_status to just commit the source path via direct model change if available
        # As repository lacks a dedicated method, do minimal update
        rec = analysis_repo.get_by_id(analysis_id)
        if rec:
            rec.source_file_path = source_path
            analysis_repo.db.commit()

        return {"analysis_id": analysis_id}
    except Exception as e:
        # Mark as failed on any error during save
        analysis_repo.update_status(analysis_id, models.AnalysisStatus.FAILED)
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")


@router.post("/rerun/{analysis_id}")
async def rerun_analysis(
    analysis_id: str,
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    # 1. Verify analysis exists and belongs to user
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Get transcript path
    transcript_path = analysis.transcript_path
    if not transcript_path or not os.path.exists(transcript_path):
        raise HTTPException(status_code=404, detail="Transcript not available for rerun")

    # 3. Read transcript content asynchronously
    try:
        async with aiofiles.open(transcript_path, "r", encoding="utf-8") as f:
            transcript = await f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read transcript: {str(e)}")

    # Prepare output dir
    task_dir = os.path.dirname(transcript_path) or os.path.join("uploads", analysis_id)
    os.makedirs(task_dir, exist_ok=True)

    # Update status to PROCESSING before launching background task
    analysis_repo.update_status(analysis_id, models.AnalysisStatus.PROCESSING)

    # 4. Launch background task to rerun analysis
    background_tasks.add_task(
        analysis_service.rerun_analysis_from_transcript,
        analysis_id=analysis_id,
        transcript=transcript,
        new_prompt=prompt,
        base_output_dir=task_dir,
    )

    # 5. Return success
    return {"message": "Rerun started", "analysis_id": analysis_id}


@router.get("/status/{analysis_id}")
async def get_status(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "status": analysis.status,
        "has_result": bool(analysis.result_path and os.path.exists(analysis.result_path)),
        "has_transcript": bool(analysis.transcript_path and os.path.exists(analysis.transcript_path)),
    }


@router.get("/result/{analysis_id}")
async def get_result(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if analysis.status != models.AnalysisStatus.COMPLETED:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    if not analysis.result_path or not os.path.exists(analysis.result_path):
        raise HTTPException(status_code=404, detail="Result file not found")

    return FileResponse(analysis.result_path, media_type='text/plain', filename="report.txt")


@router.get("/result/version/{version_id}")
async def get_version_result(
    version_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
):
    version = analysis_repo.get_version_by_id(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    # Check ownership via the parent analysis
    analysis = analysis_repo.get_by_id(version.analysis_id)
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


@router.get("/transcript/{analysis_id}")
async def get_transcript(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if analysis.status != models.AnalysisStatus.COMPLETED:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    if not analysis.transcript_path or not os.path.exists(analysis.transcript_path):
        raise HTTPException(status_code=404, detail="Transcript file not found")

    return FileResponse(analysis.transcript_path, media_type='text/plain', filename="transcription.txt")


@router.get("/list")
async def list_analyses(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
):
    items = analysis_repo.list_by_user(current_user.id)
    return [
        {
            "id": a.id,
            "status": a.status,
            "created_at": a.created_at,
            "filename": os.path.basename(a.source_file_path) if a.source_file_path else "",
        }
        for a in items
    ]


@router.get("/{analysis_id}")
async def get_analysis_detail(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
) -> schemas.AnalysisDetail:
    a = analysis_repo.get_detailed_by_id(analysis_id)
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
