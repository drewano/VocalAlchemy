import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src import auth
from src.api import schemas
from src.infrastructure.database import get_async_db
from src.infrastructure.repositories.prompt_flow_repository import PromptFlowRepository


router = APIRouter()


def get_prompt_flow_repository(db: AsyncSession = Depends(get_async_db)) -> PromptFlowRepository:
    return PromptFlowRepository(db)


@router.post("", response_model=schemas.PromptFlow, status_code=status.HTTP_201_CREATED)
async def create_prompt_flow(
    body: schemas.PromptFlowCreate,
    user: schemas.User = Depends(auth.get_current_user),
    repo: PromptFlowRepository = Depends(get_prompt_flow_repository),
):
    created = await repo.create(user_id=user.id, data=body)
    return schemas.PromptFlow.from_orm(created)


@router.get("", response_model=List[schemas.PromptFlow])
async def list_prompt_flows(
    user: schemas.User = Depends(auth.get_current_user),
    repo: PromptFlowRepository = Depends(get_prompt_flow_repository),
):
    flows = await repo.list_by_user(user_id=user.id)
    return [schemas.PromptFlow.from_orm(f) for f in flows]


@router.get("/{flow_id}", response_model=schemas.PromptFlow)
async def get_prompt_flow(
    flow_id: str,
    user: schemas.User = Depends(auth.get_current_user),
    repo: PromptFlowRepository = Depends(get_prompt_flow_repository),
):
    flow = await repo.get_by_id(flow_id)
    if not flow or flow.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt flow not found")
    return schemas.PromptFlow.from_orm(flow)


@router.put("/{flow_id}", response_model=schemas.PromptFlow)
async def update_prompt_flow(
    flow_id: str,
    body: schemas.PromptFlowUpdate,
    user: schemas.User = Depends(auth.get_current_user),
    repo: PromptFlowRepository = Depends(get_prompt_flow_repository),
):
    flow = await repo.get_by_id(flow_id)
    if not flow or flow.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt flow not found")
    updated = await repo.update(flow, body)
    return schemas.PromptFlow.from_orm(updated)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_flow(
    flow_id: str,
    user: schemas.User = Depends(auth.get_current_user),
    repo: PromptFlowRepository = Depends(get_prompt_flow_repository),
):
    flow = await repo.get_by_id(flow_id)
    if not flow or flow.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt flow not found")
    await repo.delete(flow)
    return None


