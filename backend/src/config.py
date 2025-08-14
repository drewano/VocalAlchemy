from pydantic import Field, PostgresDsn, constr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API keys
    AZURE_SPEECH_KEY: constr(strip_whitespace=True, min_length=1)
    AZURE_SPEECH_REGION: constr(strip_whitespace=True, min_length=1)
    AZURE_AI_API_KEY: constr(strip_whitespace=True, min_length=1)
    AZURE_AI_API_BASE: constr(strip_whitespace=True, min_length=1)
    AZURE_AI_MODEL_NAME: str = "DeepSeek-V3"

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: constr(strip_whitespace=True, min_length=1)
    AZURE_STORAGE_CONTAINER_NAME: constr(strip_whitespace=True, min_length=1)

    # Database
    DATABASE_URL: PostgresDsn | str = Field(
        default="postgresql+asyncpg://user:password@db/dbname",
        description="SQLAlchemy-compatible database URL",
    )

    # Redis / ARQ
    REDIS_URL: str = Field(
        default="redis://redis:6379/0", description="Redis connection URL"
    )

    # JWT configuration
    SECRET_KEY: constr(strip_whitespace=True, min_length=1) = Field(
        ..., description="JWT signing secret key (required)"
    )
    ALGORITHM: constr(strip_whitespace=True, min_length=1) = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, ge=1)

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=500, ge=1, description="Maximum upload file size in megabytes"
    )

    # LiteLLM debug mode: enable detailed LiteLLM logging when set to True (overridable via env var)
    LITELLM_DEBUG: bool = Field(default=False)

    # Rate limiting configuration
    RATE_LIMIT_REQUESTS: int = Field(
        default=10,
        description="Maximum number of requests allowed per timescale for rate limiting",
    )
    RATE_LIMIT_TIMESCALE_MINUTES: int = Field(
        default=1,
        description="Time period in minutes for rate limiting (e.g., 1 request per minute)",
    )

    # CORS configuration
    CORS_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:8000",
        description="Liste des origines autorisées pour le CORS, séparées par des virgules",
    )

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        # Normalise et vérifie l'absence de wildcard
        if not isinstance(value, str):
            value = str(value)
        origins = [origin.strip() for origin in value.split(",") if origin and origin.strip()]
        if any(origin == "*" or origin.endswith("/*") for origin in origins):
            raise ValueError("CORS_ALLOWED_ORIGINS ne doit pas contenir '*'. Déclarez explicitement vos origines.")
        # Recompose proprement (évite les espaces parasites)
        return ",".join(origins)

    def get_cors_allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
