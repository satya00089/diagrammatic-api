"""API router for guided walkthrough endpoints."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.models.walkthrough_models import GuidedWalkthrough
from app.services.dynamodb_service import dynamodb_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/problem/{problem_id}/walkthrough",
    response_model=GuidedWalkthrough,
    summary="Get guided walkthrough for a problem",
)
async def get_walkthrough(problem_id: str) -> GuidedWalkthrough:
    """
    Get the step-by-step guided walkthrough for a specific problem.

    Args:
        problem_id: The unique identifier of the problem (e.g. 'ai_001')

    Returns:
        Full guided walkthrough with phases, steps, components, connections,
        decision points, and scale triggers.

    Raises:
        404: If no walkthrough exists for the given problem_id.
    """
    try:
        data = dynamodb_service.get_walkthrough_by_problem_id(problem_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No guided walkthrough found for problem '{problem_id}'",
            )
        return GuidedWalkthrough(**data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching walkthrough for problem '%s': %s", problem_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch guided walkthrough",
        ) from e
