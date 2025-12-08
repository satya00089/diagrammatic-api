"""
Tests for AI-powered recommendation system.

Tests cover:
1. Request validation
2. Recommendation filtering (high precision)
3. Fallback behavior
4. API endpoint
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.recommendation_models import (
    RecommendationRequest,
    CanvasContextInfo,
    UserIntentInfo,
    ComponentInfo,
    ConnectionInfo,
)
from app.services.ai_recommendation_service import (
    AIRecommendationService,
    ConfidenceBasedFilter,
    ContextAwareEnricher,
)


client = TestClient(app)


class TestRecommendationModels:
    """Test Pydantic model validation."""

    def test_canvas_context_validation(self):
        """Test canvas context model validation."""
        # Valid context
        context = CanvasContextInfo(
            node_count=5,
            edge_count=3,
            component_types=["database", "server"],
            is_empty=False,
        )
        assert context.node_count == 5
        assert context.edge_count == 3
        assert not context.is_empty

    def test_canvas_context_negative_validation(self):
        """Test that negative counts raise validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            CanvasContextInfo(
                node_count=-1, edge_count=0, component_types=[], is_empty=True
            )

    def test_recommendation_request_validation(self):
        """Test recommendation request validation."""
        request = RecommendationRequest(
            user_intent=UserIntentInfo(
                title="E-commerce Platform",
                description="Build an online shopping system",
            ),
            canvas_context=CanvasContextInfo(
                node_count=0, edge_count=0, component_types=[], is_empty=True
            ),
            components=[],
            connections=[],
            max_suggestions=5,
        )
        assert request.max_suggestions == 5
        assert request.user_intent.title == "E-commerce Platform"

    def test_max_suggestions_validation(self):
        """Test max_suggestions bounds."""
        with pytest.raises(Exception):  # Should fail for values > 10
            RecommendationRequest(
                canvas_context=CanvasContextInfo(
                    node_count=0, edge_count=0, component_types=[], is_empty=True
                ),
                max_suggestions=15,  # Too high
            )


class TestConfidenceBasedFilter:
    """Test high-precision confidence filtering."""

    def test_filter_by_confidence_threshold(self):
        """Test that low-confidence recommendations are filtered out."""
        filter_service = ConfidenceBasedFilter()

        recommendations = [
            {"id": "1", "title": "High Confidence", "confidence": 0.9, "priority": 8},
            {
                "id": "2",
                "title": "Medium Confidence",
                "confidence": 0.65,
                "priority": 7,
            },
            {"id": "3", "title": "Low Confidence", "confidence": 0.4, "priority": 9},
            {"id": "4", "title": "Borderline", "confidence": 0.6, "priority": 6},
        ]

        filtered = filter_service.filter(recommendations, threshold=0.6)

        # Should keep only items with confidence >= 0.6
        assert len(filtered) == 3
        assert all(rec["confidence"] >= 0.6 for rec in filtered)
        assert filtered[0]["confidence"] == 0.9  # Highest confidence first

    def test_deduplication(self):
        """Test that duplicate titles are removed."""
        filter_service = ConfidenceBasedFilter()

        recommendations = [
            {"id": "1", "title": "Add Database", "confidence": 0.8, "priority": 8},
            {
                "id": "2",
                "title": "add database",
                "confidence": 0.7,
                "priority": 7,
            },  # Duplicate (case-insensitive)
            {"id": "3", "title": "Add Cache", "confidence": 0.75, "priority": 6},
        ]

        filtered = filter_service.filter(recommendations, threshold=0.6)

        # Should keep only unique titles
        assert len(filtered) == 2
        titles = [rec["title"].lower() for rec in filtered]
        assert len(set(titles)) == len(titles)  # All unique

    def test_sorting_by_confidence_and_priority(self):
        """Test that recommendations are sorted correctly."""
        filter_service = ConfidenceBasedFilter()

        recommendations = [
            {"id": "1", "title": "Low Priority", "confidence": 0.8, "priority": 5},
            {"id": "2", "title": "High Confidence", "confidence": 0.9, "priority": 8},
            {"id": "3", "title": "Medium", "confidence": 0.85, "priority": 7},
        ]

        filtered = filter_service.filter(recommendations, threshold=0.6)

        # Should be sorted by confidence first, then priority
        assert filtered[0]["confidence"] == 0.9
        assert filtered[0]["priority"] == 8


class TestContextAwareEnricher:
    """Test recommendation enrichment."""

    def test_adds_default_values(self):
        """Test that enricher adds default values for missing fields."""
        enricher = ContextAwareEnricher()

        recommendations = [
            {
                "title": "Test Recommendation",
                "description": "Test description",
            }
        ]

        request = RecommendationRequest(
            canvas_context=CanvasContextInfo(
                node_count=0, edge_count=0, component_types=[], is_empty=True
            )
        )

        enriched = enricher.enrich(recommendations, request)

        assert "id" in enriched[0]
        assert "icon" in enriched[0]
        assert enriched[0]["icon"] == "💡"  # Default icon
        assert enriched[0]["category"] == "tip"  # Default category


class TestRecommendationAPIEndpoint:
    """Test the FastAPI endpoint."""

    def test_recommendations_endpoint_success(self):
        """Test successful recommendation request."""
        payload = {
            "user_intent": {
                "title": "Social Media Platform",
                "description": "Build a scalable social network",
            },
            "canvas_context": {
                "node_count": 0,
                "edge_count": 0,
                "component_types": [],
                "is_empty": True,
            },
            "components": [],
            "connections": [],
            "max_suggestions": 5,
        }

        response = client.post("/api/v1/recommendations", json=payload)

        # Should return 200 even if AI fails (fallback)
        assert response.status_code == 200

        data = response.json()
        assert "recommendations" in data
        assert "total_count" in data
        assert "filtered_count" in data
        assert "min_confidence_threshold" in data
        assert isinstance(data["recommendations"], list)

    def test_recommendations_endpoint_validation_error(self):
        """Test that invalid requests return 422."""
        payload = {
            "canvas_context": {
                "node_count": -5,  # Invalid: negative
                "edge_count": 0,
                "component_types": [],
                "is_empty": True,
            },
            "max_suggestions": 5,
        }

        response = client.post("/api/v1/recommendations", json=payload)

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_health_check_endpoint(self):
        """Test recommendations health check."""
        response = client.get("/api/v1/recommendations/health")

        assert response.status_code in [200, 503]  # Healthy or unavailable
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert data["service"] == "recommendations"


class TestHighPrecisionRequirements:
    """Test that high precision requirements are met."""

    def test_minimum_confidence_threshold_enforced(self):
        """Test that system enforces minimum 0.6 confidence."""
        filter_service = ConfidenceBasedFilter()

        recommendations = [
            {"id": "1", "title": "Low Quality", "confidence": 0.3, "priority": 10},
            {"id": "2", "title": "Medium Quality", "confidence": 0.5, "priority": 9},
            {"id": "3", "title": "High Quality", "confidence": 0.7, "priority": 8},
        ]

        filtered = filter_service.filter(recommendations, threshold=0.6)

        # Only high-quality recommendation should pass
        assert len(filtered) == 1
        assert filtered[0]["confidence"] >= 0.6

    def test_quality_over_quantity(self):
        """Test that system prefers fewer high-quality suggestions."""
        filter_service = ConfidenceBasedFilter()

        # 10 recommendations, but only 2 are high quality
        recommendations = [
            {
                "id": str(i),
                "title": f"Rec {i}",
                "confidence": 0.9 if i < 2 else 0.4,
                "priority": i,
            }
            for i in range(10)
        ]

        filtered = filter_service.filter(recommendations, threshold=0.6)

        # Should return only the 2 high-quality ones
        assert len(filtered) == 2
        assert all(rec["confidence"] >= 0.6 for rec in filtered)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
