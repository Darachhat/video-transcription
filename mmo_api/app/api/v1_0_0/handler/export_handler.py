import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.system.db import getSession
from app.models.export_model import EXPORT_MODEL
from app.models.job_model import JOB_MODEL
from app.schemas.base_schema import IResponseBase
from app.schemas.export_schema import ExportOut, ExportRequest
from app.services.export_runner import run_export_job

router = APIRouter()


@router.post(
    "/pipeline/jobs/{job_id}/export",
    summary="Export dubbed video with editor subtitle styling",
    response_model=IResponseBase[ExportOut],
    status_code=201,
)
async def create_export(
    job_id: str,
    payload: ExportRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(getSession),
):
    job = session.query(JOB_MODEL).filter(JOB_MODEL.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "DONE":
        raise HTTPException(status_code=400, detail="Job must be DONE before exporting")

    clips_data = [c.model_dump() for c in payload.clips]
    export = EXPORT_MODEL(
        id=str(uuid.uuid4()),
        job_id=job_id,
        status="PENDING",
        subtitle_segments_json=json.dumps(clips_data),
    )
    session.add(export)
    session.commit()
    session.refresh(export)

    image_data = [ov.model_dump() for ov in payload.image_overlays]
    background_tasks.add_task(
        run_export_job,
        export.id,
        job_id,
        json.dumps(clips_data),
        payload.trim_start,
        payload.trim_end,
        json.dumps(image_data),
    )

    return IResponseBase[ExportOut](
        data=ExportOut.model_validate(export),
        response_status=201,
        response_code=1,
        response_msg="Export job started. Poll /pipeline/exports/{id} for status.",
    )


@router.get(
    "/pipeline/exports/{export_id}",
    summary="Poll export job status",
    response_model=IResponseBase[ExportOut],
)
async def get_export(export_id: str, session: Session = Depends(getSession)):
    export = session.query(EXPORT_MODEL).filter(EXPORT_MODEL.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    return IResponseBase[ExportOut](
        data=ExportOut.model_validate(export),
        response_status=200,
        response_code=1,
        response_msg="Export status retrieved.",
    )


@router.get(
    "/pipeline/exports/{export_id}/download",
    summary="Download the exported video with burned-in subtitles",
)
async def download_export(export_id: str, session: Session = Depends(getSession)):
    export = session.query(EXPORT_MODEL).filter(EXPORT_MODEL.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.status != "DONE" or not export.output_path:
        raise HTTPException(status_code=400, detail="Export not ready yet")
    out = Path(export.output_path)
    if not out.exists():
        raise HTTPException(status_code=404, detail="Export file missing from disk")
    return FileResponse(
        path=str(out),
        filename=export.output_filename or out.name,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{export.output_filename or out.name}"'},
    )
