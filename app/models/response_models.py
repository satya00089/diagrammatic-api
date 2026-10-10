"""Models for system design assessment responses."""

from typing import Dict, List, Literal, Optional, cast
from enum import Enum
from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Enumeration for feedback types."""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class FindingSeverity(str, Enum):
    """Severity used for actionable architecture findings."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    IMPROVEMENT = "improvement"
    POSITIVE = "positive"


class AssessmentSource(str, Enum):
    """How the assessment was produced."""

    AI = "ai"
    RULE_BASED = "rule_based"


class AssessmentVerdict(str, Enum):
    STRONG_ALIGNMENT = "strong_alignment"
    NEEDS_REVISION = "needs_revision"
    MORE_CONTEXT_NEEDED = "more_context_needed"
    UNAVAILABLE = "unavailable"


class FindingKind(str, Enum):
    DEFECT = "defect"
    CLARIFICATION = "clarification"
    EXTENSION = "extension"
    STRENGTH = "strength"


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
    COMPONENT_DESCRIPTION = "component_description"
    CONNECTION_REASONING = "connection_reasoning"
    OBSERVABILITY = "observability"
    DELIVERABILITY = "deliverability"


class ValidationFeedback(BaseModel):
    """Model for validation feedback."""

    type: FeedbackType
    message: str
    category: FeedbackCategory
    priority: Optional[int] = Field(default=1, ge=1, le=5)


class ReviewFinding(BaseModel):
    """A structured finding that explains and prioritises an observation."""

    title: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    recommendation: Optional[str] = None
    severity: FindingSeverity = FindingSeverity.IMPROVEMENT
    evidence_ids: List[str] = Field(default_factory=list)
    requirement_ids: List[str] = Field(default_factory=list)
    kind: FindingKind = FindingKind.EXTENSION
    criterion: Optional[str] = None
    scored_gap: bool = Field(default=False, strict=True)


class RequirementCoverage(BaseModel):
    """Evidence-supported coverage of one published requirement."""

    requirement_id: str
    status: Literal["supported", "partial", "missing", "needs_clarification"]
    explanation: str = Field(min_length=1)
    evidence_ids: List[str] = Field(default_factory=list)


class IntegrityCheck(BaseModel):
    """An observable diagram check, never an architecture grade."""

    check: str
    status: Literal["passed", "failed"]
    explanation: str
    evidence_ids: List[str] = Field(default_factory=list)


class StructuralCheck(BaseModel):
    """Fallback walkthrough observations supplied by the semantic checker."""

    title: str = Field(min_length=1)
    status: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class ScoreBreakdown(BaseModel):
    """Model for detailed score breakdown."""

    scalability: int = Field(ge=0, le=100)
    reliability: int = Field(ge=0, le=100)
    security: int = Field(ge=0, le=100)
    maintainability: int = Field(ge=0, le=100)
    performance: Optional[int] = Field(default=None, ge=0, le=100)
    cost_efficiency: Optional[int] = Field(default=None, ge=0, le=100)
    observability: Optional[int] = Field(default=None, ge=0, le=100)
    deliverability: Optional[int] = Field(default=None, ge=0, le=100)
    requirements_alignment: Optional[int] = Field(default=None, ge=0, le=100)
    constraint_compliance: Optional[int] = Field(default=None, ge=0, le=100)
    component_justification: Optional[int] = Field(default=None, ge=0, le=100)
    connection_clarity: Optional[int] = Field(default=None, ge=0, le=100)


class AssessmentResponse(BaseModel):
    """Model for system design assessment response."""

    is_valid: bool
    overall_score: int = Field(ge=0, le=100)
    score_available: bool = True
    verdict: AssessmentVerdict = AssessmentVerdict.MORE_CONTEXT_NEEDED
    rubric_version: str = "2.0"
    requirement_revision: Optional[str] = None
    problem_id: Optional[str] = None
    requirement_coverage: List[RequirementCoverage] = Field(default_factory=list)
    integrity_checks: List[IntegrityCheck] = Field(default_factory=list)
    structural_checks: List[StructuralCheck] = Field(default_factory=list)
    model_version: Optional[str] = None
    scores: ScoreBreakdown
    feedback: List[ValidationFeedback]
    summary: Optional[str] = None
    findings: List[ReviewFinding] = Field(
        default_factory=lambda: cast(List[ReviewFinding], [])
    )
    strengths: List[str]
    improvements: List[str]
    missing_components: List[str]
    missing_descriptions: Optional[List[str]] = None
    unclear_connections: Optional[List[str]] = None
    suggestions: List[str]
    detailed_analysis: Optional[Dict[str, str]] = None
    interview_questions: Optional[List[str]] = None
    assessment_id: Optional[str] = None
    trace_id: Optional[str] = None
    processing_time_ms: Optional[int] = None
    source: AssessmentSource = AssessmentSource.AI
