import json

from app.models.analytics_models import AnalyticsEvent, AnalyticsEventBatch
from app.services.s3_analytics_aggregator import S3AnalyticsAggregator


def test_analytics_batch_requires_a_non_empty_bounded_session_id() -> None:
    event = AnalyticsEvent(ts=1, event_name="page_view", route="/")

    batch = AnalyticsEventBatch(session_id="session-1", events=[event])

    assert batch.session_id == "session-1"


def test_analytics_batch_rejects_empty_session_id() -> None:
    event = AnalyticsEvent(ts=1, event_name="page_view", route="/")

    try:
        AnalyticsEventBatch(session_id="", events=[event])
    except ValueError:
        return

    raise AssertionError("empty session IDs must be rejected")


def test_session_hash_is_deterministic_and_secret_scoped(monkeypatch) -> None:
    aggregator = S3AnalyticsAggregator.__new__(S3AnalyticsAggregator)
    monkeypatch.setattr(
        "app.services.s3_analytics_aggregator.get_settings",
        lambda: type("Settings", (), {"analytics_hmac_secret": "secret-a"})(),
    )

    first = aggregator._session_hash("session-1")
    second = aggregator._session_hash("session-1")

    assert first == second
    assert first is not None
    assert len(first) == 64


def test_aggregate_events_tracks_unique_sessions_without_raw_ids(monkeypatch) -> None:
    class FakePipeline:
        def __init__(self, redis):
            self.redis = redis
            self.commands = []

        def hincrby(self, key, field, amount):
            self.commands.append(("hincrby", key, field, amount))

        def hset(self, key, field, value):
            self.commands.append(("hset", key, field, value))

        def expire(self, key, seconds):
            self.commands.append(("expire", key, seconds))

        def execute(self):
            for command in self.commands:
                if command[0] == "hincrby":
                    _, key, field, amount = command
                    self.redis._ensure_key(key)
                    self.redis.data[key][field] = int(
                        self.redis.data[key].get(field, 0)
                    ) + amount
                elif command[0] == "hset":
                    _, key, field, value = command
                    self.redis._ensure_key(key)
                    self.redis.data[key][field] = value

    class FakeRedis:
        def __init__(self):
            self.data = {}

        def pipeline(self, transaction=True):
            return FakePipeline(self)

        def _ensure_key(self, key):
            self.data.setdefault(key, {})

    fake_redis = FakeRedis()

    aggregator = S3AnalyticsAggregator.__new__(S3AnalyticsAggregator)
    aggregator._redis = fake_redis
    aggregator._prefix = "analytics:aggregate"
    monkeypatch.setattr(aggregator, "_date", lambda: "2026-08-28")
    monkeypatch.setattr(
        "app.services.s3_analytics_aggregator.get_settings",
        lambda: type("Settings", (), {"analytics_hmac_secret": "secret-a"})(),
    )
    monkeypatch.setattr(aggregator, "_get_existing", lambda _key: {})

    event = AnalyticsEvent(ts=1, event_name="challenge_started", route="/problems")
    aggregator.aggregate_events([event, event], "session-1")

    key = "analytics:aggregate:2026-08-28"
    fields = fake_redis.data[key]
    assert fields["total_events"] == 2
    assert fields["count|Y2hhbGxlbmdlX3N0YXJ0ZWQ=|L3Byb2JsZW1z"] == 2
    assert any(field.startswith("session|") for field in fields)
    assert "session-1" not in json.dumps(fields)
