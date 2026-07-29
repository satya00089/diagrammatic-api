"""
Whisper Service Proxy
Forwards audio transcription requests to the standalone whisper-service,
so the browser never needs a direct URL to (or credentials for) it.
"""

import httpx
from fastapi import HTTPException

from app.utils.config import get_settings


class WhisperService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    async def submit_transcription(
        self, filename: str, content: bytes, content_type: str | None
    ) -> dict:
        """Submit audio to whisper-service and return the job it created."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"audio": (filename, content, content_type or "audio/webm")}
            try:
                resp = await client.post(
                    f"{self.settings.whisper_service_url}/transcribe", files=files
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502, detail=f"Whisper service unreachable: {exc}"
                ) from exc

        if resp.status_code == 400:
            detail = resp.json().get("detail", "Invalid audio recording.")
            raise HTTPException(status_code=400, detail=detail)
        resp.raise_for_status()
        return resp.json()

    async def get_job(self, job_id: str) -> dict:
        """Poll whisper-service for a transcription job's status/result."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self.settings.whisper_service_url}/jobs/{job_id}"
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502, detail=f"Whisper service unreachable: {exc}"
                ) from exc

        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Job not found.")
        resp.raise_for_status()
        return resp.json()


whisper_service = WhisperService()
