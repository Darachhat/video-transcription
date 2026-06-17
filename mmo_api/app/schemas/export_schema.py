from datetime import datetime
from typing import Any, Optional

from pydantic import Field

from app.schemas.base_schema import Base


class SubtitleStyleIn(Base):
    fontFamily: str = "Leelawadee UI"
    fontSize: int = 28
    color: str = "#ffffff"
    bgColor: str = "#000000"
    bgOpacity: float = 0.65
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: str = "center"
    outlineColor: str = "#000000"
    outlineWidth: float = 2.0
    positionY: int = 88


class SubtitleClipIn(Base):
    id: int
    start: float
    end: float
    text: str
    style: SubtitleStyleIn
    # Deprecated: VoxCPM2 does not support named voice selection.
    # Retained for backward API compatibility; this field is ignored during synthesis.
    voice: Optional[str] = None


class ImageOverlayIn(Base):
    name:    str   = "overlay"
    src:     str             # base64 data URL (data:image/...;base64,...)
    x:       float = 5.0    # % from left
    y:       float = 5.0    # % from top
    width:   float = 20.0   # % of video width
    opacity: float = 1.0    # 0–1


class ExportRequest(Base):
    clips:          list[SubtitleClipIn]  = Field(..., min_length=0)
    image_overlays: list[ImageOverlayIn]  = []
    trim_start:     float                 = 0.0
    trim_end:       Optional[float]       = None


class ExportOut(Base):
    id: str
    job_id: str
    status: str
    output_filename: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
