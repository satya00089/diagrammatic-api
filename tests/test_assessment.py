import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.request_models import AssessmentRequest, SystemComponent, ComponentType
from app.services.ai_assessor import AIAssessorService

client = TestClient(app)


def test_health_endpoint():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_assessment_health_endpoint():
    """Test the assessment health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "assessment"}


def test_assess_system_design_valid_request():
    """Test system design assessment with valid request"""
    test_request = {
        "components": [
            {"id": "frontend-1", "type": "frontend", "label": "React Frontend"},
            {"id": "backend-1", "type": "backend", "label": "Node.js API"},
            {"id": "database-1", "type": "database", "label": "PostgreSQL"},
        ],
        "connections": [
            {
                "id": "conn-1",
                "source": "frontend-1",
                "target": "backend-1",
                "label": "API calls",
            },
            {
                "id": "conn-2",
                "source": "backend-1",
                "target": "database-1",
                "label": "Database queries",
            },
        ],
        "explanation": "Simple web application architecture",
        "requirements": "Handle 1000 concurrent users",
    }

    response = client.post("/api/v1/assess", json=test_request)
    assert response.status_code == 200

    data = response.json()
    assert "is_valid" in data
    assert "overall_score" in data
    assert "scores" in data
    assert "feedback" in data
    assert "assessment_id" in data
    assert "summary" in data
    assert isinstance(data["findings"], list)
    assert data["source"] in {"ai", "rule_based"}


def test_assess_system_design_empty_components():
    """Test system design assessment with empty components"""
    test_request = {"components": [], "explanation": "No components provided"}

    response = client.post("/api/v1/assess", json=test_request)
    assert response.status_code == 400
    assert "At least one component is required" in response.json()["detail"]


def test_assess_system_design_minimal_request():
    """Test system design assessment with minimal valid request"""
    test_request = {
        "components": [{"id": "app-1", "type": "backend", "label": "Simple API"}]
    }

    response = client.post("/api/v1/assess", json=test_request)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data["is_valid"], bool)
    assert 0 <= data["overall_score"] <= 100
    assert "scalability" in data["scores"]
    assert "reliability" in data["scores"]
    assert "security" in data["scores"]
    assert "maintainability" in data["scores"]


def test_ai_response_is_transformed_into_structured_findings():
    """Structured findings are validated and the weighted score remains server-owned."""
    service = object.__new__(AIAssessorService)
    result = service._transform_ai_response(
        {
            "summary": "The request path is clear, but the database is a bottleneck.",
            "scores": {
                "scalability": 80,
                "reliability": 70,
                "security": 60,
                "maintainability": 90,
                "performance": 70,
                "cost_efficiency": 60,
                "observability": 50,
                "deliverability": 80,
                "requirements_alignment": 80,
                "constraint_compliance": 80,
                "component_justification": 90,
                "connection_clarity": 90,
            },
            "findings": [
                {
                    "title": "Database is a likely bottleneck",
                    "explanation": "All writes converge on one database instance.",
                    "recommendation": "Explain the replication and partitioning strategy.",
                    "severity": "important",
                },
                {
                    "title": "Clear request flow",
                    "explanation": "The API path is explicit and easy to trace.",
                    "recommendation": None,
                    "severity": "positive",
                },
            ],
            "feedback": [],
            "strengths": ["Clear request flow"],
            "improvements": [],
            "missing_components": [],
            "suggestions": [],
        }
    )

    assert result.source == "ai"
    assert result.summary == "The request path is clear, but the database is a bottleneck."
    assert len(result.findings) == 2
    assert result.findings[0].severity == "important"
    assert result.findings[1].severity == "positive"
    assert result.overall_score == 74


def test_fallback_assessment_identifies_that_it_is_not_an_ai_review():
    """Fallback output is explicit so users do not mistake a basic check for AI feedback."""
    service = object.__new__(AIAssessorService)
    request = AssessmentRequest(
        components=[
            SystemComponent(
                id="api-1",
                type=ComponentType.BACKEND,
                label="API",
            )
        ]
    )

    result = service._fallback_assessment(request, "provider unavailable")

    assert result.source == "rule_based"
    assert result.findings[0].severity == "important"
    assert "basic structural check" in (result.summary or "")
