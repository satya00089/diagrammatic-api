"""API router for problem-related endpoints."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from app.models.problem_models import ProblemSummary, ProblemDetail
from app.services.problem_service import get_problem_service, ProblemService


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/all-problems", response_model=List[ProblemSummary])
async def get_all_problems(
    problem_service: ProblemService = Depends(get_problem_service),
) -> List[ProblemSummary]:
    """
    Get all problems with summary information.

    Returns:
        List of problems with id, title, description, difficulty, category,
        estimatedTime, tags, and companies.
    """
    try:
        problems = await problem_service.get_all_problems()
        return problems
    except Exception as e:
        logger.error("Error in get_all_problems: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch problems from database",
        ) from e


@router.get("/problem/{problem_id}", response_model=ProblemDetail)
async def get_problem_by_id(
    problem_id: str, problem_service: ProblemService = Depends(get_problem_service)
) -> ProblemDetail:
    """
    Get a specific problem by ID with full details.

    Args:
        problem_id: The unique identifier of the problem

    Returns:
        Complete problem details including requirements, constraints, and hints.
    """
    try:
        problem = await problem_service.get_problem_by_id(problem_id)

        if not problem:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problem with ID '{problem_id}' not found",
            )

        return problem
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in get_problem_by_id: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch problem from database",
        ) from e


@router.get("/problems/health")
async def problems_health_check(
    problem_service: ProblemService = Depends(get_problem_service),
):
    """Health check for problems service and database connection."""
    try:
        is_healthy = await problem_service.health_check()

        if is_healthy:
            return {"status": "healthy", "service": "problems", "database": "connected"}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection is not healthy",
            )
    except Exception as e:
        logger.error("Error in problems health check: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Problems service is unavailable",
        ) from e
