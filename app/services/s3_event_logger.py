"""Service for writing canvas event logs to S3 as JSONL files (ML training data)."""

import logging
from datetime import datetime, timezone
from typing import List

import boto3
from botocore.exceptions import ClientError

from app.models.event_models import CanvasEvent
from app.utils.config import get_settings

logger = logging.getLogger(__name__)


class S3EventLogger:
    """
    Appends canvas event batches to per-session JSONL files in S3.

    S3 key pattern:
        events/{year}/{month}/{user_id}/{problem_id}_{session_id}.jsonl

    Each line is a JSON-serialised CanvasEvent (JSONL / ndjson format).
    S3 does not support true appends, so we GET → concat → PUT.
    This is safe at our write frequency (~1 batch per 15 s per session).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.training_s3_bucket
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_key(self, user_id: str, problem_id: str, session_id: str) -> str:
        now = datetime.now(timezone.utc)
        return f"events/{now.year}/{now.month:02d}/{user_id}/{problem_id}_{session_id}.jsonl"

    def _get_existing_body(self, key: str) -> str:
        """Return the existing S3 object body, or empty string if it doesn't exist."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read().decode("utf-8")
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return ""
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_events(
        self,
        user_id: str,
        problem_id: str,
        session_id: str,
        events: List[CanvasEvent],
    ) -> None:
        """
        Append *events* to the session JSONL file in S3.
        Creates the file if it does not yet exist.
        """
        if not events:
            return

        key = self._build_key(user_id, problem_id, session_id)
        new_lines = "".join(e.model_dump_json() + "\n" for e in events)

        try:
            existing_body = self._get_existing_body(key)
            updated_body = existing_body + new_lines

            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=updated_body.encode("utf-8"),
                ContentType="application/x-ndjson",
            )
            logger.debug(
                "Wrote %d events to s3://%s/%s", len(events), self._bucket, key
            )
        except ClientError:
            logger.exception("Failed to write events to S3 key %s", key)
            raise


# Module-level singleton — re-uses boto3 session across requests
s3_event_logger = S3EventLogger()
