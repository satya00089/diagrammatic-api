"""Service for aggregating analytics events into daily counters on S3."""

from datetime import datetime, timezone
from typing import List, Dict, Any
import json
import logging

import boto3
from botocore.exceptions import ClientError

from app.models.analytics_models import AnalyticsEvent
from app.utils.config import get_settings

logger = logging.getLogger(__name__)


class S3AnalyticsAggregator:
    """Aggregate analytics event counts into a daily JSON file on S3.

    Structure (JSON):
    {
      "events": {
        "page_view": {"/problems": 123, "/": 456},
        "cta_click": {"/": 10}
      },
      "total_events": 789,
      "updated_at": "2026-05-02T12:34:56Z"
    }
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.analytics_s3_bucket
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def _build_key(self) -> str:
        now = datetime.now(timezone.utc)
        return f"analytics/aggregates/{now.year}/{now.month:02d}/{now.day:02d}.json"

    def _get_existing(self, key: str) -> Dict[str, Any]:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            body = resp["Body"].read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                return {}
            logger.exception("Failed to read analytics aggregate from S3: %s", exc)
            return {}
        except Exception:
            logger.exception("Failed to parse analytics aggregate JSON")
            return {}

    def aggregate_events(self, events: List[AnalyticsEvent]) -> None:
        if not events:
            return

        key = self._build_key()

        # Build counts for this batch
        batch_counts: Dict[str, Dict[str, int]] = {}
        total = 0
        for e in events:
            name = e.event_name or "unknown"
            route = e.route or (e.page_url or "unknown")
            batch_counts.setdefault(name, {})
            batch_counts[name][route] = batch_counts[name].get(route, 0) + 1
            total += 1

        try:
            existing = self._get_existing(key)
            events_map = existing.get("events", {}) if isinstance(existing, dict) else {}
            total_events = existing.get("total_events", 0) if isinstance(existing, dict) else 0

            # Merge batch into existing
            for name, routes in batch_counts.items():
                if name not in events_map:
                    events_map[name] = {}
                for route, cnt in routes.items():
                    events_map[name][route] = events_map[name].get(route, 0) + cnt

            total_events = total_events + total

            payload = {
                "events": events_map,
                "total_events": total_events,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=json.dumps(payload, default=str).encode("utf-8"),
                ContentType="application/json",
            )
            logger.debug("Aggregated %d analytics events to s3://%s/%s", total, self._bucket, key)
        except Exception:
            logger.exception("Failed to aggregate analytics events to S3")


# Module-level singleton
s3_analytics_aggregator = S3AnalyticsAggregator()
