from typing import Optional
from pydantic import Field, PostgresDsn, constr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API keys
    GLADIA_API_KEY: constr(strip_whitespace=True, min_length=1)
    GOOGLE_API_KEY: constr(strip_whitespace=True, min_length=1)

    # Database
    DATABASE_URL: PostgresDsn | str = Field(
        default="postgresql://user:password@localhost/dbname",
        description="SQLAlchemy-compatible database URL",
    )

    # JWT configuration
    SECRET_KEY: constr(strip_whitespace=True, min_length=1) = Field(
        default="your_secret_key_here"
    )
    ALGORITHM: constr(strip_whitespace=True, min_length=1) = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()