from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from src.infrastructure.repositories.base_repository import BaseRepository
from src.infrastructure import sql_models as models


class UserRepository(BaseRepository):
    async def get_by_email(self, email: str) -> Optional[models.User]:
        result = await self.db.execute(
            select(models.User).where(models.User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[models.User]:
        result = await self.db.execute(
            select(models.User).where(models.User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, *, email: str, hashed_password: str, is_admin: bool = False, status: models.UserStatus = models.UserStatus.PENDING) -> models.User:
        user = models.User(email=email, hashed_password=hashed_password, is_admin=is_admin, status=status)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def list_all_with_analysis_count(self) -> List[models.User]:
        result = await self.db.execute(
            select(models.User)
            .options(selectinload(models.User.analyses))
            .order_by(models.User.created_at.desc())
        )
        return list(result.scalars().all())

    async def has_admin_user(self) -> bool:
        result = await self.db.execute(
            select(func.count()).where(models.User.is_admin == True)
        )
        count = result.scalar_one()
        return count > 0
