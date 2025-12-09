"""
FastAPI router for AI-powered recommendations.

Provides REST API endpoints for getting context-aware design recommendations.
Includes proper error handling, validation, and rate limiting.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from app.models.recommendation_models import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.routers.auth import get_current_user
from app.services.ai_recommendation_service import create_recommendation_service


router = APIRouter()


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI-powered design recommendations",
    description="""
    Get context-aware recommendations for improving system design diagrams.
    
    **Requirements:**
    - Minimum 5 nodes on the canvas
    - User must be authenticated
    - Use `force_refresh=true` to trigger LLM analysis (increases API costs)
    
    **Behavior:**
    - By default returns rule-based recommendations (no LLM costs)
    - Set `force_refresh=true` to get AI-powered analysis from LLM
    - LLM calls are rate-limited and should be used sparingly
    
    This endpoint uses AI to analyze the current canvas state, user intent,
    and design patterns to provide highly relevant, actionable suggestions.
    
    **Features:**
    - High precision filtering (confidence threshold >= 0.6)
    - Context-aware suggestions based on user intent
    - Pattern detection and best practice recommendations
    - Graceful fallback to rule-based suggestions if AI fails
    
    **Rate Limiting:**
    Subject to API rate limits to ensure fair usage.
    """,
    responses={
        200: {
            "description": "Successfully generated recommendations",
            "content": {
                "application/json": {
                    "example": {
                        "recommendations": [
                            {
                                "id": "rec-1",
                                "title": "Add Load Balancer",
                                "description": "Distribute traffic across your API servers",
                                "icon": "⚖️",
                                "category": "component",
                                "priority": 9,
                                "confidence": 0.85,
                                "action_type": "add-component",
                                "component_id": "loadbalancer",
                                "reasoning": "Multiple API servers detected without load balancing",
                            }
                        ],
                        "total_count": 8,
                        "filtered_count": 1,
                        "min_confidence_threshold": 0.6,
                        "context_summary": "5 components for E-commerce Platform",
                        "processing_time_ms": 1250,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Validation error: max_suggestions must be between 1 and 10"
                    }
                }
            },
        },
        422: {"description": "Validation error in request body"},
        500: {
            "description": "Internal server error (will attempt fallback recommendations)"
        },
    },
    tags=["Recommendations"],
)
async def get_recommendations(
    request: RecommendationRequest,
    current_user: dict = Depends(get_current_user)
) -> RecommendationResponse:
    """
    Get AI-powered recommendations for system design improvement.

    Args:
        request: RecommendationRequest with user intent, canvas state, and components

    Returns:
        RecommendationResponse with filtered, high-quality recommendations

    Raises:
        HTTPException: If validation fails or service is unavailable
    """
    try:
        # Validate request (Pydantic handles this automatically)
        # Additional business logic validation
        if request.canvas_context.node_count < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid canvas state: node_count cannot be negative",
            )

        # Minimum 5 nodes requirement for recommendations
        if request.canvas_context.node_count < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum 5 nodes required for recommendations. Add more components to your diagram.",
            )

        # Create service instance (can be singleton in production)
        service = create_recommendation_service()

        # Get recommendations - only authenticated users can get AI-powered recommendations
        response = await service.get_recommendations(request)

        return response

    except ValueError as ve:
        # Validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(ve)}",
        ) from ve
    except Exception as e:
        # Unexpected errors - log and return fallback
        # In production, this would log to monitoring service
        print(f"Error in recommendations endpoint: {str(e)}")

        # Try to return fallback recommendations instead of hard failure
        try:
            service = create_recommendation_service()
            fallback_response = service.get_fallback_recommendations(
                request, f"Service error: {str(e)[:100]}"
            )
            return fallback_response
        except Exception as exc:
            # If even fallback fails, return error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Recommendation service temporarily unavailable",
            ) from exc


@router.get(
    "/recommendations/health",
    status_code=status.HTTP_200_OK,
    summary="Health check for recommendations service",
    tags=["Recommendations"],
)
async def recommendations_health_check():
    """
    Health check endpoint for recommendation service.

    Returns:
        Status of the recommendations service
    """
    try:
        # Simple health check - ensure we can create service
        service = create_recommendation_service()
        return {
            "status": "healthy",
            "service": "recommendations",
            "min_confidence_threshold": service.min_confidence_threshold,
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "recommendations",
                "error": str(e)[:200],
            },
        )
