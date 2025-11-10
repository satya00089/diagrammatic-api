"""Models for problem attempt tracking."""

from typing import Optional, List, Any
from pydantic import BaseModel, Field


class AttemptCreate(BaseModel):
    """Request model for creating/updating a problem attempt."""

    problemId: str = Field(..., description="ID of the problem being attempted")
    title: str = Field(..., description="Title of the problem")
    difficulty: Optional[str] = Field(None, description="Difficulty level")
    category: Optional[str] = Field(None, description="Problem category")
    nodes: List[Any] = Field(default_factory=list, description="Canvas nodes")
    edges: List[Any] = Field(default_factory=list, description="Canvas edges")
    elapsedTime: int = Field(
        default=0, description="Time spent on the problem in seconds"
    )
    lastAssessment: Optional[dict] = Field(
        None, description="Latest assessment result"
    )


class AttemptUpdate(BaseModel):
    """Request model for updating a problem attempt."""

    nodes: Optional[List[Any]] = None
    edges: Optional[List[Any]] = None
    elapsedTime: Optional[int] = None
    lastAssessment: Optional[dict] = None


class AttemptResponse(BaseModel):
    """Response model for problem attempt data."""

    id: str = Field(..., description="Unique attempt ID")
    userId: str = Field(..., description="User who made the attempt")
    problemId: str = Field(..., description="Problem ID")
    title: str = Field(..., description="Problem title")
    difficulty: Optional[str] = Field(None, description="Difficulty level")
    category: Optional[str] = Field(None, description="Problem category")
    nodes: List[Any] = Field(
        default_factory=list, description="Canvas nodes from attempt"
    )
    edges: List[Any] = Field(
        default_factory=list, description="Canvas edges from attempt"
    )
    elapsedTime: int = Field(
        default=0, description="Total time spent in seconds"
    )
    lastAssessment: Optional[dict] = Field(
        None, description="Latest assessment result"
    )
    assessmentCount: int = Field(
        default=0, description="Number of assessments run"
    )
    createdAt: str = Field(..., description="When the attempt was first created")
    updatedAt: str = Field(..., description="When the attempt was last updated")
    lastAttemptedAt: str = Field(
        ..., description="When the problem was last worked on"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True
