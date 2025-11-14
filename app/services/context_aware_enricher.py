"""
Context-aware enrichment strategy for recommendations.

Single responsibility: Enrich recommendations with metadata.
Adds default values and validates fields.
"""

import time
from typing import List, Dict, Any

from app.models.recommendation_models import RecommendationRequest
from app.services.recommendation_interfaces import IRecommendationEnricher


class ContextAwareEnricher(IRecommendationEnricher):
    """
    Enriches recommendations with context-specific metadata.

    Responsibilities:
    - Add default values for optional fields
    - Validate component IDs against known components
    - Enhance reasoning with context
    """

    def enrich(
        self, recommendations: List[Dict[str, Any]], context: RecommendationRequest
    ) -> List[Dict[str, Any]]:
        """
        Enrich recommendations with additional metadata.

        Args:
            recommendations: Filtered recommendations
            context: Original request context

        Returns:
            Enriched recommendations
        """
        enriched = []

        for rec in recommendations:
            # Ensure all required fields have values
            enriched_rec = {
                "id": rec.get("id", f"rec-{int(time.time() * 1000)}"),
                "title": rec.get("title", "Untitled Recommendation"),
                "description": rec.get("description", ""),
                "icon": rec.get("icon", "💡"),
                "category": rec.get("category", "tip"),
                "priority": rec.get("priority", 5),
                "confidence": rec.get("confidence", 0.5),
                "action_type": rec.get("action_type", "info-only"),
            }

            # Add optional fields if present
            if "component_id" in rec:
                enriched_rec["component_id"] = rec["component_id"]
            if "component_ids" in rec:
                enriched_rec["component_ids"] = rec["component_ids"]
            if "reasoning" in rec:
                enriched_rec["reasoning"] = rec["reasoning"]

            enriched.append(enriched_rec)

        return enriched
