import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Environment
    ENV: Literal["development", "production"] = "development"
    PROJECT_NAME: str = "SentinAI-SMARTLVF"
    
    # API Keys
    GROQ_API_KEY: str
    GOOGLE_API_KEY: str

    # Infrastructure Storage Configurations
    SQLITE_DB_PATH: str = "sentinai_state.db"
    CHROMA_PERSIST_DIR: str = "./.chroma_data"
    
    # Production Infrastructure Swaps
    POSTGRES_DSN: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False

    # Rate Limiting Parameters
    RATE_LIMIT_TOKENS: int = 100
    RATE_LIMIT_REFILL_RATE: float = 10.0  # Tokens per second

    # JWT Authentication Parameters
    JWT_SECRET_KEY: str = "sentinai-super-secret-development-key-1234"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

settings = Settings()