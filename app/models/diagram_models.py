"""Diagram related Pydantic models."""

from typing import Optional, List, Any
from pydantic import BaseModel, Field
from enum import Enum


class Permission(str, Enum):
    """Permission levels for diagram sharing."""
    
    READ = "read"
    EDIT = "edit"


class Collaborator(BaseModel):
    """Model for diagram collaborators."""
    
    userId: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    permission: Permission
    addedAt: str


class ShareRequest(BaseModel):
    """Request model for sharing a diagram."""
    
    email: str = Field(..., description="Email of the user to share with")
    permission: Permission = Field(..., description="Permission level to grant")


class ShareResponse(BaseModel):
    """Response model for sharing operations."""
    
    success: bool
    message: str
    collaborator: Optional[Collaborator] = None


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
    isPublic: bool = Field(default=False, description="Whether the diagram is publicly accessible")
    collaborators: List[Collaborator] = Field(default_factory=list, description="List of collaborators with access")

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
    isPublic: bool = Field(default=False)
    collaborators: List[Collaborator] = Field(default_factory=list)
