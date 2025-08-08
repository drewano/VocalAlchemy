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
    return schemas.PromptFlow(
        id=created.id,
        name=created.name,
        description=created.description,
        steps=[
            schemas.PromptStep(
                id=s.id,
                name=s.name,
                content=s.content,
                step_order=s.step_order,
            )
            for s in created.steps
        ],
    )


@router.get("", response_model=List[schemas.PromptFlow])
async def list_prompt_flows(
    user: schemas.User = Depends(auth.get_current_user),
    repo: PromptFlowRepository = Depends(get_prompt_flow_repository),
):
    flows = await repo.list_by_user(user_id=user.id)

    # Map DB flows to schema objects
    db_flows = [
        schemas.PromptFlow(
            id=f.id,
            name=f.name,
            description=f.description,
            steps=[
                schemas.PromptStep(
                    id=s.id,
                    name=s.name,
                    content=s.content,
                    step_order=s.step_order,
                )
                for s in f.steps
            ],
        )
        for f in flows
    ]

    # Append virtual flows from predefined prompts (legacy)
    from src.services.prompts import PREDEFINED_PROMPTS

    virtual_flows: list[schemas.PromptFlow] = []
    for name, content in PREDEFINED_PROMPTS.items():
        virtual_id = f"predefined_{name.replace(' ', '_')}"
        step = schemas.PromptStep(
            id=f"{virtual_id}_step_1",
            name="analyse",
            content=content,
            step_order=1,
        )
        virtual_flows.append(
            schemas.PromptFlow(
                id=virtual_id,
                name=name,
                description="Prompt prédéfini",
                steps=[step],
            )
        )

    return db_flows + virtual_flows


@router.get("/{flow_id}", response_model=schemas.PromptFlow)
async def get_prompt_flow(
    flow_id: str,
    user: schemas.User = Depends(auth.get_current_user),
    repo: PromptFlowRepository = Depends(get_prompt_flow_repository),
):
    flow = await repo.get_by_id(flow_id)
    if not flow or flow.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt flow not found")
    return schemas.PromptFlow(
        id=flow.id,
        name=flow.name,
        description=flow.description,
        steps=[
            schemas.PromptStep(
                id=s.id,
                name=s.name,
                content=s.content,
                step_order=s.step_order,
            )
            for s in flow.steps
        ],
    )


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
    return schemas.PromptFlow(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        steps=[
            schemas.PromptStep(
                id=s.id,
                name=s.name,
                content=s.content,
                step_order=s.step_order,
            )
            for s in updated.steps
        ],
    )


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


