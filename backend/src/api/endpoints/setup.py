from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_async_db
from src.api import schemas
from src.infrastructure.repositories.user_repository import UserRepository
from src.infrastructure import sql_models as models
from src.auth import get_password_hash

router = APIRouter()


@router.get("/status")
async def get_setup_status(db: AsyncSession = Depends(get_async_db)):
    """
    Public endpoint to check if admin setup is needed.
    Returns {"admin_exists": true} if an admin user exists, false otherwise.
    """
    user_repo = UserRepository(db)
    admin_exists = await user_repo.has_admin_user()
    return {"admin_exists": admin_exists}


@router.post("/create-admin", status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    user_create: schemas.UserCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create the first administrator user.
    This endpoint can only be used when no admin user exists.
    """
    user_repo = UserRepository(db)
    
    # Check if an admin already exists
    admin_exists = await user_repo.has_admin_user()
    if admin_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An administrator account already exists."
        )
    
    # Check if a user with the same email already exists
    existing_user = await user_repo.get_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )
    
    # Hash the password
    hashed_password = get_password_hash(user_create.password)
    
    # Create the admin user
    admin_user = await user_repo.create(
        email=user_create.email,
        hashed_password=hashed_password,
        is_admin=True,
        status=models.UserStatus.APPROVED
    )
    
    # Return the created user (excluding the hashed password)
    return schemas.User(
        id=admin_user.id,
        email=admin_user.email,
        is_admin=admin_user.is_admin,
        status=admin_user.status.value
    )