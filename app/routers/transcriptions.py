"""
Transcriptions Router
Proxies audio uploads and job polling to the standalone whisper-service.
"""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, File, UploadFile

from app.services.whisper_service import whisper_service

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])


@router.post("", status_code=202)
async def submit_transcription(
    audio: Annotated[UploadFile, File(...)],
) -> Dict[str, Any]:
    """Submit a voice recording for transcription. Returns a job id to poll."""
    content = await audio.read()
    return await whisper_service.submit_transcription(
        audio.filename or "voice.webm", content, audio.content_type
    )


@router.get("/{job_id}")
async def get_transcription(job_id: str) -> Dict[str, Any]:
    """Poll a transcription job's status/result."""
    return await whisper_service.get_job(job_id)
