"""Router for interactive system-design interview practice."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.reasoning_models import InterviewQuestionsResponse, InterviewResponse
from app.models.request_models import InterviewQuestionsRequest, InterviewRequest
from app.services.ai_assessor import AIAssessorService
from app.routers.assessment import ProblemLookup, get_problem_lookup, resolve_problem_context


router = APIRouter()


@router.post(
    "/interview/questions",
    status_code=status.HTTP_200_OK,
)
async def generate_interview_questions(
    request: InterviewQuestionsRequest,
    problem_lookup: Annotated[ProblemLookup, Depends(get_problem_lookup)],
) -> InterviewQuestionsResponse:
    """Generate architecture-specific questions before assessment begins."""
    try:
        architecture = await resolve_problem_context(request.architecture, problem_lookup)
        return await AIAssessorService().generate_interview_questions(request.model_copy(update={"architecture": architecture}))
    except HTTPException:
        raise
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
    problem_lookup: Annotated[ProblemLookup, Depends(get_problem_lookup)],
) -> InterviewResponse:
    """Evaluate one answer without replacing the candidate's architecture."""
    try:
        architecture = await resolve_problem_context(request.architecture, problem_lookup)
        return await AIAssessorService().critique_interview_answer(request.model_copy(update={"architecture": architecture}))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Interview review is temporarily unavailable. Please try again.",
        ) from exc
