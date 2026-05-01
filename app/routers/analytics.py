"""Router for analytics event ingestion."""

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.models.analytics_models import AnalyticsEventBatch
from app.services.s3_analytics_aggregator import s3_analytics_aggregator
from app.utils.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _pseudonymize_user(user_id: str) -> str:
    # Left for compatibility; aggregated pipeline will not use pseudonymized ids
    settings = get_settings()
    secret = getattr(settings, "analytics_hmac_secret", None)
    if secret:
        return hmac.new(secret.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256).hexdigest()
    logger.debug("analytics_hmac_secret not configured; pseudonymization skipped")
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

    # For a cookie-less, aggregated pipeline we do NOT persist IPs or user ids.
    # Instead, aggregate event counts server-side into daily counters.
    background_tasks.add_task(s3_analytics_aggregator.aggregate_events, batch.events)

    logger.debug("Queued %d analytics events for aggregation", len(batch.events))

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
