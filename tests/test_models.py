import pytest
from pydantic import ValidationError
from app.models.request_models import AssessmentRequest, SystemComponent, ComponentType, Connection
from app.models.response_models import AssessmentResponse, ScoreBreakdown, ValidationFeedback, FeedbackType, FeedbackCategory

def test_system_component_model():
    """Test SystemComponent model validation"""
    component = SystemComponent(
        id="test-1",
        type=ComponentType.FRONTEND,
        label="Test Frontend",
        properties={"framework": "React"}
    )
    
    assert component.id == "test-1"
    assert component.type == ComponentType.FRONTEND
    assert component.label == "Test Frontend"
    assert component.properties["framework"] == "React"

def test_assessment_request_model():
    """Test AssessmentRequest model validation"""
    components = [
        SystemComponent(
            id="frontend-1",
            type=ComponentType.FRONTEND,
            label="React App"
        ),
        SystemComponent(
            id="backend-1",
            type=ComponentType.BACKEND,
            label="API Server"
        )
    ]
    
    connections = [
        Connection(
            id="conn-1",
            source="frontend-1",
            target="backend-1",
            label="HTTP requests"
        )
    ]
    
    request = AssessmentRequest(
        components=components,
        connections=connections,
        explanation="Test architecture",
        requirements="High performance"
    )
    
    assert len(request.components) == 2
    assert len(request.connections) == 1
    assert request.explanation == "Test architecture"
    assert request.requirements == "High performance"

def test_score_breakdown_model():
    """Test ScoreBreakdown model validation"""
    scores = ScoreBreakdown(
        scalability=85,
        reliability=90,
        security=75,
        maintainability=80,
        performance=88,
        cost_efficiency=70
    )
    
    assert scores.scalability == 85
    assert scores.reliability == 90
    assert scores.security == 75
    assert scores.maintainability == 80
    assert scores.performance == 88
    assert scores.cost_efficiency == 70

def test_score_breakdown_validation():
    """Test ScoreBreakdown model validation constraints"""
    # Test valid scores
    ScoreBreakdown(
        scalability=100,
        reliability=0,
        security=50,
        maintainability=25
    )
    
    # Test invalid scores
    with pytest.raises(ValidationError):
        ScoreBreakdown(
            scalability=101,  # Invalid: > 100
            reliability=90,
            security=75,
            maintainability=80
        )
    
    with pytest.raises(ValidationError):
        ScoreBreakdown(
            scalability=85,
            reliability=-1,  # Invalid: < 0
            security=75,
            maintainability=80
        )

def test_validation_feedback_model():
    """Test ValidationFeedback model validation"""
    feedback = ValidationFeedback(
        type=FeedbackType.WARNING,
        message="Consider adding load balancer",
        category=FeedbackCategory.SCALABILITY,
        priority=3
    )
    
    assert feedback.type == FeedbackType.WARNING
    assert feedback.message == "Consider adding load balancer"
    assert feedback.category == FeedbackCategory.SCALABILITY
    assert feedback.priority == 3

def test_assessment_response_model():
    """Test AssessmentResponse model validation"""
    scores = ScoreBreakdown(
        scalability=85,
        reliability=90,
        security=75,
        maintainability=80
    )
    
    feedback = [
        ValidationFeedback(
            type=FeedbackType.SUCCESS,
            message="Good architecture",
            category=FeedbackCategory.RELIABILITY
        )
    ]
    
    response = AssessmentResponse(
        is_valid=True,
        overall_score=82,
        scores=scores,
        feedback=feedback,
        strengths=["Well structured"],
        improvements=["Add monitoring"],
        missing_components=["Load balancer"],
        suggestions=["Consider caching"],
        assessment_id="test-123",
        processing_time_ms=1500
    )
    
    assert response.is_valid is True
    assert response.overall_score == 82
    assert len(response.feedback) == 1
    assert response.assessment_id == "test-123"
    assert response.processing_time_ms == 1500
