from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks, Form, Body
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
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.config import settings

router = APIRouter()

def get_analysis_repository(db: Session = Depends(get_db)) -> AnalysisRepository:
    return AnalysisRepository(db)

# External clients dependencies

from functools import lru_cache

@lru_cache()
def get_transcriber() -> AzureSpeechClient:
    return AzureSpeechClient(
        api_key=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
        storage_connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
        storage_container_name=settings.AZURE_STORAGE_CONTAINER_NAME,
    )


def get_ai_analyzer() -> LiteLLMAIProcessor:
    # LiteLLM/Azure AI: model name driven; API key/base should be set in environment for litellm
    return LiteLLMAIProcessor(model_name=settings.AZURE_AI_MODEL_NAME)


def get_analysis_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    transcriber: AzureSpeechClient = Depends(get_transcriber),
    ai_analyzer: LiteLLMAIProcessor = Depends(get_ai_analyzer),
) -> AnalysisService:
    return AnalysisService(
        analysis_repo,
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
        filename=file.filename or "uploaded_audio",
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

        # Background task: start only the transcription pipeline (no polling)
        background_tasks.add_task(
            analysis_service.start_transcription_pipeline,
            analysis_id,
            source_path,
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

    # Update status to ANALYSIS_PENDING before launching background task
    analysis_repo.update_status(analysis_id, models.AnalysisStatus.ANALYSIS_PENDING)

    # 4. Launch background task to rerun analysis with existing transcript
    background_tasks.add_task(
        analysis_service.run_ai_analysis_pipeline,
        analysis_id=analysis_id,
        base_output_dir=task_dir,
    )

    # 5. Return success
    return {"message": "Rerun started", "analysis_id": analysis_id}


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        analysis_service.delete_analysis(analysis_id=analysis_id, user_id=current_user.id)
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    # 204 No Content
    return





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


@router.get("/audio/{analysis_id}")
async def get_original_audio(
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

    source_path = analysis.source_file_path
    if not source_path or not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source audio file not found")

    # Guess media type from extension; default to audio/mpeg
    ext = os.path.splitext(source_path)[1].lower()
    media_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".webm": "audio/webm",
        ".opus": "audio/opus",
    }
    media_type = media_map.get(ext, "audio/mpeg")

    return FileResponse(source_path, media_type=media_type, filename=os.path.basename(source_path))


@router.get("/list")
async def list_analyses(
    skip: int = 0,
    limit: int = 20,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
) -> schemas.AnalysisListResponse:
    items = analysis_repo.list_by_user(current_user.id, skip=skip, limit=limit)
    total = analysis_repo.count_by_user(current_user.id)

    summaries: list[schemas.AnalysisSummary] = []
    for a in items:
        transcript_snippet: str | None = None
        analysis_snippet: str | None = None

        # Read first 200 chars of transcript if available
        try:
            if a.transcript_path and os.path.exists(a.transcript_path):
                with open(a.transcript_path, "r", encoding="utf-8") as f:
                    transcript_snippet = f.read(200)
        except Exception:
            transcript_snippet = None

        # Read first 200 chars of analysis result if available
        try:
            if a.result_path and os.path.exists(a.result_path):
                with open(a.result_path, "r", encoding="utf-8") as f:
                    analysis_snippet = f.read(200)
        except Exception:
            analysis_snippet = None

        summaries.append(
            schemas.AnalysisSummary(
                id=a.id,
                status=a.status,
                created_at=a.created_at,
                filename=a.filename,
                transcript_snippet=transcript_snippet,
                analysis_snippet=analysis_snippet,
            )
        )

    return schemas.AnalysisListResponse(
        items=summaries,
        total=total,
    )


@router.get("/{analysis_id}")
async def get_analysis_detail(
    analysis_id: str,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> schemas.AnalysisDetail:
    a = analysis_repo.get_detailed_by_id(analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if a.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Backend polling step for transcription completion
    if a.status == models.AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
        base_output_dir = os.path.join("uploads", analysis_id)
        # This call may update status and enqueue analysis
        analysis_service.check_transcription_and_run_analysis(analysis_id, base_output_dir)
        # Reload fresh state after potential update
        a = analysis_repo.get_detailed_by_id(analysis_id)

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
    action_plan = None
    if versions_sorted:
        latest_version = versions_sorted[0]
        if latest_version.result_path and os.path.exists(latest_version.result_path):
            try:
                with open(latest_version.result_path, "r", encoding="utf-8") as f:
                    latest_analysis_content = f.read()
            except Exception:
                latest_analysis_content = ""
        people_involved = latest_version.people_involved
        # Extract structured plan if available
        try:
            if latest_version.structured_plan is not None:
                if isinstance(latest_version.structured_plan, dict) and "extractions" in latest_version.structured_plan:
                    action_plan = latest_version.structured_plan.get("extractions")
                elif isinstance(latest_version.structured_plan, list):
                    action_plan = latest_version.structured_plan
                else:
                    action_plan = latest_version.structured_plan
        except Exception:
            action_plan = None

    return schemas.AnalysisDetail(
        id=a.id,
        status=a.status,
        created_at=a.created_at,
        filename=a.filename,
        prompt=a.prompt,
        transcript=transcript_content,
        latest_analysis=latest_analysis_content or "",
        people_involved=people_involved,
        action_plan=action_plan,
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

@router.patch("/{analysis_id}/rename", response_model=schemas.AnalysisSummary)
async def rename_analysis(
    analysis_id: str,
    rename_data: schemas.AnalysisRename = Body(...),
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    updated = analysis_repo.update_filename(analysis_id, rename_data.filename)
    if not updated:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return schemas.AnalysisSummary(
        id=updated.id,
        status=updated.status,
        created_at=updated.created_at,
        filename=os.path.basename(updated.source_file_path) if updated.source_file_path else "",
    )
