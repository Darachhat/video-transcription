from sqlalchemy.orm import Session

from app.models.job_model import JOB_MODEL
from app.schemas.job_schema import JobOut


class JobService:
    @staticmethod
    def list_jobs(session: Session) -> list[JobOut]:
        jobs = session.query(JOB_MODEL).order_by(JOB_MODEL.created_at.desc()).all()
        return [JobOut.model_validate(j) for j in jobs]

    @staticmethod
    def get_job(session: Session, job_id: str) -> JobOut | None:
        job = session.query(JOB_MODEL).filter(JOB_MODEL.id == job_id).first()
        return JobOut.model_validate(job) if job else None

    @staticmethod
    def delete_job(session: Session, job_id: str) -> bool:
        job = session.query(JOB_MODEL).filter(JOB_MODEL.id == job_id).first()
        if not job:
            return False
        session.delete(job)
        session.commit()
        return True
