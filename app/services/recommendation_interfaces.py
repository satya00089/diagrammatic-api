"""
Abstract interfaces for recommendation service components.

Focused, minimal interfaces for each component:
- IRecommendationFilter: Filters recommendations based on precision criteria
- IRecommendationEnricher: Enriches recommendations with metadata
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from app.models.recommendation_models import RecommendationRequest


class IRecommendationFilter(ABC):
    """Interface for filtering recommendations based on precision criteria."""

    @abstractmethod
    def filter(
        self, recommendations: List[Dict[str, Any]], threshold: float
    ) -> List[Dict[str, Any]]:
        """Filter recommendations based on confidence threshold."""


class IRecommendationEnricher(ABC):
    """Interface for enriching recommendations with additional metadata."""

    @abstractmethod
    def enrich(
        self, recommendations: List[Dict[str, Any]], context: RecommendationRequest
    ) -> List[Dict[str, Any]]:
        """Enrich recommendations with context-aware metadata."""
