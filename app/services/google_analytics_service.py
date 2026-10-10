"""Read-only GA4 reporting for the protected super-admin dashboard."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

import google.auth
import google_auth_httplib2
import httplib2
from google.auth.exceptions import DefaultCredentialsError

from app.utils.config import Settings, get_settings

logger = logging.getLogger(__name__)

ANALYTICS_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
GA_DATA_API_URL = (
    "https://analyticsdata.googleapis.com/v1beta/properties/"
    "{property_id}:runReport"
)
REPORT_TIMEOUT_SECONDS = 15
METRIC_NAMES = ("activeUsers", "newUsers", "sessions", "screenPageViews")


class GoogleAnalyticsApiError(Exception):
    """An upstream GA Data API response that can be safely classified."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Google Analytics Data API returned HTTP {status_code}")


def _authorized_http(credentials: Any) -> google_auth_httplib2.AuthorizedHttp:
    return google_auth_httplib2.AuthorizedHttp(
        credentials,
        http=httplib2.Http(timeout=REPORT_TIMEOUT_SECONDS),
    )


def _run_report(
    http: google_auth_httplib2.AuthorizedHttp,
    property_id: str,
    request_body: Dict[str, Any],
) -> Dict[str, Any]:
    response, content = http.request(
        GA_DATA_API_URL.format(property_id=property_id),
        method="POST",
        body=json.dumps(request_body),
        headers={"Content-Type": "application/json"},
    )
    if response.status < 200 or response.status >= 300:
        raise GoogleAnalyticsApiError(response.status)
    return json.loads(content.decode("utf-8"))


def _metric_value(row: Dict[str, Any] | None, index: int) -> int:
    if not row:
        return 0
    values = row.get("metricValues", [])
    if index >= len(values):
        return 0
    try:
        return int(values[index].get("value", "0"))
    except (TypeError, ValueError):
        return 0


def _channel_groups(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    groups = []
    for row in report.get("rows", []):
        dimensions = row.get("dimensionValues", [])
        name = dimensions[0].get("value", "Unassigned") if dimensions else "Unassigned"
        groups.append(
            {
                "name": name or "Unassigned",
                "sessions": _metric_value(row, 0),
            }
        )
    return groups


def _error_report(
    status: str, message: str, property_id: str | None = None
) -> Dict[str, Any]:
    return {
        "status": status,
        "propertyId": property_id,
        "message": message,
        "channelGroups": [],
    }


def get_google_analytics_report(
    days: int, settings: Settings | None = None
) -> Dict[str, Any]:
    """Return aggregate GA4 metrics without exposing user-level data."""
    resolved_settings = settings or get_settings()
    property_id = (resolved_settings.google_analytics_property_id or "").strip()
    if not property_id:
        return _error_report(
            "not_configured",
            "Set GOOGLE_ANALYTICS_PROPERTY_ID and configure Google credentials "
            "on the API server.",
        )
    if not re.fullmatch(r"\d+", property_id):
        return _error_report(
            "error",
            "The configured Google Analytics property ID must contain digits only.",
        )

    try:
        credentials, _ = google.auth.default(scopes=[ANALYTICS_READONLY_SCOPE])
    except DefaultCredentialsError:
        return _error_report(
            "not_configured",
            "Configure Google Application Default Credentials on the API server.",
            property_id,
        )
    except Exception as exc:  # Credentials must never be included in the API response.
        logger.warning(
            "Google Analytics credential initialization failed (%s)",
            type(exc).__name__,
        )
        return _error_report(
            "error",
            "Google Analytics credentials could not be initialized. Check the "
            "API server configuration.",
            property_id,
        )

    try:
        http = _authorized_http(credentials)
        date_range = {
            "startDate": f"{days - 1}daysAgo",
            "endDate": "today",
        }
        totals = _run_report(
            http,
            property_id,
            {
                "dateRanges": [date_range],
                "metrics": [{"name": name} for name in METRIC_NAMES],
            },
        )
        channels = _run_report(
            http,
            property_id,
            {
                "dateRanges": [date_range],
                "dimensions": [{"name": "sessionDefaultChannelGroup"}],
                "metrics": [{"name": "sessions"}],
                "orderBys": [
                    {"metric": {"metricName": "sessions"}, "desc": True}
                ],
                "limit": "5",
            },
        )
    except GoogleAnalyticsApiError as exc:
        logger.warning(
            "Google Analytics Data API request failed with HTTP %s", exc.status_code
        )
        if exc.status_code in (401, 403):
            message = (
                "Check that the Analytics Data API is enabled and the API service "
                "account has Viewer access to this property."
            )
        elif exc.status_code == 404:
            message = (
                "The configured Google Analytics property was not found or is "
                "not accessible to the API service account."
            )
        else:
            message = "Google Analytics could not return a report. Try again later."
        return _error_report("error", message, property_id)
    except Exception as exc:
        logger.warning(
            "Google Analytics report request failed (%s)", type(exc).__name__
        )
        return _error_report(
            "error",
            "Google Analytics could not return a report. Check the API server "
            "logs and try again.",
            property_id,
        )

    rows = totals.get("rows", [])
    total_row = rows[0] if rows else None
    return {
        "status": "connected",
        "propertyId": property_id,
        "activeUsers": _metric_value(total_row, 0),
        "newUsers": _metric_value(total_row, 1),
        "sessions": _metric_value(total_row, 2),
        "screenPageViews": _metric_value(total_row, 3),
        "channelGroups": _channel_groups(channels),
        "message": None,
    }
