from fastapi import APIRouter

from app.api.v1_0_0.handler import export_handler, job_handler

router = APIRouter()

router.include_router(job_handler.router,    prefix="", tags=["Pipeline Jobs"])
router.include_router(export_handler.router, prefix="", tags=["Export"])
