"""Router for analytics event ingestion."""

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.models.analytics_models import AnalyticsEventBatch
from app.services.s3_analytics_logger import s3_analytics_logger
from app.utils.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _pseudonymize_user(user_id: str) -> str:
    settings = get_settings()
    secret = getattr(settings, "analytics_hmac_secret", None)
    if secret:
        return hmac.new(secret.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256).hexdigest()
    # Fallback - no secret configured; log a warning and return raw id (not recommended)
    logger.warning("analytics_hmac_secret not configured; storing raw user_id for analytics")
    return user_id


@router.post(
    "/analytics/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of analytics events",
    response_description="Number of events accepted for processing",
)
async def ingest_analytics_batch(
    batch: AnalyticsEventBatch,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Accept a batch of analytics events and queue an async S3 write."""
    if not batch.events:
        return {"accepted": 0}

    # Server-side pseudonymization of user_id
    if batch.user_id:
        user_part = _pseudonymize_user(batch.user_id)
    elif batch.anon_id:
        user_part = f"anon_{batch.anon_id}"
    else:
        user_part = "anonymous"

    # Capture client IP server-side
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None

    user_agent = request.headers.get("User-Agent")

    background_tasks.add_task(
        s3_analytics_logger.append_events,
        user_part,
        batch.session_id,
        batch.events,
        ip,
        user_agent,
    )

    logger.debug(
        "Queued %d analytics events for user=%s session=%s",
        len(batch.events),
        user_part,
        batch.session_id,
    )

    return {"accepted": len(batch.events)}


@router.post(
    "/analytics/event",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single analytics event (wrapped as a batch)",
)
async def ingest_analytics_event(
    batch: AnalyticsEventBatch,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    # Reuse batch handler; allows clients to POST single-event batches
    return await ingest_analytics_batch(batch, request, background_tasks)
