"""API router for problem-related endpoints."""

import logging
from typing import Any, List, Optional, Dict, Union

from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.models.problem_models import ProblemSummary, ProblemDetail
from app.services.dynamodb_service import dynamodb_service
from app.routers.auth import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/all-problems", response_model=List[ProblemSummary])
async def get_all_problems(
    category: Optional[str] = Query(None, description="Filter by category"),
    difficulty: Optional[str] = Query(
        None, description="Filter by difficulty (easy/medium/hard/very hard)"
    ),
) -> List[ProblemSummary]:
    """
    Get all problems with summary information, sorted from easy to very hard.

    Query Parameters:
        category: Optional filter by category (e.g., 'graphs', 'trees', 'arrays')
        difficulty: Optional filter by difficulty ('easy', 'medium', 'hard', 'very hard')

    Returns:
        List of problems with id, title, description, difficulty, category,
        estimatedTime, tags, and companies. Sorted by difficulty: easy -> medium -> hard -> very hard.
    """
    try:
        # Filter by category if provided
        if category:
            problems = dynamodb_service.get_problems_by_category(category)
        # Filter by difficulty if provided
        elif difficulty:
            problems = dynamodb_service.get_problems_by_difficulty(difficulty)
        # Get all problems if no filters
        else:
            problems = dynamodb_service.get_all_problems()

        # Convert DynamoDB items to ProblemSummary models
        problem_list = [ProblemSummary(**problem) for problem in problems]

        # Sort by difficulty: easy -> medium -> hard -> very hard
        difficulty_order = {"easy": 1, "medium": 2, "hard": 3, "very hard": 4}
        problem_list.sort(key=lambda p: difficulty_order.get(p.difficulty.lower(), 5))

        return problem_list
    except Exception as e:
        logger.error("Error in get_all_problems: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch problems from database",
        ) from e


@router.get("/problem/{problem_id}", response_model=ProblemDetail)
async def get_problem_by_id(problem_id: str) -> ProblemDetail:
    """
    Get a specific problem by ID with full details.

    Args:
        problem_id: The unique identifier of the problem

    Returns:
        Complete problem details including requirements, constraints, and hints.
    """
    try:
        problem = dynamodb_service.get_problem_by_id(problem_id)

        if not problem:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problem with ID '{problem_id}' not found",
            )

        return ProblemDetail(**problem)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in get_problem_by_id: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch problem from database",
        ) from e


@router.get("/problems/attempted", response_model=List[str])
async def get_attempted_problems(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[str]:
    """
    Get list of problem IDs that the user has attempted.

    Returns:
        List of problem IDs (strings) that the user has attempted.
    """
    try:
        user_id = current_user["user_id"]
        attempts = dynamodb_service.get_user_attempts(user_id)
        
        # Extract just the problem IDs
        problem_ids = [attempt.problemId for attempt in attempts]
        
        return problem_ids
    except Exception as e:
        logger.error("Error in get_attempted_problems: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch attempted problems",
        ) from e


@router.get("/problems/health")
async def problems_health_check() -> Dict[str, Union[str, int]]:
    """Health check for problems service and database connection."""
    try:
        # Try to query a single item to check if DynamoDB is accessible
        problems = dynamodb_service.get_all_problems()

        return {
            "status": "healthy",
            "service": "problems",
            "database": "dynamodb",
            "connection": "connected",
            "problem_count": len(problems) if problems else 0,
        }
    except Exception as e:
        logger.error("Error in problems health check: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Problems service is unavailable",
        ) from e
