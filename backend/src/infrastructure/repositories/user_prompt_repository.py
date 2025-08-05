from typing import List, Optional

from sqlalchemy.orm import Session

from src.infrastructure.repositories.base_repository import BaseRepository
from src.infrastructure import sql_models as models
from src.api import schemas


class UserPromptRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create(self, user_id: int, prompt: schemas.UserPromptCreate) -> models.UserPrompt:
        db_prompt = models.UserPrompt(
            name=prompt.name,
            content=prompt.content,
            user_id=user_id,
        )
        self.db.add(db_prompt)
        self.db.commit()
        self.db.refresh(db_prompt)
        return db_prompt

    def get_by_id(self, prompt_id: int) -> Optional[models.UserPrompt]:
        return self.db.query(models.UserPrompt).filter(models.UserPrompt.id == prompt_id).first()

    def list_by_user(self, user_id: int) -> List[models.UserPrompt]:
        return (
            self.db.query(models.UserPrompt)
            .filter(models.UserPrompt.user_id == user_id)
            .order_by(models.UserPrompt.created_at.desc())
            .all()
        )

    def update(self, prompt_id: int, prompt_data: schemas.UserPromptCreate) -> Optional[models.UserPrompt]:
        db_prompt = self.db.query(models.UserPrompt).filter(models.UserPrompt.id == prompt_id).first()
        if not db_prompt:
            return None
        db_prompt.name = prompt_data.name
        db_prompt.content = prompt_data.content
        self.db.commit()
        self.db.refresh(db_prompt)
        return db_prompt

    def delete(self, prompt_id: int) -> None:
        db_prompt = self.db.query(models.UserPrompt).filter(models.UserPrompt.id == prompt_id).first()
        if db_prompt:
            self.db.delete(db_prompt)
            self.db.commit()
