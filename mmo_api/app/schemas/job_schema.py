from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from app.schemas.base_schema import Base


WHISPER_MODELS = Literal["tiny", "base", "small", "medium", "large"]

STAGE_ORDER = ["PENDING", "DOWNLOADING", "TRANSCRIBING", "TRANSLATING", "DUBBING", "DONE"]


class JobCreate(Base):
    url: str = Field(..., min_length=10, description="YouTube or other video URL")
    whisper_model: WHISPER_MODELS = "base"

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class SubtitleSegmentOut(Base):
    id: int
    start: float
    end: float
    text: str


class JobOut(Base):
    id: str
    url: str
    status: str
    error_message: Optional[str] = None
    whisper_model: str

    detected_language: Optional[str] = None
    transcript_length: Optional[int] = None
    segment_count: Optional[int] = None
    subtitle_segments: Optional[list[SubtitleSegmentOut]] = None

    output_filename: Optional[str] = None
    output_size_bytes: Optional[int] = None

    created_at: datetime
    updated_at: datetime

    @property
    def stage_index(self) -> int:
        try:
            return STAGE_ORDER.index(self.status)
        except ValueError:
            return -1

    @property
    def is_terminal(self) -> bool:
        return self.status in ("DONE", "FAILED")

    @property
    def is_active(self) -> bool:
        return self.status in ("PENDING", "DOWNLOADING", "TRANSCRIBING", "TRANSLATING", "DUBBING")
