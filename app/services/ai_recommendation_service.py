"""
AI-powered recommendation service following SOLID principles.

Implementation:
- AIRecommendationService: Orchestrates AI recommendations
- Filter and enricher components injected via dependency injection
- Graceful fallback to rule-based recommendations on errors
- High precision filtering with configurable confidence thresholds
"""

import copy
import json
import time
from typing import Optional, TypeAlias, cast

from openai import AsyncOpenAI
from openai.types.chat.completion_create_params import CompletionCreateParamsNonStreaming

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


JsonObject: TypeAlias = dict[str, object]


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

    @staticmethod
    def _parse_json_response(content: str | None) -> JsonObject:
        """Parse a JSON-object model response, including fenced JSON output."""
        if not content or not content.strip():
            raise ValueError("The AI returned an empty response")

        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        parsed: object = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("The AI response must be a JSON object")
        raw_object = cast(dict[object, object], parsed)
        if not all(isinstance(key, str) for key in raw_object):
            raise ValueError("AI response object keys must be strings")
        return {cast(str, key): value for key, value in raw_object.items()}

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

            # GPT-5/o-series reasoning models reject sampling temperature.
            completion_options: CompletionCreateParamsNonStreaming = {
                "model": self.settings.openai_model,
                "messages": [
                    {"role": "system", "content": get_system_message()},
                    {"role": "user", "content": prompt},
                ],
                "max_completion_tokens": self.settings.openai_max_tokens,
                "response_format": {"type": "json_object"},
            }
            if not self.settings.openai_model.lower().startswith(("gpt-5", "o1", "o3", "o4")):
                completion_options["temperature"] = self.settings.openai_temperature

            response = await self.client.chat.completions.create(**completion_options)

            # Parse AI response
            ai_result = self._parse_json_response(response.choices[0].message.content)
            raw_recommendations = ai_result.get("recommendations", [])
            if not isinstance(raw_recommendations, list):
                raise ValueError("AI response field 'recommendations' must be a list")
            raw_items = cast(list[object], raw_recommendations)
            recommendation_dicts = [
                cast(dict[str, object], item)
                for item in raw_items
                if isinstance(item, dict) and all(isinstance(key, str) for key in item)
            ]
            total_count = len(raw_items)

            # Use injected filter for high precision
            filtered_recommendations = self.filter.filter(
                recommendation_dicts, self.min_confidence_threshold
            )

            # Use injected enricher for context enhancement
            enriched_recommendations = self.enricher.enrich(
                filtered_recommendations, request
            )

            # Limit to max_suggestions
            final_recommendations = enriched_recommendations[: request.max_suggestions]

            # Build response with metadata
            processing_time = int((time.time() - start_time) * 1000)
            context_summary = ai_result.get("context_summary")
            if not isinstance(context_summary, str):
                context_summary = self._generate_context_summary(request)

            return RecommendationResponse(
                recommendations=[
                    RecommendationItem(**rec) for rec in final_recommendations
                ],
                total_count=total_count,
                filtered_count=len(final_recommendations),
                min_confidence_threshold=self.min_confidence_threshold,
                context_summary=context_summary,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            # Graceful fallback to rule-based recommendations
            return self.get_fallback_recommendations(
                request,
                str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

    def _generate_context_summary(self, request: RecommendationRequest) -> str:
        """Generate a brief summary of the request context."""
        if request.user_intent:
            return f"{request.canvas_context.node_count} components for {request.user_intent.title}"
        elif request.canvas_context.is_empty:
            return "Empty canvas - starting fresh"
        else:
            return f"{request.canvas_context.node_count} components, {request.canvas_context.edge_count} connections"

    def get_fallback_recommendations(
        self,
        request: RecommendationRequest,
        error: str,
        processing_time_ms: int | None = None,
    ) -> RecommendationResponse:
        """
        Provide fallback recommendations when AI is unavailable.

        Args:
            request: Original request
            error: Error message from AI service

        Returns:
            Response with conservative fallback recommendations
        """
        # Prompt utilities return nested mutable data. Copy it so one failed
        # request cannot modify the fallback returned to later requests.
        fallback = copy.deepcopy(get_fallback_recommendations())

        # Add error context to first recommendation if any
        recommendations = fallback.get("recommendations", [])
        if recommendations:
            recommendations[0]["reasoning"] = (
                "AI recommendations are temporarily unavailable; "
                "showing conservative fallback guidance."
            )

        context_summary = fallback.get("context_summary")
        if not isinstance(context_summary, str):
            context_summary = self._generate_context_summary(request)

        return RecommendationResponse(
            recommendations=[RecommendationItem(**rec) for rec in recommendations],
            total_count=len(recommendations),
            filtered_count=len(recommendations),
            min_confidence_threshold=0.6,
            context_summary=context_summary,
            processing_time_ms=processing_time_ms,
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
