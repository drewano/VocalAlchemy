from typing import List, Optional

from sqlalchemy import select

from src.infrastructure.repositories.base_repository import BaseRepository
from src.infrastructure import sql_models as models
from src.api import schemas


class UserPromptRepository(BaseRepository):
    def __init__(self, db) -> None:
        super().__init__(db)

    async def create(self, user_id: int, prompt: schemas.UserPromptCreate) -> models.UserPrompt:
        db_prompt = models.UserPrompt(
            name=prompt.name,
            content=prompt.content,
            user_id=user_id,
        )
        self.db.add(db_prompt)
        await self.db.commit()
        await self.db.refresh(db_prompt)
        return db_prompt

    async def get_by_id(self, prompt_id: int) -> Optional[models.UserPrompt]:
        result = await self.db.execute(select(models.UserPrompt).where(models.UserPrompt.id == prompt_id))
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> List[models.UserPrompt]:
        result = await self.db.execute(
            select(models.UserPrompt)
            .where(models.UserPrompt.user_id == user_id)
            .order_by(models.UserPrompt.created_at.desc())
        )
        return result.scalars().all()

    async def update(self, prompt_id: int, prompt_data: schemas.UserPromptCreate) -> Optional[models.UserPrompt]:
        result = await self.db.execute(select(models.UserPrompt).where(models.UserPrompt.id == prompt_id))
        db_prompt = result.scalar_one_or_none()
        if not db_prompt:
            return None
        db_prompt.name = prompt_data.name
        db_prompt.content = prompt_data.content
        await self.db.commit()
        await self.db.refresh(db_prompt)
        return db_prompt

    async def delete(self, prompt_id: int) -> None:
        result = await self.db.execute(select(models.UserPrompt).where(models.UserPrompt.id == prompt_id))
        db_prompt = result.scalar_one_or_none()
        if db_prompt:
            await self.db.delete(db_prompt)
            await self.db.commit()
