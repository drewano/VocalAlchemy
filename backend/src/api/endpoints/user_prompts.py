from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import schemas
from src import auth
from src.infrastructure.database import get_async_db
from src.infrastructure.repositories.user_prompt_repository import UserPromptRepository

router = APIRouter()


def get_user_prompt_repository(db: AsyncSession = Depends(get_async_db)) -> UserPromptRepository:
    return UserPromptRepository(db)


@router.post("", response_model=schemas.UserPrompt, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    prompt: schemas.UserPromptCreate,
    user: schemas.User = Depends(auth.get_current_user),
    repo: UserPromptRepository = Depends(get_user_prompt_repository),
):
    return await repo.create(user_id=user.id, prompt=prompt)


@router.get("", response_model=List[schemas.UserPrompt])
async def list_prompts(
    user: schemas.User = Depends(auth.get_current_user),
    repo: UserPromptRepository = Depends(get_user_prompt_repository),
):
    return await repo.list_by_user(user_id=user.id)


@router.put("/{prompt_id}", response_model=schemas.UserPrompt)
async def update_prompt(
    prompt_id: int,
    prompt: schemas.UserPromptCreate,
    user: schemas.User = Depends(auth.get_current_user),
    repo: UserPromptRepository = Depends(get_user_prompt_repository),
):
    db_prompt = await repo.get_by_id(prompt_id)
    if not db_prompt or db_prompt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    updated = await repo.update(prompt_id=prompt_id, prompt_data=prompt)
    return updated


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: int,
    user: schemas.User = Depends(auth.get_current_user),
    repo: UserPromptRepository = Depends(get_user_prompt_repository),
):
    db_prompt = await repo.get_by_id(prompt_id)
    if not db_prompt or db_prompt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    await repo.delete(prompt_id)
    return None
