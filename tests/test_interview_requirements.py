"""Interview and assessment share approved scope; these tests never use AWS/LLMs."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.models.reasoning_models import InterviewQuestionsResponse, InterviewResponse
from app.models.request_models import InterviewQuestionsRequest, InterviewRequest
from app.routers import interview
from app.routers.assessment import get_problem_lookup
from app.utils.prompts import get_interview_prompt, get_interview_questions_prompt


def architecture():
    return {
        "components": [{"id": "api", "type": "backend", "label": "API"}],
        "problem": {"id": "catalog-id", "title": "Links", "description": "Short links",
                    "requirements": "Client-supplied old scope"},
    }


def approved_record():
    return {"title": "Approved links", "requirements": ["Create links"],
            "constraints": ["No external paid service"], "requirementSpec": {
                "schemaVersion": 1, "revision": "r2",
                "functional": [{"id": "create", "text": "Create links", "scope": "core"},
                               {"id": "qr", "text": "Export QR codes", "scope": "extension"}],
                "nonFunctional": [{"id": "latency", "text": "Keep redirect p99 below 50 ms", "scope": "core", "category": "latency"}],
                "assumptions": ["One region is the worked-example scenario"],
            }}


def client_for(monkeypatch, lookup):
    calls = []

    async def questions(request):
        calls.append(request.architecture)
        return InterviewQuestionsResponse(questions=["How does the cache meet the provided latency target?"])

    async def critique(request):
        calls.append(request.architecture)
        return InterviewResponse(critique="Explain cache misses under this target.")

    monkeypatch.setattr(interview, "AIAssessorService", lambda: SimpleNamespace(
        generate_interview_questions=questions, critique_interview_answer=critique,
    ))
    app = FastAPI()
    app.include_router(interview.router)
    app.dependency_overrides[get_problem_lookup] = lambda: lookup
    return TestClient(app), calls


@pytest.mark.parametrize("path", ["/interview/questions", "/interview/respond"])
def test_both_interview_routes_resolve_approved_scope(monkeypatch, path):
    client, calls = client_for(monkeypatch, lambda _: approved_record())
    payload = {"architecture": architecture(), "question": "Why Redis?", "answer": "To reduce redirect latency"}
    with client:
        response = client.post(path, json=payload)
    assert response.status_code == 200
    assert calls[0].problem.title == "Approved links"
    assert calls[0].problem.requirementSpec.revision == "r2"
    assert calls[0].problem.constraints == "No external paid service"


@pytest.mark.parametrize("path", ["/interview/questions", "/interview/respond"])
def test_old_revision_is_visible_as_conflict_not_regraded(monkeypatch, path):
    client, calls = client_for(monkeypatch, lambda _: approved_record())
    old = architecture()
    old["problem"]["requirementRevision"] = "r1"
    with client:
        response = client.post(path, json={"architecture": old, "question": "Why Redis?", "answer": "Low latency"})
    assert response.status_code == 409
    assert response.json()["detail"]["current_revision"] == "r2"
    assert calls == []


def test_catalog_failure_does_not_generate_questions_from_unapproved_context(monkeypatch):
    def unavailable(_):
        raise RuntimeError("Catalog offline")
    client, calls = client_for(monkeypatch, unavailable)
    with client:
        response = client.post("/interview/questions", json={"architecture": architecture()})
    assert response.status_code == 503
    assert calls == []


def test_interview_prompts_include_true_constraints_core_optional_scope_and_assumptions():
    source = architecture()
    source["problem"]["requirementSpec"] = approved_record()["requirementSpec"]
    source["problem"]["constraints"] = "No external paid service"
    requests = [InterviewQuestionsRequest(architecture=source),
                InterviewRequest(architecture=source, question="Why a cache?", answer="Latency")]
    for request, render in zip(requests, (get_interview_questions_prompt, get_interview_prompt)):
        prompt = render(request)
        assert "p99 below 50 ms" in prompt
        assert "No external paid service" in prompt
        assert "scope=extension" in prompt
        assert "REFERENCE ASSUMPTIONS" in prompt
        assert "extensions are not mandatory" in prompt
