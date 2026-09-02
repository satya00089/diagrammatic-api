import pytest
from pydantic import ValidationError

from app.models.feedback_models import FeedbackCategory, FeedbackCreate, FeedbackSource


def test_feedback_accepts_contextual_assessment_helpfulness() -> None:
    feedback = FeedbackCreate(
        source=FeedbackSource.ASSESSMENT,
        category=FeedbackCategory.ASSESSMENT,
        helpful=False,
        reasons=["too_generic"],
        context={"problemId": "problem-1", "assessmentId": "assessment-1"},
    )

    assert feedback.helpful is False
    assert feedback.context.problemId == "problem-1"


def test_feedback_requires_a_signal() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreate()


def test_feedback_bounds_rating_and_message() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreate(rating=6)

    with pytest.raises(ValidationError):
        FeedbackCreate(message="x" * 4001)
