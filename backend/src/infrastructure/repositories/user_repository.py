from typing import Optional
from sqlalchemy import select
from src.infrastructure.repositories.base_repository import BaseRepository
from src.infrastructure import sql_models as models


class UserRepository(BaseRepository):
    async def get_by_email(self, email: str) -> Optional[models.User]:
        result = await self.db.execute(
            select(models.User).where(models.User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, *, email: str, hashed_password: str) -> models.User:
        user = models.User(email=email, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
