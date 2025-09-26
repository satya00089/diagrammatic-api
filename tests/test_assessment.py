import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.request_models import AssessmentRequest, SystemComponent, ComponentType

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
            {
                "id": "frontend-1",
                "type": "frontend",
                "label": "React Frontend"
            },
            {
                "id": "backend-1",
                "type": "backend",
                "label": "Node.js API"
            },
            {
                "id": "database-1",
                "type": "database",
                "label": "PostgreSQL"
            }
        ],
        "connections": [
            {
                "id": "conn-1",
                "source": "frontend-1",
                "target": "backend-1",
                "label": "API calls"
            },
            {
                "id": "conn-2",
                "source": "backend-1",
                "target": "database-1",
                "label": "Database queries"
            }
        ],
        "explanation": "Simple web application architecture",
        "requirements": "Handle 1000 concurrent users"
    }
    
    response = client.post("/api/v1/assess", json=test_request)
    assert response.status_code == 200
    
    data = response.json()
    assert "is_valid" in data
    assert "overall_score" in data
    assert "scores" in data
    assert "feedback" in data
    assert "assessment_id" in data

def test_assess_system_design_empty_components():
    """Test system design assessment with empty components"""
    test_request = {
        "components": [],
        "explanation": "No components provided"
    }
    
    response = client.post("/api/v1/assess", json=test_request)
    assert response.status_code == 400
    assert "At least one component is required" in response.json()["detail"]

def test_assess_system_design_minimal_request():
    """Test system design assessment with minimal valid request"""
    test_request = {
        "components": [
            {
                "id": "app-1",
                "type": "backend",
                "label": "Simple API"
            }
        ]
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
