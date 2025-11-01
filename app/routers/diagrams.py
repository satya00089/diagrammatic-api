"""Diagrams router for CRUD operations on diagrams."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.diagram_models import DiagramCreate, DiagramUpdate, DiagramResponse
from app.services.dynamodb_service import dynamodb_service
from app.routers.auth import get_current_user

router = APIRouter()

# Constants
DIAGRAM_NOT_FOUND = "Diagram not found"


@router.post("/diagrams", response_model=DiagramResponse, status_code=status.HTTP_201_CREATED)
async def create_diagram(
    request: DiagramCreate, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Save a new diagram (requires authentication)."""
    diagram = dynamodb_service.create_diagram(
        user_id=current_user["user_id"],
        title=request.title,
        description=request.description,
        nodes=request.nodes,
        edges=request.edges,
    )

    return DiagramResponse(
        id=diagram.id,
        userId=diagram.userId,
        title=diagram.title,
        description=diagram.description,
        nodes=diagram.nodes,
        edges=diagram.edges,
        createdAt=diagram.createdAt,
        updatedAt=diagram.updatedAt,
    )


@router.get("/diagrams", response_model=List[DiagramResponse])
async def get_diagrams(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all diagrams for the authenticated user."""
    diagrams = dynamodb_service.get_diagrams_by_user(current_user["user_id"])

    return [
        DiagramResponse(
            id=diagram.id,
            userId=diagram.userId,
            title=diagram.title,
            description=diagram.description,
            nodes=diagram.nodes,
            edges=diagram.edges,
            createdAt=diagram.createdAt,
            updatedAt=diagram.updatedAt,
        )
        for diagram in diagrams
    ]


@router.get("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def get_diagram(diagram_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get a specific diagram (requires authentication and ownership)."""
    diagram = dynamodb_service.get_diagram(current_user["user_id"], diagram_id)

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=DIAGRAM_NOT_FOUND
        )

    return DiagramResponse(
        id=diagram.id,
        userId=diagram.userId,
        title=diagram.title,
        description=diagram.description,
        nodes=diagram.nodes,
        edges=diagram.edges,
        createdAt=diagram.createdAt,
        updatedAt=diagram.updatedAt,
    )


@router.put("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def update_diagram(
    diagram_id: str,
    request: DiagramUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update an existing diagram (requires authentication and ownership)."""
    # Check if diagram exists and belongs to user
    existing = dynamodb_service.get_diagram(current_user["user_id"], diagram_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=DIAGRAM_NOT_FOUND
        )

    # Update diagram
    diagram = dynamodb_service.update_diagram(
        user_id=current_user["user_id"],
        diagram_id=diagram_id,
        title=request.title,
        description=request.description,
        nodes=request.nodes,
        edges=request.edges,
    )

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update diagram",
        )

    return DiagramResponse(
        id=diagram.id,
        userId=diagram.userId,
        title=diagram.title,
        description=diagram.description,
        nodes=diagram.nodes,
        edges=diagram.edges,
        createdAt=diagram.createdAt,
        updatedAt=diagram.updatedAt,
    )


@router.delete("/diagrams/{diagram_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diagram(
    diagram_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a diagram (requires authentication and ownership)."""
    # Check if diagram exists and belongs to user
    existing = dynamodb_service.get_diagram(current_user["user_id"], diagram_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=DIAGRAM_NOT_FOUND
        )

    # Delete diagram
    success = dynamodb_service.delete_diagram(
        current_user["user_id"], diagram_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete diagram",
        )

    return None
