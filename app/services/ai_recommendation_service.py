"""
AI-powered recommendation service following SOLID principles.

Implementation:
- AIRecommendationService: Orchestrates AI recommendations
- Filter and enricher components injected via dependency injection
- Graceful fallback to rule-based recommendations on errors
- High precision filtering with configurable confidence thresholds
"""

import json
import time
from typing import Optional

from openai import AsyncOpenAI

from app.models.recommendation_models import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationItem,
)
from app.utils.recommendation_prompts import (
    build_recommendation_prompt,
    get_system_message,
    get_fallback_recommendations,
)
from app.utils.config import get_settings
from app.services.recommendation_interfaces import (
    IRecommendationFilter,
    IRecommendationEnricher,
)
from app.services.confidence_based_filter import ConfidenceBasedFilter
from app.services.context_aware_enricher import ContextAwareEnricher


class AIRecommendationService:
    """
    Main service for AI-powered recommendations.

    Responsibilities:
    - Orchestrate AI API calls
    - Coordinate filtering and enrichment
    - Handle errors with graceful fallbacks
    - Track performance metrics
    """

    def __init__(
        self,
        recommendation_filter: Optional[IRecommendationFilter] = None,
        recommendation_enricher: Optional[IRecommendationEnricher] = None,
    ):
        """
        Initialize service with dependency injection.

        Args:
            recommendation_filter: Strategy for filtering recommendations
            recommendation_enricher: Strategy for enriching recommendations
        """
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        # Depend on abstractions, inject dependencies
        self.filter = recommendation_filter or ConfidenceBasedFilter()
        self.enricher = recommendation_enricher or ContextAwareEnricher()

        # High precision threshold (configurable)
        self.min_confidence_threshold = 0.6

    async def get_recommendations(
        self, request: RecommendationRequest
    ) -> RecommendationResponse:
        """
        Get AI-powered recommendations with high precision filtering.

        Args:
            request: Recommendation request with full context

        Returns:
            Response with filtered, high-quality recommendations
        """
        start_time = time.time()

        try:
            # Build intelligent prompt
            prompt = build_recommendation_prompt(request)

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": get_system_message()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,  # Lower temperature for more consistent, precise output
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            # Parse AI response
            ai_result = json.loads(response.choices[0].message.content)
            raw_recommendations = ai_result.get("recommendations", [])
            total_count = len(raw_recommendations)

            # Use injected filter for high precision
            filtered_recommendations = self.filter.filter(
                raw_recommendations, self.min_confidence_threshold
            )

            # Use injected enricher for context enhancement
            enriched_recommendations = self.enricher.enrich(
                filtered_recommendations, request
            )

            # Limit to max_suggestions
            final_recommendations = enriched_recommendations[: request.max_suggestions]

            # Build response with metadata
            processing_time = int((time.time() - start_time) * 1000)

            return RecommendationResponse(
                recommendations=[
                    RecommendationItem(**rec) for rec in final_recommendations
                ],
                total_count=total_count,
                filtered_count=len(final_recommendations),
                min_confidence_threshold=self.min_confidence_threshold,
                context_summary=ai_result.get(
                    "context_summary", self._generate_context_summary(request)
                ),
                processing_time_ms=processing_time,
            )

        except Exception as e:
            # Graceful fallback to rule-based recommendations
            return self.get_fallback_recommendations(request, str(e))

    def _generate_context_summary(self, request: RecommendationRequest) -> str:
        """Generate a brief summary of the request context."""
        if request.user_intent:
            return f"{request.canvas_context.node_count} components for {request.user_intent.title}"
        elif request.canvas_context.is_empty:
            return "Empty canvas - starting fresh"
        else:
            return f"{request.canvas_context.node_count} components, {request.canvas_context.edge_count} connections"

    def get_fallback_recommendations(
        self, request: RecommendationRequest, error: str
    ) -> RecommendationResponse:
        """
        Provide fallback recommendations when AI is unavailable.

        Args:
            request: Original request
            error: Error message from AI service

        Returns:
            Response with conservative fallback recommendations
        """
        fallback = get_fallback_recommendations()

        # Add error context to first recommendation if any
        recommendations = fallback.get("recommendations", [])
        if recommendations:
            recommendations[0]["reasoning"] = f"AI service error: {error[:100]}"

        return RecommendationResponse(
            recommendations=[RecommendationItem(**rec) for rec in recommendations],
            total_count=len(recommendations),
            filtered_count=len(recommendations),
            min_confidence_threshold=0.6,
            context_summary=self._generate_context_summary(request),
            processing_time_ms=0,
        )


# Factory function for easy instantiation
def create_recommendation_service() -> AIRecommendationService:
    """
    Factory function to create a configured recommendation service.

    Returns abstraction, hides concrete implementation.
    Easy to extend with different configurations.
    """
    return AIRecommendationService(
        recommendation_filter=ConfidenceBasedFilter(),
        recommendation_enricher=ContextAwareEnricher(),
    )
