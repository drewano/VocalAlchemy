from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base

from src.config import settings

engine = create_async_engine(settings.DATABASE_URL)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


# Async dependency to get DB session
async def get_async_db():
    async with async_session_factory() as session:
        yield session
