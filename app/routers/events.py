"""Router for canvas event log ingestion (ML training data collection)."""

import logging

from fastapi import APIRouter, BackgroundTasks, status

from app.models.event_models import CanvasEventBatch
from app.services.s3_event_logger import s3_event_logger

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/events/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of canvas events for ML training data collection",
    description="""
    Accepts a batch of canvas interaction events from the frontend and writes
    them to S3 as a JSONL file. Used to build the GNN training dataset.

    - Returns **202 Accepted** immediately; S3 write is fire-and-forget (BackgroundTask).
    - No authentication required — user_id is supplied in the payload.
    - Only structural events are stored (component types, graph size).
      No positions, labels, or user-typed text are persisted.
    """,
    response_description="Number of events accepted for processing",
)
async def ingest_event_batch(
    batch: CanvasEventBatch,
    background_tasks: BackgroundTasks,
) -> dict:
    """Accept a batch of canvas events and queue an async S3 write."""
    if not batch.events:
        return {"accepted": 0}

    background_tasks.add_task(
        s3_event_logger.append_events,
        batch.user_id,
        batch.problem_id,
        batch.session_id,
        batch.events,
    )

    logger.debug(
        "Queued %d events for user=%s problem=%s session=%s",
        len(batch.events),
        batch.user_id,
        batch.problem_id,
        batch.session_id,
    )

    return {"accepted": len(batch.events)}
