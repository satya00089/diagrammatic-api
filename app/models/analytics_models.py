"""Pydantic models for analytics event ingestion."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyticsEvent(BaseModel):
    """A single analytics event captured on the frontend."""

    ts: int = Field(..., description="Unix timestamp in milliseconds")
    event_name: str = Field(..., description="Event type/name")
    page_url: Optional[str] = Field(None, description="Full page URL")
    route: Optional[str] = Field(None, description="SPA route or path")
    page_title: Optional[str] = Field(None, description="Document title")
    event_props: Optional[Dict[str, Any]] = Field(
        None, description="Optional event properties"
    )
    time_on_page_ms: Optional[int] = Field(
        None, description="Time spent on page for time_on_page events"
    )


class AnalyticsEventBatch(BaseModel):
    """Batch of analytics events sent from the frontend.

    The batch includes optional user identifiers which will be
    pseudonymized server-side before persistence.
    """

    user_id: Optional[str] = Field(None, description="Authenticated user id")
    anon_id: Optional[str] = Field(
        None, description="Anonymous client id (when not authenticated)"
    )
    session_id: str = Field(..., description="Stable browser session id")
    events: List[AnalyticsEvent] = Field(..., description="Ordered list of events")
