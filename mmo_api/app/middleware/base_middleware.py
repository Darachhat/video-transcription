from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.system.log import logger


class BaseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except RequestValidationError:
            raise
        except Exception as exc:
            logger.error(f"BaseMiddleware caught: {exc}")
            raise
