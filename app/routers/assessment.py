import uuid

from fastapi import APIRouter, HTTPException, Depends
from app.models.request_models import AssessmentRequest
from app.models.response_models import AssessmentResponse
from app.services.ai_assessor import AIAssessorService

router = APIRouter()


def get_assessor_service() -> AIAssessorService:
    """Dependency injection for AIAssessorService."""
    return AIAssessorService()


@router.post("/assess", response_model=AssessmentResponse)
async def assess_system_design(
    request: AssessmentRequest,
    assessor: AIAssessorService = Depends(get_assessor_service),
) -> AssessmentResponse:
    """
    Assess a system design solution using AI-powered analysis.

    Returns detailed feedback on scalability, reliability, security, and maintainability.
    """
    try:
        # Validate input
        if not request.components:
            raise HTTPException(
                status_code=400,
                detail="At least one component is required for assessment",
            )

        # Generate assessment ID
        assessment_id = str(uuid.uuid4())

        # Perform AI assessment
        result = await assessor.assess_design(request)
        result.assessment_id = assessment_id

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}") from e


@router.get("/health")
async def assessment_health():
    """Health check endpoint for the assessment router."""
    return {"status": "healthy", "service": "assessment"}
