"""Models for system design assessment responses."""

from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Enumeration for feedback types."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"

class FeedbackCategory(str, Enum):
    """Enumeration for feedback categories."""
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE = "performance"
    COST = "cost"
    REQUIREMENTS = "requirements"
    CONSTRAINTS = "constraints"

class ValidationFeedback(BaseModel):
    """Model for validation feedback."""
    type: FeedbackType
    message: str
    category: FeedbackCategory
    priority: Optional[int] = Field(default=1, ge=1, le=5)

class ScoreBreakdown(BaseModel):
    """Model for detailed score breakdown."""
    scalability: int = Field(ge=0, le=100)
    reliability: int = Field(ge=0, le=100)
    security: int = Field(ge=0, le=100)
    maintainability: int = Field(ge=0, le=100)
    performance: Optional[int] = Field(default=None, ge=0, le=100)
    cost_efficiency: Optional[int] = Field(default=None, ge=0, le=100)
    requirements_alignment: Optional[int] = Field(default=None, ge=0, le=100)
    constraint_compliance: Optional[int] = Field(default=None, ge=0, le=100)

class AssessmentResponse(BaseModel):
    """Model for system design assessment response."""
    is_valid: bool
    overall_score: int = Field(ge=0, le=100)
    scores: ScoreBreakdown
    feedback: List[ValidationFeedback]
    strengths: List[str]
    improvements: List[str]
    missing_components: List[str]
    suggestions: List[str]
    assessment_id: Optional[str] = None
    processing_time_ms: Optional[int] = None
