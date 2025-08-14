from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Body,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse, Response
import uuid
from typing import Optional
import asyncio
import re

from arq.connections import ArqRedis

from src.infrastructure import sql_models as models
from src.api import schemas
from src.auth import get_current_user
from src.services.analysis_service import AnalysisService, AnalysisNotFoundException
from src.services.export_service import ExportService
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.blob_storage_service import BlobStorageService
from src.config import settings
from src.rate_limiter import limiter
from src.api.dependencies import (
    get_analysis_service,
    get_analysis_repository,
    get_blob_storage_service,
    get_export_service,
    ARQ_POOL,
)

router = APIRouter()


class TranscriptUpdate(BaseModel):
    content: str


class StepResultUpdate(BaseModel):
    content: str


class RerunStepRequest(BaseModel):
    new_prompt_content: Optional[str] = None


@router.put("/{analysis_id}/transcript")
async def update_transcript(
    analysis_id: str,
    body: TranscriptUpdate,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        await analysis_service.overwrite_transcript_content(
            analysis_id, current_user.id, body.content
        )
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
        await analysis_service.update_step_result_content(
            step_result_id, current_user.id, body.content
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except ValueError:
        raise HTTPException(status_code=404, detail="Step result not found")
    return {"status": "ok"}


@router.post("/initiate-upload/", response_model=schemas.InitiateUploadResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_TIMESCALE_MINUTES}minute")
async def initiate_upload(
    request: Request,
    body: schemas.InitiateUploadRequest,
    current_user: models.User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
):
    # 1. Validate file size
    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if body.filesize > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
        )

    # 2. Generate a unique blob name
    blob_name = f"{current_user.id}/{uuid.uuid4()}-{body.filename}"

    # 3. Create analysis row storing the blob name
    analysis = await analysis_repo.create(
        user_id=current_user.id,
        filename=body.filename,
        status=models.AnalysisStatus.PENDING,
        source_blob_name=blob_name,
    )

    analysis_id = analysis.id

    # 4. Generate SAS URL for upload
    try:
        sas_url = await blob_storage_service.get_blob_upload_sas_url(
            blob_name, ttl_minutes=60
        )
    except Exception as e:
        await analysis_repo.update_status(analysis_id, models.AnalysisStatus.FAILED)
        raise HTTPException(
            status_code=500, detail=f"Error generating SAS URL: {str(e)}"
        )

    return schemas.InitiateUploadResponse(
        sas_url=sas_url, blob_name=blob_name, analysis_id=analysis_id
    )


@router.post("/finalize-upload/")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_TIMESCALE_MINUTES}minute")
async def finalize_upload(
    request: Request,
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

    # 2. Update prompt_flow_id
    try:
        flow_id = body.prompt_flow_id
        analysis.prompt_flow_id = flow_id
        await analysis_repo.db.commit()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating analysis: {str(e)}"
        )

    # 3. Enqueue transcription task
    try:
        await arq_pool.enqueue_job("start_transcription_task", body.analysis_id)
        return {"status": "processing_started"}
    except Exception as e:
        await analysis_repo.update_status(
            body.analysis_id, models.AnalysisStatus.FAILED
        )
        raise HTTPException(
            status_code=500, detail=f"Error starting transcription: {str(e)}"
        )


@router.post("/rerun/{analysis_id}")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_TIMESCALE_MINUTES}minute")
async def rerun_analysis(
    analysis_id: str,
    request: Request,
    body: schemas.RerunAnalysisRequest = Body(...),
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
        raise HTTPException(
            status_code=404, detail="Transcript not available for rerun"
        )

    # 3. Read transcript content from blob storage (validate accessibility)
    try:
        _ = await blob_storage_service.download_blob_as_text(
            analysis.transcript_blob_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to read transcript from storage: {str(e)}"
        )

    # Update the prompt flow
    flow_id = body.prompt_flow_id
    analysis.prompt_flow_id = flow_id
    await analysis_repo.db.commit()

    # Update status to ANALYSIS_PENDING before enqueuing task
    await analysis_repo.update_status(
        analysis_id, models.AnalysisStatus.ANALYSIS_PENDING
    )

    # 4. Enqueue background task to rerun analysis with existing transcript
    await arq_pool.enqueue_job("setup_ai_analysis_pipeline_task", analysis_id)

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
    await arq_pool.enqueue_job("delete_analysis_task", analysis_id, current_user.id)
    return


@router.get("/result/{analysis_id}")
async def get_result(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        content = await analysis_service.get_result_content(
            analysis_id, current_user.id
        )
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Result not found")
    except ValueError:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    except Exception:
        raise HTTPException(
            status_code=404, detail="Failed to read result from storage"
        )

    return PlainTextResponse(content)


@router.get("/result/version/{version_id}")
async def get_version_result(
    version_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        content = await analysis_service.get_version_result_content(
            version_id, current_user.id
        )
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Version not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Version result not found")
    except Exception:
        raise HTTPException(
            status_code=500, detail="Failed to read version result from storage"
        )

    return PlainTextResponse(content)


@router.get("/transcript/{analysis_id}")
async def get_transcript(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    try:
        content = await analysis_service.get_transcript_content(
            analysis_id, current_user.id
        )
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Transcript not found")
    except ValueError:
        raise HTTPException(status_code=422, detail="Task not completed yet")
    except Exception:
        raise HTTPException(
            status_code=404, detail="Failed to read transcript from storage"
        )

    return PlainTextResponse(content)


@router.get("/audio/{analysis_id}")
async def get_audio(
    analysis_id: str,
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Récupère l'URL SAS du fichier audio traité (normalisé) pour une analyse donnée.
    
    Args:
        analysis_id (str): L'identifiant de l'analyse
        current_user (models.User): L'utilisateur actuel (dépendance injectée)
        analysis_service (AnalysisService): Le service d'analyse (dépendance injectée)
        
    Returns:
        dict: Un dictionnaire contenant l'URL SAS du fichier audio
        
    Raises:
        HTTPException: Si l'analyse n'est pas trouvée, si l'accès est refusé ou si aucun fichier audio traité n'est disponible
    """
    try:
        sas_url = await analysis_service.get_audio_sas_url(analysis_id, current_user.id)
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No processed audio file available")

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
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> schemas.AnalysisDetail:
    try:
        return await analysis_service.get_detailed_analysis_dto(
            analysis_id, current_user.id
        )
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.websocket("/ws/{analysis_id}")
async def analysis_status_ws(
    analysis_id: str,
    websocket: WebSocket,
    redis: ArqRedis = ARQ_POOL,
):
    await websocket.accept()
    channel_name = f"analysis:{analysis_id}:updates"

    async def sender(channel: str):
        async with redis.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    await websocket.send_text(message["data"].decode("utf-8"))

    async def receiver():
        # This loop waits for a message from the client.
        # If the client disconnects, a WebSocketDisconnect exception is raised,
        # which will end the task.
        try:
            async for message in websocket.iter_text():
                # We can ignore messages; the goal is to keep the connection alive
                # and detect disconnection.
                pass
        except WebSocketDisconnect:
            # Expected when the client disconnects
            pass

    sender_task = asyncio.create_task(sender(channel_name))
    receiver_task = asyncio.create_task(receiver())

    try:
        done, pending = await asyncio.wait(
            {sender_task, receiver_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except WebSocketDisconnect:
        # The client has disconnected, stop the tasks.
        sender_task.cancel()
        receiver_task.cancel()
    except Exception:
        # Handle any other exceptions that might occur
        sender_task.cancel()
        receiver_task.cancel()
    finally:
        try:
            await websocket.close()
        except:
            # Ignore errors when closing, as the connection might already be closed
            pass


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
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_TIMESCALE_MINUTES}minute")
async def retranscribe_analysis(
    analysis_id: str,
    request: Request,
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

    # 2. Update status to TRANSCRIPTION_IN_PROGRESS before enqueuing task
    await analysis_repo.update_status(
        analysis_id, models.AnalysisStatus.TRANSCRIPTION_IN_PROGRESS
    )

    # 3. Enqueue transcription task
    await arq_pool.enqueue_job("start_transcription_task", analysis_id)

    return {"message": "Retranscription started", "analysis_id": analysis_id}


@router.post("/step-result/{step_result_id}/rerun")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_TIMESCALE_MINUTES}minute")
async def rerun_step_result(
    step_result_id: str,
    request: Request,
    body: RerunStepRequest = Body(default=None),
    current_user: models.User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    arq_pool: ArqRedis = ARQ_POOL,
):
    try:
        # Validate step result ownership through analysis
        step_result = await analysis_service.analysis_repo.get_step_result_by_id(
            step_result_id
        )
        if not step_result:
            raise HTTPException(status_code=404, detail="Step result not found")

        analysis = await analysis_service.analysis_repo.get_by_id(
            step_result.analysis_version.analysis_id
        )
        if not analysis or analysis.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Enqueue rerun task
        new_prompt_content = body.new_prompt_content if body else None
        await arq_pool.enqueue_job(
            "rerun_ai_analysis_step_task", step_result_id, new_prompt_content
        )

        return {"message": "Step rerun started", "step_result_id": step_result_id}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error starting step rerun: {str(e)}"
        )


@router.get("/{analysis_id}/download-word", response_class=Response)
async def download_word_document(
    analysis_id: str,
    type: str = "assembly",  # Paramètre de requête pour le type de contenu
    current_user: models.User = Depends(get_current_user),
    export_service: ExportService = Depends(get_export_service),
):
    try:
        # Get analysis detail
        analysis_detail = await export_service.get_analysis_detail_for_export(
            analysis_id, current_user.id
        )

        # Generate Word document with specified content type
        docx_buffer = await export_service.generate_word_document(analysis_detail, type)

        # Sanitize the filename to remove invalid characters
        safe_filename = re.sub(r'[\\/*?:"<>|]', "", analysis_detail.filename)
        safe_filename = safe_filename.replace(" ", "_")
        filename = f"{safe_filename}.docx"
        
        # Prepare response
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        return Response(
            content=docx_buffer.getvalue(),
            headers=headers,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except AnalysisNotFoundException:
        raise HTTPException(status_code=404, detail="Analysis not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating Word document: {str(e)}"
        )
