from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from sqlalchemy import select
from fastapi.responses import PlainTextResponse, Response
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from arq.connections import ArqRedis
from src.worker.redis import get_redis_pool

from src.infrastructure import sql_models as models
from src.api import schemas
from src.auth import get_current_user
from src.infrastructure.database import get_async_db
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.analysis_service import AnalysisService, AnalysisNotFoundException
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.services.blob_storage_service import BlobStorageService
from src.config import settings

router = APIRouter()
class TranscriptUpdate(BaseModel):
    content: str

class StepResultUpdate(BaseModel):
    content: str

class RerunStepRequest(BaseModel):
    new_prompt_content: Optional[str] = None


# Dependency providers (grouped at top for clarity and to avoid NameError in Depends)
from functools import lru_cache

ARQ_POOL = Depends(get_redis_pool)

def get_analysis_repository(db: AsyncSession = Depends(get_async_db)) -> AnalysisRepository:
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
):
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return schemas.AnalysisStatusResponse(id=analysis.id, status=analysis.status)


@router.put("/{analysis_id}/transcript")
async def update_transcript(
    analysis_id: str,
    body: TranscriptUpdate,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        await analysis_service.overwrite_transcript_content(analysis_id, current_user.id, body.content)
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"status": "ok"}


@router.put("/step-result/{step_result_id}")
async def update_step_result(
    step_result_id: str,
    body: StepResultUpdate,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        await analysis_service.update_step_result_content(step_result_id, current_user.id, body.content)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except ValueError:
        raise HTTPException(status_code=404, detail="Step result not found")
    return {"status": "ok"}

@router.post("/initiate-upload/", response_model=schemas.InitiateUploadResponse)
async def initiate_upload(
    body: schemas.InitiateUploadRequest,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
):
    # 1. Generate a unique blob name
    blob_name = f"{current_user.id}/{uuid.uuid4()}-{body.filename}"

    # 2. Create analysis row storing the blob name
    analysis = await analysis_repo.create(
        user_id=current_user.id,
        filename=body.filename,
        status=models.AnalysisStatus.PENDING,
        source_blob_name=blob_name,
    )

    analysis_id = analysis.id

    # 3. Generate SAS URL for upload
    try:
        sas_url = await blob_storage_service.get_blob_upload_sas_url(blob_name, ttl_minutes=60)
    except Exception as e:
        await analysis_repo.update_status(analysis_id, models.AnalysisStatus.FAILED)
        raise HTTPException(status_code=500, detail=f"Error generating SAS URL: {str(e)}")

    return schemas.InitiateUploadResponse(
        sas_url=sas_url,
        blob_name=blob_name,
        analysis_id=analysis_id
    )


@router.post("/finalize-upload/")
async def finalize_upload(
    body: schemas.FinalizeUploadRequest,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    arq_pool: ArqRedis = ARQ_POOL,
):
    # 1. Retrieve and validate analysis ownership
    analysis = await analysis_repo.get_by_id(body.analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Ensure predefined flow exists to satisfy FK, then update prompt_flow_id
    try:
        flow_id = body.prompt_flow_id
        if str(flow_id).startswith("predefined_"):
            # Create a placeholder PromptFlow row if missing (to satisfy foreign key)
            result = await analysis_repo.db.execute(
                select(models.PromptFlow).where(models.PromptFlow.id == flow_id)
            )
            flow = result.scalar_one_or_none()
            if not flow:
                name = str(flow_id).removeprefix("predefined_").replace("_", " ")
                flow = models.PromptFlow(
                    id=flow_id,
                    name=name,
                    description="Prompt prédéfini (virtuel)",
                    user_id=current_user.id,
                )
                analysis_repo.db.add(flow)
                await analysis_repo.db.commit()

        analysis.prompt_flow_id = flow_id
        await analysis_repo.db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating analysis: {str(e)}")

    # 3. Enqueue transcription task
    try:
        await arq_pool.enqueue_job('start_transcription_task', body.analysis_id)
        return {"status": "processing_started"}
    except Exception as e:
        await analysis_repo.update_status(body.analysis_id, models.AnalysisStatus.FAILED)
        raise HTTPException(status_code=500, detail=f"Error starting transcription: {str(e)}")


@router.post("/rerun/{analysis_id}")
async def rerun_analysis(
    analysis_id: str,
    body: schemas.FinalizeUploadRequest,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
    arq_pool: ArqRedis = ARQ_POOL,
):
    # 1. Verify analysis exists and belongs to user
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Ensure transcript blob exists
    if not analysis.transcript_blob_name:
        raise HTTPException(status_code=404, detail="Transcript not available for rerun")

    # 3. Read transcript content from blob storage (validate accessibility)
    try:
        _ = await blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read transcript from storage: {str(e)}")

    # Update the prompt flow if provided (ensure predefined row exists for FK)
    if getattr(body, "prompt_flow_id", None):
        flow_id = body.prompt_flow_id
        if str(flow_id).startswith("predefined_"):
            result = await analysis_repo.db.execute(
                select(models.PromptFlow).where(models.PromptFlow.id == flow_id)
            )
            flow = result.scalar_one_or_none()
            if not flow:
                name = str(flow_id).removeprefix("predefined_").replace("_", " ")
                flow = models.PromptFlow(
                    id=flow_id,
                    name=name,
                    description="Prompt prédéfini (virtuel)",
                    user_id=current_user.id,
                )
                analysis_repo.db.add(flow)
                await analysis_repo.db.commit()
        analysis.prompt_flow_id = flow_id
        await analysis_repo.db.commit()

    # Update status to ANALYSIS_PENDING before enqueuing task
    await analysis_repo.update_status(analysis_id, models.AnalysisStatus.ANALYSIS_PENDING)

    # 4. Enqueue background task to rerun analysis with existing transcript
    await arq_pool.enqueue_job('run_ai_analysis_task', analysis_id)

    # 5. Return success
    return {"message": "Rerun started", "analysis_id": analysis_id}


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    arq_pool: ArqRedis = ARQ_POOL,
):
    # Validate early to provide immediate feedback
    try:
        # Ensure analysis exists and ownership
        analysis = await analysis_service.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException()
        if analysis.user_id != current_user.id:
            raise PermissionError()
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")

    # Enqueue deletion task
    await arq_pool.enqueue_job('delete_analysis_task', analysis_id, current_user.id)
    return





@router.get("/result/{analysis_id}")
async def get_result(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        content = await analysis_service.get_result_content(analysis_id, current_user.id)
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Result not found")
    except ValueError:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    except Exception:
        raise HTTPException(status_code=404, detail="Failed to read result from storage")

    return PlainTextResponse(content)


@router.get("/result/version/{version_id}")
async def get_version_result(
    version_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        content = await analysis_service.get_version_result_content(version_id, current_user.id)
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Version not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Version result not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read version result from storage")

    return PlainTextResponse(content)


@router.get("/transcript/{analysis_id}")
async def get_transcript(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        content = await analysis_service.get_transcript_content(analysis_id, current_user.id)
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Transcript not found")
    except ValueError:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    except Exception:
        raise HTTPException(status_code=404, detail="Failed to read transcript from storage")

    return PlainTextResponse(content)


@router.get("/audio/{analysis_id}")
async def get_original_audio(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        sas_url = await analysis_service.get_audio_sas_url(analysis_id, current_user.id)
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No source blob available")

    return {"url": sas_url}


@router.get("/list")
async def list_analyses(
    skip: int = 0,
    limit: int = 20,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
) -> schemas.AnalysisListResponse:
    items = await analysis_repo.list_by_user(current_user.id, skip=skip, limit=limit)
    total = await analysis_repo.count_by_user(current_user.id)

    summaries: list[schemas.AnalysisSummary] = []
    for a in items:
        transcript_snippet: str | None = a.transcript_snippet
        analysis_snippet: str | None = a.analysis_snippet

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
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
) -> schemas.AnalysisDetail:
    a = await analysis_repo.get_detailed_by_id(analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if a.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Sort versions by created_at desc
    versions_sorted = sorted(a.versions or [], key=lambda v: v.created_at or 0, reverse=True)

    # Read transcript content
    transcript_content = ""
    if getattr(a, "transcript_blob_name", None):
        try:
            transcript_content = await blob_storage_service.download_blob_as_text(a.transcript_blob_name)
        except Exception:
            transcript_content = ""

    # Latest analysis content and people involved (keep compatibility)
    latest_analysis_content = ""
    people_involved = None
    action_plan = None
    if versions_sorted:
        latest_version = versions_sorted[0]
        if getattr(latest_version, "result_blob_name", None):
            try:
                latest_analysis_content = await blob_storage_service.download_blob_as_text(latest_version.result_blob_name)
            except Exception:
                latest_analysis_content = ""
        people_involved = latest_version.people_involved
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
        prompt=None,
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
                steps=[
                    schemas.AnalysisStepResult(
                        id=sr.id,
                        step_name=sr.step_name,
                        step_order=sr.step_order,
                        status=str(sr.status.value) if hasattr(sr.status, "value") else str(sr.status),
                        content=sr.content,
                    )
                    for sr in (v.steps or [])
                ],
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
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    updated = await analysis_repo.update_filename(analysis_id, rename_data.filename)
    if not updated:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return schemas.AnalysisSummary(
        id=updated.id,
        status=updated.status,
        created_at=updated.created_at,
        filename=updated.filename,
    )


@router.post("/{analysis_id}/retranscribe")
async def retranscribe_analysis(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    arq_pool: ArqRedis = ARQ_POOL,
):
    # 1. Verify analysis exists and belongs to user
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Update status to TRANSCRIPTION_PENDING before enqueuing task
    await analysis_repo.update_status(analysis_id, models.AnalysisStatus.TRANSCRIPTION_PENDING)

    # 3. Enqueue transcription task
    await arq_pool.enqueue_job('start_transcription_task', analysis_id)

    return {"message": "Retranscription started", "analysis_id": analysis_id}


@router.post("/step-result/{step_result_id}/rerun")
async def rerun_step_result(
    step_result_id: str,
    body: RerunStepRequest = Body(default=None),
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    arq_pool: ArqRedis = ARQ_POOL,
):
    try:
        # Validate step result ownership through analysis
        step_result = await analysis_service.analysis_repo.get_step_result_by_id(step_result_id)
        if not step_result:
            raise HTTPException(status_code=404, detail="Step result not found")
        
        analysis = await analysis_service.analysis_repo.get_by_id(step_result.analysis_version.analysis_id)
        if not analysis or analysis.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Enqueue rerun task
        new_prompt_content = body.new_prompt_content if body else None
        await arq_pool.enqueue_job('rerun_ai_analysis_step_task', step_result_id, new_prompt_content)
        
        return {"message": "Step rerun started", "step_result_id": step_result_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting step rerun: {str(e)}")


@router.get("/{analysis_id}/download-word")
async def download_word_document(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        # Get analysis detail
        analysis_detail = await analysis_service.get_analysis_detail_for_export(analysis_id, current_user.id)
        
        # Generate Word document
        docx_buffer = await analysis_service.generate_word_document(analysis_detail)
        
        # Prepare response
        filename = f"analyse_{analysis_id}.docx"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        
        return Response(content=docx_buffer.getvalue(), headers=headers, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Word document: {str(e)}")
