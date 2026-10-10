import json
from types import SimpleNamespace

import google.auth

from app.services import google_analytics_service as service


def test_report_returns_setup_state_when_property_is_missing() -> None:
    report = service.get_google_analytics_report(
        30, SimpleNamespace(google_analytics_property_id=None)
    )

    assert report["status"] == "not_configured"
    assert report["propertyId"] is None
    assert "GOOGLE_ANALYTICS_PROPERTY_ID" in report["message"]


def test_report_maps_ga_metrics_and_channel_groups(monkeypatch) -> None:
    responses = [
        {
            "rows": [
                {
                    "metricValues": [
                        {"value": value}
                        for value in ("120", "35", "180", "410")
                    ]
                }
            ]
        },
        {
            "rows": [
                {
                    "dimensionValues": [{"value": "Organic Search"}],
                    "metricValues": [{"value": "95"}],
                },
                {
                    "dimensionValues": [{"value": "Direct"}],
                    "metricValues": [{"value": "60"}],
                },
            ]
        },
    ]
    requests = []

    class FakeHttp:
        def request(self, uri, method, body, headers):
            requests.append((uri, method, json.loads(body), headers))
            return SimpleNamespace(status=200), json.dumps(responses.pop(0)).encode()

    monkeypatch.setattr(google.auth, "default", lambda **_kwargs: (object(), None))
    monkeypatch.setattr(service, "_authorized_http", lambda _credentials: FakeHttp())

    report = service.get_google_analytics_report(
        7, SimpleNamespace(google_analytics_property_id="123456789")
    )

    assert report["status"] == "connected"
    assert report["activeUsers"] == 120
    assert report["newUsers"] == 35
    assert report["sessions"] == 180
    assert report["screenPageViews"] == 410
    assert report["channelGroups"] == [
        {"name": "Organic Search", "sessions": 95},
        {"name": "Direct", "sessions": 60},
    ]
    assert requests[0][0].endswith("properties/123456789:runReport")
    assert requests[0][2]["dateRanges"] == [
        {"startDate": "6daysAgo", "endDate": "today"}
    ]
    assert requests[1][2]["dimensions"] == [
        {"name": "sessionDefaultChannelGroup"}
    ]


def test_report_uses_service_account_json_when_configured(monkeypatch) -> None:
    responses = [
        {"rows": [{"metricValues": [{"value": "1"}] * 4}]},
        {"rows": []},
    ]

    class FakeHttp:
        def request(self, *_args, **_kwargs):
            return SimpleNamespace(status=200), json.dumps(
                responses.pop(0)
            ).encode()

    credentials = object()
    loaded = {}

    def load_service_account(info, scopes):
        loaded["info"] = info
        loaded["scopes"] = scopes
        return credentials

    def fail_if_adc_is_used(**_kwargs):
        raise AssertionError("ADC should not run when service-account JSON is set")

    monkeypatch.setattr(
        service.service_account.Credentials,
        "from_service_account_info",
        load_service_account,
    )
    monkeypatch.setattr(google.auth, "default", fail_if_adc_is_used)
    monkeypatch.setattr(service, "_authorized_http", lambda _credentials: FakeHttp())

    report = service.get_google_analytics_report(
        30,
        SimpleNamespace(
            google_analytics_property_id="554763049",
            google_service_account_json=json.dumps(
                {
                    "type": "service_account",
                    "client_email": "ga-reader@example.iam.gserviceaccount.com",
                    "private_key": "test-only-placeholder",
                }
            ),
        ),
    )

    assert report["status"] == "connected"
    assert loaded["info"]["client_email"] == (
        "ga-reader@example.iam.gserviceaccount.com"
    )
    assert loaded["scopes"] == [service.ANALYTICS_READONLY_SCOPE]


def test_report_rejects_invalid_service_account_json_without_leaking_it() -> None:
    secret_value = "not-a-real-private-key"
    report = service.get_google_analytics_report(
        30,
        SimpleNamespace(
            google_analytics_property_id="554763049",
            google_service_account_json=secret_value,
        ),
    )

    assert report["status"] == "error"
    assert secret_value not in report["message"]


def test_report_does_not_expose_upstream_error_details(monkeypatch) -> None:
    class ForbiddenHttp:
        def request(self, *_args, **_kwargs):
            content = b'{"error":{"message":"private detail"}}'
            return SimpleNamespace(status=403), content

    monkeypatch.setattr(google.auth, "default", lambda **_kwargs: (object(), None))
    monkeypatch.setattr(
        service, "_authorized_http", lambda _credentials: ForbiddenHttp()
    )

    report = service.get_google_analytics_report(
        30, SimpleNamespace(google_analytics_property_id="123456789")
    )

    assert report["status"] == "error"
    assert "Viewer access" in report["message"]
    assert "private detail" not in report["message"]
