"""Tests for public problem response models."""

from app.models.problem_models import (
    ProblemDetail,
    ProblemPage,
    ProblemSummary,
    problem_slug,
)


def problem_data() -> dict[str, object]:
    """Return the fields shared by summary and detail problem responses."""
    return {
        "id": "rate-limiter",
        "title": "Design a Rate Limiter",
        "description": "Protect an API from excessive traffic.",
        "difficulty": "medium",
        "category": "system-design",
        "estimated_time": "45 minutes",
    }


def test_problem_slug_normalizes_title_without_edge_separators() -> None:
    assert problem_slug("  John's Cache & Queue!  ") == "johns-cache-and-queue"


def test_problem_summary_populates_missing_slug_and_defaults() -> None:
    summary = ProblemSummary.model_validate(problem_data())

    assert summary.slug == "design-a-rate-limiter"
    assert summary.estimatedTime == "45 minutes"
    assert summary.requirements == []
    assert summary.has_guided_walkthrough is False


def test_problem_detail_preserves_existing_slug() -> None:
    data = problem_data()
    data["slug"] = "custom-slug"

    detail = ProblemDetail.model_validate(data)

    assert detail.slug == "custom-slug"
    assert detail.created_at is None
    assert detail.updated_at is None


def test_problem_page_exposes_authoritative_total_count() -> None:
    page = ProblemPage(items=[], total_count=145)

    assert page.total_count == 145
