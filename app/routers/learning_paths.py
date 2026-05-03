"""API router for learning paths endpoints."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, Header

from app.services.auth_service import auth_service
from app.services.dynamodb_service import dynamodb_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Determine data directory relative to repo root
# file structure: <repo>/diagrammatic-api/app/routers/learning_paths.py
# repo root is parents[3]
BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "diagrammatic-data" / "learning-paths"
SAMPLE_FILE = DATA_DIR / "sample-learning-path.json"


def _read_sample():
    if not SAMPLE_FILE.exists():
        logger.warning("Learning path sample file not found: %s", SAMPLE_FILE)
        return None
    with SAMPLE_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@router.get("/learning-paths", summary="List available learning paths")
async def list_learning_paths():
    try:
        data = _read_sample()
        if not data:
            return []
        return [data]
    except Exception as e:
        logger.error("Error reading learning paths: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load learning paths")


@router.get("/learning-paths/{slug}", summary="Get learning path by slug")
async def get_learning_path(slug: str):
    try:
        data = _read_sample()
        if not data or data.get("slug") != slug:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Learning path not found"
            )
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching learning path %s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Failed to fetch learning path")


@router.get("/learning-paths/{path_id}/progress", summary="Get user progress for a path")
async def get_progress(path_id: str, authorization: str | None = Header(None)):
    """Return the authenticated user's progress for the given learning path.

    Requires a Bearer token in the `Authorization` header. Returns a JSON object
    with `completed` as an array of lesson IDs. If the user has no saved
    progress, an empty array is returned.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    token = authorization.split(" ")[1] if " " in authorization else authorization
    try:
        payload = auth_service.decode_token(token)
        user_id = payload.get("user_id")
    except Exception as e:
        logger.debug("Invalid token when fetching progress: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    prefs = dynamodb_service.get_user_preferences(user_id) or {}
    learning_progress = prefs.get("learningProgress") or {}
    completed = learning_progress.get(path_id, [])
    return {"completed": completed}


@router.post("/learning-paths/{path_id}/progress", summary="Record user progress")
async def post_progress(path_id: str, payload: dict, authorization: str | None = Header(None)):
    """Persist the authenticated user's progress for the given learning path.

    Payload should be a JSON object with a `completed` field containing an
    array of lesson IDs. The progress is stored in the user's `preferences`
    under the `learningProgress` key using DynamoDB.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    token = authorization.split(" ")[1] if " " in authorization else authorization
    try:
        payload_token = auth_service.decode_token(token)
        user_id = payload_token.get("user_id")
    except Exception as e:
        logger.debug("Invalid token when saving progress: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    if not isinstance(payload, dict) or "completed" not in payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload: expected { completed: string[] }")

    completed = payload.get("completed") or []

    # Merge into existing preferences
    prefs = dynamodb_service.get_user_preferences(user_id) or {}
    learning_progress = prefs.get("learningProgress", {})
    learning_progress[path_id] = completed

    # Persist preferences back to DynamoDB
    updated = dynamodb_service.update_user_preferences(user_id, {**prefs, "learningProgress": learning_progress})
    if not updated:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save learning progress")

    return {"status": "ok", "learningProgress": learning_progress}
