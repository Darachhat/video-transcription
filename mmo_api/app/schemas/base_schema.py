from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field
from ulid import ULID


DataType = TypeVar("DataType")


def _trace_id() -> str:
    return str(ULID())


class Base(BaseModel):
    class Config:
        from_attributes = True


class IResponseBase(BaseModel, Generic[DataType]):
    trace_id: str = Field(default_factory=_trace_id)
    data: Optional[DataType] = None
    response_status: int
    response_code: int
    response_msg: str
