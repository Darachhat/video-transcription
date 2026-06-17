"""
Runs the mmo-tool dubbing pipeline in a background thread,
updating the job record in the database at each stage transition.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Add mmo_api root so we can import from src/
# Layout: mmo_api/app/services/pipeline_runner.py → mmo_api/ is 3 levels up
_MMO_TOOL_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MMO_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_MMO_TOOL_ROOT))

from dotenv import load_dotenv
load_dotenv(_MMO_TOOL_ROOT / ".env")

from app.core.system.log import logger

TEMP_DIR = str(_MMO_TOOL_ROOT / "temp_assets")
OUTPUT_DIR = str(_MMO_TOOL_ROOT / "output")


def _get_job(session, job_id: str):
    from app.models.job_model import JOB_MODEL
    return session.query(JOB_MODEL).filter(JOB_MODEL.id == job_id).first()


def _set_status(session, job, status: str) -> None:
    job.status = status
    job.updated_at = datetime.utcnow()
    session.commit()
    logger.info(f"[Job {job.id}] → {status}")


def run_pipeline_job(job_id: str, url: str, whisper_model: str = "base") -> None:
    """Entry point called by FastAPI BackgroundTasks."""
    from app.core.system.db import getStaticSession

    session = getStaticSession()
    job = None

    try:
        job = _get_job(session, job_id)
        if not job:
            logger.error(f"run_pipeline_job: job {job_id} not found")
            return

        # ── Stage 1: Download ──────────────────────────────────────────────
        _set_status(session, job, "DOWNLOADING")
        from src.downloader import download_video_and_audio
        downloaded = download_video_and_audio(url, output_dir=TEMP_DIR)

        # ── Stage 2: Transcribe ────────────────────────────────────────────
        _set_status(session, job, "TRANSCRIBING")
        from src.transcription import transcribe_audio
        transcript = transcribe_audio(downloaded["audio_path"], model_size=whisper_model)

        job.detected_language = transcript.get("language")
        job.transcript_length = len(transcript.get("transcript", ""))
        job.segment_count = len(transcript.get("segments", []))
        job.updated_at = datetime.utcnow()
        session.commit()

        # ── Stage 3: Translate ────────────────────────────────────────────
        _set_status(session, job, "TRANSLATING")
        from src.translator import (
            translate_segments_to_khmer_subtitles,
            translate_to_khmer_script,
        )
        source_lang = transcript.get("language") or "auto"
        khmer = translate_to_khmer_script(transcript["transcript"], source_lang=source_lang)
        subtitles = translate_segments_to_khmer_subtitles(
            transcript.get("segments", []), source_lang=source_lang
        )

        # Store subtitle segments in job for editor access
        job.subtitle_segments_json = json.dumps(subtitles.get("segments", []))
        job.updated_at = datetime.utcnow()
        session.commit()

        # ── Stage 4: Dub (TTS + Merge) ─────────────────────────────────────
        _set_status(session, job, "DUBBING")
        from src.dubbing import generate_dubbed_video
        result = generate_dubbed_video(
            original_video_path=downloaded["video_path"],
            khmer_script=khmer["khmer_script"],
            output_dir=OUTPUT_DIR,
            subtitle_segments=[],   # subtitles are added later via the editor export
            burn_subtitles=False,
            temp_dir=TEMP_DIR,
        )

        # ── Done ──────────────────────────────────────────────────────────
        output_path = result.get("output_video_path") or ""
        output_file = Path(output_path)
        job.status = "DONE"
        job.output_path = output_path
        job.output_filename = output_file.name if output_file.exists() else None
        job.output_size_bytes = output_file.stat().st_size if output_file.exists() else None
        job.updated_at = datetime.utcnow()
        session.commit()
        logger.info(f"[Job {job_id}] DONE → {output_path}")

    except Exception as exc:
        logger.error(f"[Job {job_id}] FAILED: {exc}", exc_info=True)
        try:
            if job is None:
                job = _get_job(session, job_id)
            if job:
                job.status = "FAILED"
                job.error_message = str(exc)[:2000]
                job.updated_at = datetime.utcnow()
                session.commit()
        except Exception as inner:
            logger.error(f"[Job {job_id}] Could not persist FAILED status: {inner}")
    finally:
        session.close()
