"""Models for problem data from DynamoDB."""

from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class ProblemSummary(BaseModel):
    """Model for problem summary (used in /all-problems endpoint)."""

    id: str
    title: str
    description: str
    difficulty: str
    category: str
    domain: Optional[str] = None
    estimatedTime: str = Field(alias="estimated_time")
    tags: List[str] = []
    companies: List[str] = []

    class Config:
        """Pydantic configuration for ProblemSummary."""

        populate_by_name = True


class ProblemDetail(BaseModel):
    """Model for detailed problem data (used in /problem/{id} endpoint)."""

    id: str
    title: str
    description: str
    difficulty: str
    category: str
    estimatedTime: str = Field(alias="estimated_time")
    requirements: List[str] = []
    constraints: List[str] = []
    hints: List[str] = []
    tags: List[str] = []
    companies: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration for ProblemDetail."""

        populate_by_name = True
