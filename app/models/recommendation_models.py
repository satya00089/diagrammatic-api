"""
Data models for AI-powered recommendation system.

Following SOLID principles:
- Single Responsibility: Each model has one clear purpose
- Open/Closed: Extensible through inheritance and composition
- Interface Segregation: Minimal, focused interfaces
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class ComponentInfo(BaseModel):
    """Represents a component on the canvas for context analysis."""

    id: str
    type: str
    label: str
    has_description: bool = Field(
        default=False, description="Whether component has a meaningful description"
    )
    properties: Optional[dict] = Field(default_factory=dict)


class ConnectionInfo(BaseModel):
    """Represents a connection between components."""

    source: str
    target: str
    type: Optional[str] = None
    has_label: bool = Field(
        default=False, description="Whether connection has a descriptive label"
    )


class UserIntentInfo(BaseModel):
    """User's stated intent for the design."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Ensure title is not just whitespace."""
        if not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip()


class CanvasContextInfo(BaseModel):
    """Current state of the canvas for context-aware recommendations."""

    node_count: int = Field(ge=0, description="Total number of components")
    edge_count: int = Field(ge=0, description="Total number of connections")
    component_types: List[str] = Field(
        default_factory=list, description="List of unique component types present"
    )
    is_empty: bool = Field(default=True, description="Whether canvas is empty")

    @field_validator("node_count", "edge_count")
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        """Ensure counts are non-negative."""
        if v < 0:
            raise ValueError("Count must be non-negative")
        return v


class RecommendationRequest(BaseModel):
    """
    Request model for AI-powered recommendations.

    Designed for high precision by providing rich context:
    - User intent (what they want to build)
    - Current canvas state (what they have)
    - Detailed component information
    """

    user_intent: Optional[UserIntentInfo] = None
    canvas_context: CanvasContextInfo
    components: List[ComponentInfo] = Field(default_factory=list)
    connections: List[ConnectionInfo] = Field(default_factory=list)
    max_suggestions: int = Field(
        default=5, ge=1, le=10, description="Maximum number of suggestions to return"
    )

    @field_validator("max_suggestions")
    @classmethod
    def validate_max_suggestions(cls, v: int) -> int:
        """Ensure reasonable limit on suggestions."""
        if v < 1 or v > 10:
            raise ValueError("max_suggestions must be between 1 and 10")
        return v


class RecommendationItem(BaseModel):
    """
    A single recommendation item.

    Designed for actionability with clear metadata for filtering.
    """

    id: str = Field(..., description="Unique identifier for this recommendation")
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    icon: str = Field(default="💡", max_length=10)
    category: Literal[
        "component", "pattern", "tip", "best-practice", "optimization"
    ] = Field(..., description="Category of recommendation for filtering")
    priority: int = Field(
        ..., ge=1, le=10, description="Priority score (1-10, higher = more important)"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI confidence score (0.0-1.0) for precision filtering",
    )
    action_type: Literal[
        "add-component", "add-pattern", "info-only", "connect", "refactor"
    ] = Field(..., description="Type of action this recommendation suggests")

    # Optional action metadata
    component_id: Optional[str] = Field(
        default=None, description="Component ID to add (for add-component actions)"
    )
    component_ids: Optional[List[str]] = Field(
        default=None, description="Multiple component IDs (for add-pattern actions)"
    )
    reasoning: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Why this recommendation is relevant (for transparency)",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is in valid range."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """Ensure priority is in valid range."""
        if v < 1 or v > 10:
            raise ValueError("Priority must be between 1 and 10")
        return v


class RecommendationResponse(BaseModel):
    """
    Response model for recommendations.

    Includes metadata for quality assessment and debugging.
    """

    recommendations: List[RecommendationItem] = Field(
        default_factory=list,
        description="List of recommendations, ordered by priority and confidence",
    )
    total_count: int = Field(
        ge=0, description="Total number of recommendations before filtering"
    )
    filtered_count: int = Field(
        ge=0, description="Number of recommendations after precision filtering"
    )
    min_confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold used for filtering",
    )
    context_summary: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Brief summary of the analysis context",
    )
    processing_time_ms: Optional[int] = Field(
        default=None, ge=0, description="Time taken to generate recommendations"
    )

    @field_validator("total_count", "filtered_count")
    @classmethod
    def validate_counts(cls, v: int) -> int:
        """Ensure counts are non-negative."""
        if v < 0:
            raise ValueError("Count must be non-negative")
        return v
