"""Pydantic models for canvas event logging (ML training data collection)."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CanvasEvent(BaseModel):
    """A single canvas interaction event captured on the frontend."""

    ts: int = Field(..., description="Unix timestamp in milliseconds")
    action: Literal["add_node", "delete_node", "add_edge"]
    # For add_node / delete_node
    type: Optional[str] = Field(None, description="Component type (e.g. 'cache', 'load-balancer')")
    # For add_edge
    source_type: Optional[str] = Field(None, description="Source node component type")
    target_type: Optional[str] = Field(None, description="Target node component type")
    # Graph state at the time of the event
    graph_node_count: int = Field(..., description="Number of nodes on canvas at event time")
    graph_edge_count: int = Field(..., description="Number of edges on canvas at event time")


class CanvasEventBatch(BaseModel):
    """Batch of canvas events sent from the frontend."""

    user_id: str = Field(..., description="Authenticated user ID")
    problem_id: str = Field(..., description="Problem or canvas ID being worked on")
    session_id: str = Field(..., description="UUID identifying the browser session")
    events: List[CanvasEvent] = Field(..., description="Ordered list of canvas events")
