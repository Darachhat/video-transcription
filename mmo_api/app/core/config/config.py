from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "MMO Tool API"
    API_V1_STR: str = "/api/v1.0.0"
    WHITE_LIST_CORS: List[str] = ["*"]

    ENV: str = "local"
    PORT: int = 8000

    DB_DIALECT: str = "sqlite"
    DB_PATH: str = "mmo_tool.db"

    # NVIDIA Translation Configuration
    NVIDIA_API_BASE: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_API_TIMEOUT: int = 120  # Increased from 60s to allow for slower requests
    NVIDIA_TEMPERATURE: float = 0.3
    NVIDIA_MAX_TOKENS: int = 2048
    
    # Text Chunking Configuration
    TRANSCRIPT_CHUNK_SIZE: int = 1500
    SUBTITLE_BATCH_CHUNK_SIZE: int = 1200
    
    # Retry Configuration
    MAX_QUOTA_RETRIES: int = 3  # Increased from 2 to allow more retry attempts for transient errors

    @field_validator("PORT", mode="before")
    @classmethod
    def validate_port(cls, v: object) -> int:
        return int(v)


settings = Settings()
