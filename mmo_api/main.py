import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1_0_0.router import router
from app.core.config import settings
from app.core.system.db import init_db
from app.core.system.log import logger
from app.middleware import BaseMiddleware
from app.schemas.base_schema import IResponseBase


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MMO Tool API starting...")
    init_db()
    yield
    logger.info("MMO Tool API stopped.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(BaseMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.WHITE_LIST_CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=IResponseBase(
            response_status=exc.status_code,
            response_code=exc.status_code,
            response_msg=str(exc.detail),
        ).model_dump(mode="json"),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content=IResponseBase(
            response_status=422,
            response_code=422,
            response_msg="Validation failed. Check request body.",
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content=IResponseBase(
            response_status=500,
            response_code=500,
            response_msg="Internal server error.",
        ).model_dump(mode="json"),
    )


app.include_router(router=router, prefix=settings.API_V1_STR)
