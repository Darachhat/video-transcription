import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base


class JOB_MODEL(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    whisper_model: Mapped[str] = mapped_column(String(20), default="base", nullable=False)

    # Transcription metadata
    detected_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transcript_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subtitle_segments_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Output
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
