from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks, Form, Body
from fastapi.responses import PlainTextResponse
import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse

from src.infrastructure import sql_models as models
from src.api import schemas
from src.infrastructure.database import get_db
from src.auth import get_current_user
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.analysis_service import AnalysisService, AnalysisNotFoundException
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.services.blob_storage_service import BlobStorageService
from src.config import settings

router = APIRouter()

# Dependency providers (grouped at top for clarity and to avoid NameError in Depends)
from functools import lru_cache

def get_analysis_repository(db: Session = Depends(get_db)) -> AnalysisRepository:
    return AnalysisRepository(db)

@lru_cache()
def get_blob_storage_service() -> BlobStorageService:
    return BlobStorageService(
        storage_connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
        storage_container_name=settings.AZURE_STORAGE_CONTAINER_NAME,
    )

@lru_cache()
def get_transcriber(blob_storage_service: BlobStorageService = Depends(get_blob_storage_service)) -> AzureSpeechClient:
    return AzureSpeechClient(
        api_key=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
        blob_storage_service=blob_storage_service,
    )


def get_ai_analyzer() -> LiteLLMAIProcessor:
    return LiteLLMAIProcessor(model_name=settings.AZURE_AI_MODEL_NAME)


def get_analysis_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    transcriber: AzureSpeechClient = Depends(get_transcriber),
    ai_analyzer: LiteLLMAIProcessor = Depends(get_ai_analyzer),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
) -> AnalysisService:
    return AnalysisService(
        analysis_repo,
        transcriber=transcriber,
        ai_analyzer=ai_analyzer,
        blob_storage_service=blob_storage_service,
    )

@router.get("/status/{analysis_id}", response_model=schemas.AnalysisStatusResponse)
async def get_analysis_status(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if analysis.status == models.AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
        await analysis_service.check_transcription_and_run_analysis(analysis_id)
        analysis = analysis_repo.get_by_id(analysis_id)

    return schemas.AnalysisStatusResponse(id=analysis.id, status=analysis.status)

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
    # 1. Generate a unique blob name and read file content in memory
    blob_name = f"{current_user.id}/{uuid.uuid4()}-{file.filename}"
    content = await file.read()

    # 2. Create analysis row storing the blob name
    analysis = analysis_repo.create(
        user_id=current_user.id,
        filename=file.filename or "uploaded_audio",
        status=models.AnalysisStatus.PENDING,
        source_blob_name=blob_name,
        prompt=prompt,
    )

    analysis_id = analysis.id

    # 3. Launch background transcription using in-memory bytes
    try:
        background_tasks.add_task(
            analysis_service.start_transcription_pipeline,
            analysis_id,
            content,
            file.filename or "uploaded_audio",
            blob_name,
        )
        return {"analysis_id": analysis_id}
    except Exception as e:
        analysis_repo.update_status(analysis_id, models.AnalysisStatus.FAILED)
        raise HTTPException(status_code=500, detail=f"Error starting transcription: {str(e)}")


@router.post("/rerun/{analysis_id}")
async def rerun_analysis(
    analysis_id: str,
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
):
    # 1. Verify analysis exists and belongs to user
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Ensure transcript blob exists
    if not analysis.transcript_blob_name:
        raise HTTPException(status_code=404, detail="Transcript not available for rerun")

    # 3. Read transcript content from blob storage
    try:
        transcript = await blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read transcript from storage: {str(e)}")

    # Update status to ANALYSIS_PENDING before launching background task
    analysis_repo.update_status(analysis_id, models.AnalysisStatus.ANALYSIS_PENDING)

    # 4. Launch background task to rerun analysis with existing transcript
    background_tasks.add_task(
        analysis_service.run_ai_analysis_pipeline,
        analysis_id=analysis_id,
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
        await analysis_service.delete_analysis(analysis_id=analysis_id, user_id=current_user.id)
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
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if analysis.status != models.AnalysisStatus.COMPLETED:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    if not getattr(analysis, "result_blob_name", None):
        raise HTTPException(status_code=404, detail="Result not found")

    try:
        content = await blob_storage_service.download_blob_as_text(analysis.result_blob_name)
    except Exception:
        raise HTTPException(status_code=404, detail="Failed to read result from storage")

    return PlainTextResponse(content)


@router.get("/result/version/{version_id}")
async def get_version_result(
    version_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
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
    if not getattr(version, "result_blob_name", None):
        raise HTTPException(status_code=404, detail="Version result not found")

    try:
        content = await blob_storage_service.download_blob_as_text(version.result_blob_name)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read version result from storage")

    return PlainTextResponse(content)


@router.get("/transcript/{analysis_id}")
async def get_transcript(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if analysis.status != models.AnalysisStatus.COMPLETED:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    if not getattr(analysis, "transcript_blob_name", None):
        raise HTTPException(status_code=404, detail="Transcript not found")

    try:
        content = await blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
    except Exception:
        raise HTTPException(status_code=404, detail="Failed to read transcript from storage")

    return PlainTextResponse(content)


@router.get("/audio/{analysis_id}")
async def get_original_audio(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
):
    analysis = analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    blob_name = getattr(analysis, "source_blob_name", None)
    if not blob_name:
        raise HTTPException(status_code=404, detail="No source blob available")

    sas_url = await blob_storage_service.get_blob_sas_url(blob_name)
    return {"url": sas_url}


@router.get("/list")
async def list_analyses(
    skip: int = 0,
    limit: int = 20,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
) -> schemas.AnalysisListResponse:
    items = analysis_repo.list_by_user(current_user.id, skip=skip, limit=limit)
    total = analysis_repo.count_by_user(current_user.id)

    summaries: list[schemas.AnalysisSummary] = []
    for a in items:
        transcript_snippet: str | None = None
        analysis_snippet: str | None = None

        # Read first 200 chars of transcript if available from blob
        try:
            if getattr(a, "transcript_blob_name", None):
                content = await blob_storage_service.download_blob_as_text(a.transcript_blob_name)
                transcript_snippet = content[:200]
        except Exception:
            transcript_snippet = None

        # Read first 200 chars of analysis result if available from blob
        try:
            if getattr(a, "result_blob_name", None):
                content = await blob_storage_service.download_blob_as_text(a.result_blob_name)
                analysis_snippet = content[:200]
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
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
) -> schemas.AnalysisDetail:
    a = analysis_repo.get_detailed_by_id(analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if a.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Backend polling step for transcription completion
    if a.status == models.AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
        # This call may update status and enqueue analysis
        await analysis_service.check_transcription_and_run_analysis(analysis_id)
        # Reload fresh state after potential update
        a = analysis_repo.get_detailed_by_id(analysis_id)

    # Sort versions by created_at desc
    versions_sorted = sorted(a.versions or [], key=lambda v: v.created_at or 0, reverse=True)

    # Read transcript content
    transcript_content = ""
    if getattr(a, "transcript_blob_name", None):
        try:
            transcript_content = blob_storage_service.download_blob_as_text(a.transcript_blob_name)
        except Exception:
            transcript_content = ""

    # Latest analysis content and people involved
    latest_analysis_content = ""
    people_involved = None
    action_plan = None
    if versions_sorted:
        latest_version = versions_sorted[0]
        if getattr(latest_version, "result_blob_name", None):
            try:
                latest_analysis_content = blob_storage_service.download_blob_as_text(latest_version.result_blob_name)
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
        filename=updated.filename,
    )
