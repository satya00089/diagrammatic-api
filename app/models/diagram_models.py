"""Diagram related Pydantic models."""

from typing import Optional, List, Any
from pydantic import BaseModel, Field


class DiagramCreate(BaseModel):
    """Request model for creating a new diagram."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    nodes: List[Any] = Field(default_factory=list)
    edges: List[Any] = Field(default_factory=list)


class DiagramUpdate(BaseModel):
    """Request model for updating a diagram."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    nodes: Optional[List[Any]] = None
    edges: Optional[List[Any]] = None


class DiagramResponse(BaseModel):
    """Response model for diagram data."""

    id: str
    userId: str
    title: str
    description: Optional[str] = None
    nodes: List[Any]
    edges: List[Any]
    createdAt: str
    updatedAt: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class Diagram(BaseModel):
    """Internal diagram model."""

    id: str
    userId: str
    title: str
    description: Optional[str] = None
    nodes: List[Any]
    edges: List[Any]
    createdAt: str
    updatedAt: str
