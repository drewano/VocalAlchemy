from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import schemas
from src.infrastructure import sql_models as models
from src.auth import require_admin, get_password_hash
from src.infrastructure.database import get_async_db
from src.infrastructure.repositories.user_repository import UserRepository


router = APIRouter()


def get_user_repository(db: AsyncSession = Depends(get_async_db)) -> UserRepository:
    return UserRepository(db)


@router.get("/users", response_model=schemas.AdminUserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_async_db),
    user_repo: UserRepository = Depends(get_user_repository),
    current_user: models.User = Depends(require_admin)
):
    """List all users with their meeting count."""
    users = await user_repo.list_all_with_analysis_count()
    
    admin_users = [
        schemas.AdminUserView(
            id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            status=user.status.value,
            meeting_count=len(user.analyses)
        )
        for user in users
    ]
    
    return schemas.AdminUserListResponse(users=admin_users)


@router.post("/users/{user_id}/approve", status_code=status.HTTP_200_OK)
async def approve_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_repo: UserRepository = Depends(get_user_repository),
    current_user: models.User = Depends(require_admin)
):
    """Approve a user."""
    # Get the user by ID
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user status to APPROVED
    user.status = models.UserStatus.APPROVED
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/users/{user_id}/reject", status_code=status.HTTP_200_OK)
async def reject_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_repo: UserRepository = Depends(get_user_repository),
    current_user: models.User = Depends(require_admin)
):
    """Reject a user."""
    # Get the user by ID
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user status to REJECTED
    user.status = models.UserStatus.REJECTED
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/users", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user_by_admin(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(get_async_db),
    user_repo: UserRepository = Depends(get_user_repository),
    current_user: models.User = Depends(require_admin)
):
    """Create a new user by admin."""
    # Check if user already exists
    existing_user = await user_repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash the password
    hashed_password = get_password_hash(user_data.password)
    
    # Create new user with APPROVED status
    new_user = await user_repo.create(
        email=user_data.email,
        hashed_password=hashed_password,
        status=models.UserStatus.APPROVED
    )
    
    return new_user