import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.system.db import getSession
from app.models.job_model import JOB_MODEL
from app.schemas.base_schema import IResponseBase
from app.schemas.job_schema import JobCreate, JobOut
from app.services.job_service import JobService
from app.services.pipeline_runner import run_pipeline_job

router = APIRouter()


@router.post(
    "/pipeline/jobs",
    summary="Submit a new dubbing job",
    response_model=IResponseBase[JobOut],
    status_code=201,
)
async def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(getSession),
):
    job = JOB_MODEL(
        id=str(uuid.uuid4()),
        url=payload.url,
        whisper_model=payload.whisper_model,
        status="PENDING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    background_tasks.add_task(run_pipeline_job, job.id, payload.url, payload.whisper_model)

    return IResponseBase[JobOut](
        data=JobOut.model_validate(job),
        response_status=201,
        response_code=1,
        response_msg="Job submitted. Pipeline is starting.",
    )


@router.get(
    "/pipeline/jobs",
    summary="List all jobs",
    response_model=IResponseBase[list[JobOut]],
)
async def list_jobs(session: Session = Depends(getSession)):
    jobs = JobService.list_jobs(session)
    return IResponseBase[list[JobOut]](
        data=jobs,
        response_status=200,
        response_code=1,
        response_msg="Jobs retrieved successfully.",
    )


@router.get(
    "/pipeline/jobs/{job_id}",
    summary="Get job status (poll this endpoint)",
    response_model=IResponseBase[JobOut],
)
async def get_job(job_id: str, session: Session = Depends(getSession)):
    job = JobService.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IResponseBase[JobOut](
        data=job,
        response_status=200,
        response_code=1,
        response_msg="Job retrieved successfully.",
    )


@router.get(
    "/pipeline/jobs/{job_id}/wait",
    summary="Long-poll for job status change",
    response_model=IResponseBase[JobOut],
)
async def wait_for_job_update(
    job_id: str,
    current_status: str = Query(..., description="Current status the client already knows about"),
    timeout: int = Query(25, ge=5, le=60, description="Max seconds to wait before returning"),
    session: Session = Depends(getSession),
):
    """Long-poll endpoint. Holds the connection open until the job status
    changes from ``current_status``, or ``timeout`` seconds elapse.
    Returns the latest job state either way — the client can tell whether
    anything changed by comparing the returned status to what it sent.
    """
    POLL_INTERVAL = 0.5  # seconds between DB checks
    elapsed = 0.0

    while elapsed < timeout:
        session.expire_all()  # force re-read from DB on each iteration
        job = JobService.get_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != current_status:
            # Status changed — return immediately
            return IResponseBase[JobOut](
                data=job,
                response_status=200,
                response_code=1,
                response_msg="Job status updated.",
            )

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    # Timeout reached — return current state so client can reset its timer
    session.expire_all()
    job = JobService.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IResponseBase[JobOut](
        data=job,
        response_status=200,
        response_code=1,
        response_msg="Job retrieved successfully.",
    )


@router.delete(
    "/pipeline/jobs/{job_id}",
    summary="Delete a job record",
    response_model=IResponseBase[None],
)
async def delete_job(job_id: str, session: Session = Depends(getSession)):
    deleted = JobService.delete_job(session, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return IResponseBase[None](
        data=None,
        response_status=200,
        response_code=1,
        response_msg="Job deleted successfully.",
    )


@router.get(
    "/pipeline/jobs/{job_id}/download",
    summary="Download the dubbed video output",
)
async def download_job_output(job_id: str, session: Session = Depends(getSession)):
    job = session.query(JOB_MODEL).filter(JOB_MODEL.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "DONE" or not job.output_path:
        raise HTTPException(status_code=400, detail="Output not ready. Job must be in DONE status.")

    output_path = Path(job.output_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file missing from disk.")

    return FileResponse(
        path=str(output_path),
        filename=job.output_filename or output_path.name,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{job.output_filename or output_path.name}"'},
    )


@router.get(
    "/pipeline/jobs/{job_id}/subtitles",
    summary="Get subtitle segments for the editor",
    response_model=IResponseBase[list],
)
async def get_job_subtitles(job_id: str, session: Session = Depends(getSession)):
    import json
    job = session.query(JOB_MODEL).filter(JOB_MODEL.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.subtitle_segments_json:
        return IResponseBase[list](
            data=[],
            response_status=200,
            response_code=1,
            response_msg="No subtitle segments stored for this job.",
        )
    segments = json.loads(job.subtitle_segments_json)
    return IResponseBase[list](
        data=segments,
        response_status=200,
        response_code=1,
        response_msg="Subtitle segments retrieved successfully.",
    )
