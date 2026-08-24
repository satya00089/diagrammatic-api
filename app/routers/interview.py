"""Router for interactive system-design interview practice."""

from fastapi import APIRouter, HTTPException, status

from app.models.reasoning_models import InterviewQuestionsResponse, InterviewResponse
from app.models.request_models import InterviewQuestionsRequest, InterviewRequest
from app.services.ai_assessor import AIAssessorService


router = APIRouter()


@router.post(
    "/interview/questions",
    status_code=status.HTTP_200_OK,
)
async def generate_interview_questions(
    request: InterviewQuestionsRequest,
) -> InterviewQuestionsResponse:
    """Generate architecture-specific questions before assessment begins."""
    try:
        return await AIAssessorService().generate_interview_questions(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Interview questions are temporarily unavailable. Please try again.",
        ) from exc


@router.post(
    "/interview/respond",
    status_code=status.HTTP_200_OK,
)
async def respond_to_interview(
    request: InterviewRequest,
) -> InterviewResponse:
    """Evaluate one answer without replacing the candidate's architecture."""
    try:
        return await AIAssessorService().critique_interview_answer(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Interview review is temporarily unavailable. Please try again.",
        ) from exc
