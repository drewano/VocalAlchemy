from typing import Optional
from sqlalchemy.orm import Session
from src.infrastructure.repositories.base_repository import BaseRepository
from src.infrastructure import sql_models as models


class UserRepository(BaseRepository):
    def get_by_email(self, email: str) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.email == email).first()

    def create(self, *, email: str, hashed_password: str) -> models.User:
        user = models.User(email=email, hashed_password=hashed_password)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
