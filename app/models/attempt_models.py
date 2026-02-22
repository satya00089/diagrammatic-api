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
    lastAssessment: Optional[dict] = Field(None, description="Latest assessment result")


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
    elapsedTime: int = Field(default=0, description="Total time spent in seconds")
    lastAssessment: Optional[dict] = Field(None, description="Latest assessment result")
    assessmentCount: int = Field(default=0, description="Number of assessments run")
    createdAt: str = Field(..., description="When the attempt was first created")
    updatedAt: str = Field(..., description="When the attempt was last updated")
    lastAttemptedAt: str = Field(..., description="When the problem was last worked on")
    # Public sharing fields
    isPublic: bool = Field(default=False, description="Whether the solution is public")
    publishedAt: Optional[str] = Field(None, description="When it was published")
    authorName: Optional[str] = Field(None, description="Display name of the author")
    authorPicture: Optional[str] = Field(None, description="Avatar URL of the author")
    viewCount: int = Field(default=0, description="Number of public views")

    class Config:
        """Pydantic config."""

        from_attributes = True


class PublishResponse(BaseModel):
    """Response model returned after publishing a solution."""

    attemptId: str = Field(..., description="Composite attempt ID")
    publicUrl: str = Field(..., description="Publicly accessible URL for this solution")
    publishedAt: str = Field(..., description="Timestamp when published")


class PublicSolutionResponse(BaseModel):
    """Stripped-down public view of a solution (no sensitive user data)."""

    id: str
    problemId: str
    title: str
    difficulty: Optional[str] = None
    category: Optional[str] = None
    nodes: List[Any] = Field(default_factory=list)
    edges: List[Any] = Field(default_factory=list)
    lastAssessment: Optional[dict] = None
    authorName: Optional[str] = None
    authorPicture: Optional[str] = None
    publishedAt: Optional[str] = None
    viewCount: int = 0
    elapsedTime: int = 0


class LeaderboardEntry(BaseModel):
    """Single entry in the problem leaderboard."""

    attemptId: str
    authorName: Optional[str] = None
    authorPicture: Optional[str] = None
    score: int
    publishedAt: Optional[str] = None
    elapsedTime: int = 0
