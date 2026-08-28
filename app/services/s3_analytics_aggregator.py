"""Aggregate analytics in Redis and periodically snapshot the counters to S3."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3Client
from redis import Redis

from app.models.analytics_models import AnalyticsEvent
from app.utils.config import get_settings

logger = logging.getLogger(__name__)


class RedisAnalyticsAggregator:
    """Collect counters atomically in Redis and export them to S3 in batches."""

    _redis: Redis[str] | None
    _client: S3Client

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.analytics_s3_bucket
        self._redis = (
            Redis.from_url(settings.redis_uri, decode_responses=True)
            if settings.redis_uri
            else None
        )
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self._prefix = "analytics:aggregate"

    @staticmethod
    def _encode(value: str) -> str:
        return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode(value: str) -> str:
        return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")

    def _date(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _redis_key(self, date: str) -> str:
        return f"{self._prefix}:{date}"

    def _session_hash(self, session_id: str) -> str | None:
        secret = get_settings().analytics_hmac_secret
        if not secret or not session_id:
            return None
        return hmac.new(
            secret.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def aggregate_events(
        self, events: List[AnalyticsEvent], session_id: str | None = None
    ) -> None:
        """Atomically add an accepted batch to today's Redis aggregate."""
        if not events:
            return
        if self._redis is None:
            logger.error("REDIS_URI is not configured; analytics batch was not stored")
            return

        key = self._redis_key(self._date())
        session_hash = self._session_hash(session_id or "")
        pipe = self._redis.pipeline(transaction=True)
        pipe.hincrby(key, "total_events", len(events))
        for event in events:
            name = event.event_name or "unknown"
            route = event.route or event.page_url or "unknown"
            name_key = self._encode(name)
            route_key = self._encode(route)
            pipe.hincrby(key, f"count|{name_key}|{route_key}", 1)
            if session_hash:
                pipe.hset(key, f"session|{name_key}|{route_key}|{session_hash}", 1)
        pipe.expire(key, 60 * 60 * 24 * 8)
        pipe.execute()

    def _s3_key(self, date: str) -> str:
        year, month, day = date.split("-")
        return f"analytics/aggregates/{year}/{month}/{day}.json"

    def _get_existing(self, key: str) -> tuple[Dict[str, Any], str | None]:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"].read().decode("utf-8")
            return (json.loads(body) if body else {}, response.get("ETag"))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                return {}, None
            raise

    def _merge_snapshot(
        self, existing: Dict[str, Any], fields: Dict[str, str]
    ) -> Dict[str, Any]:
        events_map = existing.setdefault("events", {})
        session_keys = existing.setdefault("_session_keys", {})
        total = int(existing.get("total_events", 0)) + int(
            fields.get("total_events", 0)
        )

        for field, value in fields.items():
            parts = field.split("|")
            if len(parts) < 3 or parts[0] not in ("count", "session"):
                continue
            name = self._decode(parts[1])
            route = self._decode(parts[2])
            events_map.setdefault(name, {})
            if parts[0] == "count":
                events_map[name][route] = events_map[name].get(route, 0) + int(value)
            elif len(parts) == 4:
                session_keys.setdefault(name, {}).setdefault(route, [])
                if parts[3] not in session_keys[name][route]:
                    session_keys[name][route].append(parts[3])

        existing["unique_sessions"] = {
            name: {route: len(hashes) for route, hashes in routes.items()}
            for name, routes in session_keys.items()
        }
        existing["total_events"] = total
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        return existing

    def _flush_snapshot(self, snapshot_key: str, date: str) -> bool:
        if self._redis is None:
            return False
        fields = self._redis.hgetall(snapshot_key)
        if not fields:
            self._redis.delete(snapshot_key)
            return True

        s3_key = self._s3_key(date)
        for attempt in range(4):
            existing, etag = self._get_existing(s3_key)
            payload = self._merge_snapshot(existing, fields)
            kwargs: Dict[str, Any] = {
                "Bucket": self._bucket,
                "Key": s3_key,
                "Body": json.dumps(payload, default=str).encode("utf-8"),
                "ContentType": "application/json",
            }
            kwargs["IfMatch" if etag else "IfNoneMatch"] = etag or "*"
            try:
                self._client.put_object(**kwargs)
                self._redis.delete(snapshot_key)
                return True
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code not in (
                    "PreconditionFailed",
                    "ConditionalRequestConflict",
                    "412",
                    "409",
                ):
                    raise
                time.sleep(0.05 * (2**attempt))
        return False

    def flush_pending(self) -> int:
        """Rotate Redis hashes and export pending counters to S3."""
        if self._redis is None:
            return 0
        lock_key = f"{self._prefix}:flush-lock"
        lock_value = str(uuid.uuid4())
        if not self._redis.set(lock_key, lock_value, nx=True, ex=55):
            return 0
        flushed = 0
        try:
            current_keys = list(
                self._redis.scan_iter(match=f"{self._prefix}:20??-??-??")
            )
            for current_key in current_keys:
                date = current_key.rsplit(":", 1)[-1]
                snapshot_key = f"{current_key}:processing:{uuid.uuid4()}"
                self._redis.rename(current_key, snapshot_key)
                if self._flush_snapshot(snapshot_key, date):
                    flushed += 1

            # Retry snapshots left behind by a process crash or a failed S3 put.
            for snapshot_key in list(
                self._redis.scan_iter(match=f"{self._prefix}:20??-??-??:processing:*")
            ):
                date = snapshot_key.split(":")[2]
                if self._flush_snapshot(snapshot_key, date):
                    flushed += 1
            return flushed
        finally:
            self._redis.delete(lock_key)


redis_analytics_aggregator = RedisAnalyticsAggregator()
# Legacy class name retained for callers importing the old service directly.
S3AnalyticsAggregator = RedisAnalyticsAggregator
# Compatibility name for the router and existing imports.
s3_analytics_aggregator = redis_analytics_aggregator
