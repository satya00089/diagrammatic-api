"""Models for public problem data from DynamoDB."""

from datetime import datetime
import re
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator


def problem_slug(title: str) -> str:
    """Return a clean, deterministic fallback slug for legacy problem records."""
    normalized = (
        title.lower()
        .replace("&", " and ")
        .replace("\u2019", "")
        .replace("'", "")
    )
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


class RequirementItem(BaseModel):
    """One approved capability or quality target, with explicit exercise scope."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    scope: Literal["core", "extension"]
    category: str | None = None


class RequirementSpec(BaseModel):
    """Versioned requirements shared by catalog records and declared contexts."""

    model_config = ConfigDict(str_strip_whitespace=True)

    schemaVersion: Literal[1] = 1
    revision: str = Field(min_length=1)
    functional: list[RequirementItem] = Field(default_factory=list)
    nonFunctional: list[RequirementItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_requirement_ids(self) -> "RequirementSpec":
        ids = [item.id for item in self.functional + self.nonFunctional]
        if len(ids) != len(set(ids)):
            raise ValueError("Requirement IDs must be unique across the specification")
        return self


class ProblemModel(BaseModel):
    """Fields and normalization shared by public problem responses."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    slug: str = ""
    title: str
    description: str
    difficulty: str
    category: str
    domain: str | None = None
    estimatedTime: str = Field(alias="estimated_time")
    requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    requirementSpec: RequirementSpec | None = None
    hints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def populate_slug(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        problem_data = cast(dict[str, object], data)
        if problem_data.get("slug"):
            return problem_data

        title = problem_data.get("title")
        if not isinstance(title, str):
            return problem_data

        normalized_data = dict(problem_data)
        normalized_data["slug"] = problem_slug(title)
        return normalized_data


class ProblemSummary(ProblemModel):
    """Model for problem summary (used in /all-problems endpoint)."""

    has_guided_walkthrough: bool = False


class ProblemPage(BaseModel):
    """Cursor-paginated problem summaries for the public catalog."""

    items: list[ProblemSummary]
    next_cursor: str | None = None
    has_more: bool = False
    total_count: int | None = None


class ProblemDetail(ProblemModel):
    """Model for detailed problem data (used in /problem/{id} endpoint)."""

    created_at: datetime | None = None
    updated_at: datetime | None = None
