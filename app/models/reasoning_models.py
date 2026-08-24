"""Shared models for design reasoning context and interview practice."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ReasoningContext(BaseModel):
    """System-generated assumptions and review signals for a design."""

    requirements: Optional[str] = Field(None, max_length=4000)
    scaleAssumptions: Optional[str] = Field(None, max_length=4000)
    expectedTraffic: Optional[str] = Field(None, max_length=4000)
    readWriteRatio: Optional[str] = Field(None, max_length=2000)
    latencyGoals: Optional[str] = Field(None, max_length=2000)
    availabilityTarget: Optional[str] = Field(None, max_length=2000)
    consistencyRequirements: Optional[str] = Field(None, max_length=4000)
    technologyChoices: Optional[str] = Field(None, max_length=4000)
    tradeoffs: Optional[str] = Field(None, max_length=4000)
    unresolvedRisks: Optional[str] = Field(None, max_length=4000)


class InterviewExchange(BaseModel):
    """A single user answer and the reviewer's critique."""

    id: str
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(default="", max_length=8000)
    critique: str = Field(default="", max_length=8000)
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    nextQuestion: Optional[str] = Field(None, max_length=4000)
    createdAt: str
    skipped: bool = False


class InterviewSession(BaseModel):
    """Persisted progress through interview follow-up questions."""

    exchanges: List[InterviewExchange] = Field(default_factory=list)
    currentQuestionIndex: int = Field(default=0, ge=0)


class InterviewResponse(BaseModel):
    """Structured critique of a candidate's interview answer."""

    critique: str = Field(min_length=1, max_length=8000)
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    nextQuestion: Optional[str] = Field(None, max_length=4000)


class InterviewQuestionsResponse(BaseModel):
    """Architecture-specific questions shown before an assessment."""

    questions: List[str] = Field(default_factory=list, max_length=8)
