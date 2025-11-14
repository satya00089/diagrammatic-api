"""
Confidence-based filtering strategy for recommendations.

Single responsibility: Filter recommendations based on confidence scores.
Ensures high precision by applying strict thresholds.
"""

from typing import List, Dict, Any

from app.services.recommendation_interfaces import IRecommendationFilter


class ConfidenceBasedFilter(IRecommendationFilter):
    """
    Filters recommendations based on confidence scores for HIGH PRECISION.

    Responsibilities:
    - Apply confidence threshold filtering
    - Remove duplicate suggestions
    - Ensure quality over quantity
    """

    def filter(
        self, recommendations: List[Dict[str, Any]], threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Filter recommendations to ensure high precision.

        Args:
            recommendations: Raw recommendations from AI
            threshold: Minimum confidence score (default 0.6 for precision)

        Returns:
            Filtered list of high-quality recommendations
        """
        # Filter by confidence threshold (HIGH PRECISION)
        filtered = [
            rec for rec in recommendations if rec.get("confidence", 0.0) >= threshold
        ]

        # Remove duplicates by title (case-insensitive)
        seen_titles = set()
        unique = []
        for rec in filtered:
            title_lower = rec.get("title", "").lower()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique.append(rec)

        # Sort by confidence (high to low) then priority (high to low)
        unique.sort(
            key=lambda x: (x.get("confidence", 0), x.get("priority", 0)), reverse=True
        )

        return unique
