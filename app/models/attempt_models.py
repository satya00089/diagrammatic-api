"""Models for problem attempt tracking."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from app.models.problem_models import RequirementSpec
from app.models.reasoning_models import InterviewSession, ReasoningContext


class AssessmentHistoryEntry(BaseModel):
    """Compact review/check history, including explicitly unscored checks."""

    id: str
    score: Optional[int] = Field(default=None, ge=0, le=100)
    scoreAvailable: bool = True
    findingCount: int = Field(default=0, ge=0)
    createdAt: str
    source: Optional[str] = None
    addressedFindingIds: List[str] = Field(default_factory=list)
    rubricVersion: Optional[str] = None
    requirementRevision: Optional[str] = None
    modelVersion: Optional[str] = None
    inputFingerprint: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_provenance(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        for camel, snake in (
            ("scoreAvailable", "score_available"),
            ("rubricVersion", "rubric_version"),
            ("requirementRevision", "requirement_revision"),
            ("modelVersion", "model_version"),
            ("inputFingerprint", "input_fingerprint"),
        ):
            if camel not in data and snake in data:
                data[camel] = data[snake]
        if (
            data.get("source") == "rule_based"
            or data.get("score") is None
            or data.get("score_available") is False
        ):
            data["scoreAvailable"] = False
        return data


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
    lastAssessment: Optional[Dict[str, Any]] = Field(
        None, description="Latest successful AI assessment result"
    )
    lastAssessmentCheck: Optional[Dict[str, Any]] = Field(
        None, description="Latest review/check result, including unavailable checks"
    )
    problemRequirementSpec: Optional[RequirementSpec] = None
    reasoningContext: Optional[ReasoningContext] = None
    interviewSession: Optional[InterviewSession] = None
    addressedFindingIds: List[str] = Field(default_factory=list)


class AttemptUpdate(BaseModel):
    """Request model for updating a problem attempt."""

    nodes: Optional[List[Any]] = None
    edges: Optional[List[Any]] = None
    elapsedTime: Optional[int] = None
    lastAssessment: Optional[Dict[str, Any]] = None
    lastAssessmentCheck: Optional[Dict[str, Any]] = None
    problemRequirementSpec: Optional[RequirementSpec] = None
    reasoningContext: Optional[ReasoningContext] = None
    interviewSession: Optional[InterviewSession] = None
    addressedFindingIds: Optional[List[str]] = None


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
    lastAssessment: Optional[Dict[str, Any]] = Field(
        None, description="Latest successful AI assessment result"
    )
    lastAssessmentCheck: Optional[Dict[str, Any]] = None
    problemRequirementSpec: Optional[RequirementSpec] = None
    reasoningContext: Optional[ReasoningContext] = None
    interviewSession: Optional[InterviewSession] = None
    assessmentCount: int = Field(default=0, description="Number of scored AI assessments")
    assessmentHistory: List[AssessmentHistoryEntry] = Field(default_factory=list)
    addressedFindingIds: List[str] = Field(default_factory=list)
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
    lastAssessment: Optional[Dict[str, Any]] = None
    lastAssessmentCheck: Optional[Dict[str, Any]] = None
    problemRequirementSpec: Optional[RequirementSpec] = None
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
