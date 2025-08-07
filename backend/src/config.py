from typing import Optional
from pydantic import Field, PostgresDsn, constr, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API keys
    AZURE_SPEECH_KEY: constr(strip_whitespace=True, min_length=1)
    AZURE_SPEECH_REGION: constr(strip_whitespace=True, min_length=1)
    AZURE_AI_API_KEY: constr(strip_whitespace=True, min_length=1)
    AZURE_AI_API_BASE: constr(strip_whitespace=True, min_length=1)
    AZURE_AI_MODEL_NAME: str = "command-r-plus"

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: constr(strip_whitespace=True, min_length=1)
    AZURE_STORAGE_CONTAINER_NAME: constr(strip_whitespace=True, min_length=1)

    # Database
    DATABASE_URL: PostgresDsn | str = Field(
        default="postgresql+asyncpg://user:password@db/dbname",
        description="SQLAlchemy-compatible database URL",
    )

    # Redis / ARQ
    REDIS_URL: str = Field(default="redis://redis:6379/0", description="Redis connection URL")

    # JWT configuration
    SECRET_KEY: constr(strip_whitespace=True, min_length=1) = Field(
        default="your_secret_key_here"
    )
    ALGORITHM: constr(strip_whitespace=True, min_length=1) = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, ge=1)

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = Field(default=100, ge=1, description="Maximum upload file size in megabytes")

    # LiteLLM debug mode: enable detailed LiteLLM logging when set to True (overridable via env var)
    LITELLM_DEBUG: bool = Field(default=False)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
