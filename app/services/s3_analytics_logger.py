"""Service for writing analytics event logs to S3 as JSONL files."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

from app.models.analytics_models import AnalyticsEvent
from app.utils.config import get_settings
import json

logger = logging.getLogger(__name__)


class S3AnalyticsLogger:
    """Writes analytics event batches to S3 as per-session JSONL files.

    Key pattern:
        analytics/{year}/{month}/{user_or_anon}/{session_id}.jsonl

    Each line is a JSON object representing an analytics event, augmented
    with server-captured metadata (ip, user_agent, user_hash).
    """

    def __init__(self) -> None:
        settings = get_settings()
        # Use the configured analytics S3 bucket for all S3 writes
        self._bucket = settings.analytics_s3_bucket
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def _build_key(self, user_part: str, session_id: str) -> str:
        now = datetime.now(timezone.utc)
        return f"analytics/{now.year}/{now.month:02d}/{user_part}/{session_id}.jsonl"

    def _get_existing_body(self, key: str) -> str:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read().decode("utf-8")
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return ""
            raise

    def append_events(
        self,
        user_part: str,
        session_id: str,
        events: List[AnalyticsEvent],
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Append events to the session JSONL file in S3.

        Each event will be augmented with `ip`, `user_agent` and `user_part`.
        """
        if not events:
            return

        key = self._build_key(user_part, session_id)

        # Prepare new JSONL lines
        new_lines = ""
        for e in events:
            obj: Dict[str, Any] = e.model_dump() if hasattr(e, "model_dump") else e.dict()
            # Augment with server-side metadata
            if ip:
                obj["ip"] = ip
            if user_agent:
                obj["user_agent"] = user_agent
            obj["user_part"] = user_part
            new_lines += json.dumps(obj, default=str) + "\n"

        try:
            existing_body = self._get_existing_body(key)
            updated_body = existing_body + new_lines

            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=updated_body.encode("utf-8"),
                ContentType="application/x-ndjson",
            )
            logger.debug("Wrote %d analytics events to s3://%s/%s", len(events), self._bucket, key)
        except ClientError:
            logger.exception("Failed to write analytics events to S3 key %s", key)
            raise


# Module-level singleton
s3_analytics_logger = S3AnalyticsLogger()
