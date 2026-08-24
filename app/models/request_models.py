"""Models for request payloads and responses for system design assessment."""

from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field

from app.models.reasoning_models import InterviewSession, ReasoningContext


class ComponentType(str, Enum):
    """Enumeration of component types."""

    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    CACHE = "cache"
    LOAD_BALANCER = "load-balancer"
    API_GATEWAY = "api-gateway"
    MESSAGE_BROKER = "message-broker"
    QUEUE = "queue"
    CDN = "cdn"
    MONITORING = "monitoring"
    ANALYTICS = "analytics"
    EXTERNAL_API = "external-api"
    STORAGE = "storage"
    SECURITY = "security"
    CUSTOM = "custom"


class SystemComponent(BaseModel):
    """Model representing a system component."""

    id: str
    type: ComponentType
    label: str
    icon: Optional[str] = None
    subtitle: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, float]] = None


class Connection(BaseModel):
    """Model representing a connection between system components."""

    id: str
    source: str
    target: str
    label: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None


class ProblemContext(BaseModel):
    """Model representing the system design problem context."""

    title: str
    description: str
    requirements: Optional[str] = None
    constraints: Optional[str] = None
    difficulty: Optional[str] = None
    category: Optional[str] = None
    estimatedTime: Optional[str] = None


class AssessmentRequest(BaseModel):
    """ "Model for system design assessment request."""

    components: List[SystemComponent]
    connections: Optional[List[Connection]] = []
    explanation: Optional[str] = None
    keyPoints: Optional[List[str]] = []
    requirements: Optional[str] = None
    constraints: Optional[str] = None
    problem: Optional[ProblemContext] = None
    reasoningContext: Optional[ReasoningContext] = None
    interviewSession: Optional[InterviewSession] = None


class InterviewQuestionsRequest(BaseModel):
    """Request for architecture-specific questions before assessment."""

    architecture: AssessmentRequest


class InterviewRequest(BaseModel):
    """Request for critique of an answer to an architecture interview question."""

    architecture: AssessmentRequest
    question: str = Field(..., min_length=1, max_length=4000)
    answer: str = Field(..., min_length=1, max_length=8000)
    previousCritique: Optional[str] = Field(None, max_length=8000)
