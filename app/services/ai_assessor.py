"""Service for assessing system design diagrams using AI and rule-based methods."""

from typing import Dict, Any
import json
import re
import time

from openai import AsyncOpenAI

from app.models.request_models import AssessmentRequest
from app.models.response_models import (
    AssessmentResponse,
    ScoreBreakdown,
    ValidationFeedback,
)
from app.utils.prompts import get_assessment_prompt
from app.utils.config import get_settings


class AIAssessorService:
    """Service to assess system design diagrams using AI and rule-based methods."""

    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    # ------------------------------------------------------------------
    # Coverage helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_meaningful_description(text: str | None) -> bool:
        """Return True if text has at least 10 real characters after stripping HTML."""
        if not text:
            return False
        stripped = re.sub(r"<[^>]+>", "", text).strip()
        return len(stripped) >= 10

    def _compute_coverage(self, request: AssessmentRequest) -> Dict[str, Any]:
        """Compute description coverage for components and connections."""
        total_comps = len(request.components)
        comps_with_desc = sum(
            1 for c in request.components
            if self._has_meaningful_description(
                (c.properties or {}).get("description", "")
            )
        )
        total_conns = len(request.connections or [])
        conns_with_desc = sum(
            1 for conn in (request.connections or [])
            if self._has_meaningful_description(conn.description)
        )
        return {
            "comp_pct": (comps_with_desc / total_comps * 100) if total_comps else 100,
            "conn_pct": (conns_with_desc / total_conns * 100) if total_conns else 100,
            "comp_ok": (comps_with_desc / total_comps >= 0.70) if total_comps else True,
            "conn_ok": (conns_with_desc / total_conns >= 0.70) if total_conns else True,
        }

    # ------------------------------------------------------------------
    # Main assessment entry-point
    # ------------------------------------------------------------------

    async def assess_design(self, request: AssessmentRequest) -> AssessmentResponse:
        """Assess the system design using AI and fallback to rule-based if needed."""
        start_time = time.time()

        # Pre-compute coverage so we can post-filter AI feedback
        coverage = self._compute_coverage(request)

        try:
            # Generate structured prompt
            prompt = get_assessment_prompt(request)

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior system architect and technical lead with 15+ years of experience "
                            "in distributed systems, microservices, and cloud architecture. "
                            "You provide tough but fair assessments. "
                            "When the design meets the 70% description-coverage threshold stated in the prompt, "
                            "do not penalise missing descriptions — focus on architecture quality instead."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )

            # Parse AI response
            ai_result = json.loads(response.choices[0].message.content)

            # Transform to response model
            assessment = self._transform_ai_response(ai_result)

            # Post-process: suppress description feedback when coverage threshold is met
            assessment = self._filter_description_feedback(assessment, coverage)

            # Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)
            assessment.processing_time_ms = processing_time

            return assessment

        except Exception as e:
            # Fallback to rule-based assessment
            return self._fallback_assessment(request, str(e))

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    _DESC_KEYWORDS = (
        "description", "no description", "missing description", "undefined purpose",
        "unclear purpose", "purpose unclear", "lacks description", "lacks detail",
        "component purpose", "add descriptions", "provide descriptions",
        "component documentation", "component_justification",
    )
    _CONN_KEYWORDS = (
        "connection description", "connection label", "connection reasoning",
        "connection clarity", "unclear connection", "missing connection description",
        "add descriptions to connection", "connection lacks",
    )

    def _filter_description_feedback(
        self, assessment: AssessmentResponse, coverage: Dict[str, Any]
    ) -> AssessmentResponse:
        """Remove or demote description-related feedback when coverage ≥ 70%."""
        comp_ok: bool = coverage["comp_ok"]
        conn_ok: bool = coverage["conn_ok"]

        if not (comp_ok or conn_ok):
            return assessment  # nothing to suppress

        def _keep_feedback(fb: ValidationFeedback) -> bool:
            lower = fb.message.lower()
            if comp_ok:
                if fb.category in ("component_description",):
                    return False
                if any(kw in lower for kw in self._DESC_KEYWORDS):
                    return False
            if conn_ok:
                if fb.category in ("connection_reasoning",):
                    return False
                if any(kw in lower for kw in self._CONN_KEYWORDS):
                    return False
            return True

        def _keep_text(msg: str) -> bool:
            lower = msg.lower()
            if comp_ok and any(kw in lower for kw in self._DESC_KEYWORDS):
                return False
            if conn_ok and any(kw in lower for kw in self._CONN_KEYWORDS):
                return False
            return True

        assessment.feedback = [fb for fb in assessment.feedback if _keep_feedback(fb)]
        assessment.improvements = [i for i in assessment.improvements if _keep_text(i)]
        if comp_ok:
            assessment.missing_descriptions = []
        if conn_ok:
            assessment.unclear_connections = []
        return assessment

    # Scoring weights by dimension importance.
    # Architecture-critical dims carry more weight than documentation dims.
    _SCORE_WEIGHTS: Dict[str, float] = {
        "scalability": 2.0,
        "reliability": 2.0,
        "security": 2.0,
        "maintainability": 2.0,
        "performance": 1.5,
        "observability": 1.5,
        "deliverability": 1.5,
        "cost_efficiency": 1.0,
        "requirements_alignment": 1.0,
        "constraint_compliance": 1.0,
        "component_justification": 0.75,
        "connection_clarity": 0.75,
    }

    def _transform_ai_response(self, ai_result: Dict[str, Any]) -> AssessmentResponse:
        # Transform AI JSON response to Pydantic model
        scores = ScoreBreakdown(**ai_result.get("scores", {}))

        feedback = [ValidationFeedback(**fb) for fb in ai_result.get("feedback", [])]

        # Weighted average: architecture-critical dims outweigh documentation dims
        weighted_sum = 0.0
        total_weight = 0.0
        for field, weight in self._SCORE_WEIGHTS.items():
            val = getattr(scores, field, None)
            if val is not None:
                weighted_sum += val * weight
                total_weight += weight

        overall_score = round(weighted_sum / total_weight) if total_weight else 0
        overall_score = max(0, min(100, overall_score))

        return AssessmentResponse(
            is_valid=overall_score >= 50,
            overall_score=overall_score,
            scores=scores,
            feedback=feedback,
            strengths=ai_result.get("strengths", []),
            improvements=ai_result.get("improvements", []),
            missing_components=ai_result.get("missing_components", []),
            missing_descriptions=ai_result.get("missing_descriptions", []),
            unclear_connections=ai_result.get("unclear_connections", []),
            suggestions=ai_result.get("suggestions", []),
            detailed_analysis=ai_result.get("detailed_analysis"),
            interview_questions=ai_result.get("interview_questions", []),
        )

    def _fallback_assessment(
        self, request: AssessmentRequest, error: str
    ) -> AssessmentResponse:
        # Simple rule-based fallback when AI fails
        component_count = len(request.components)
        has_database = any(c.type == "database" for c in request.components)
        has_load_balancer = any(c.type == "load-balancer" for c in request.components)

        # Check for component descriptions
        components_with_descriptions = sum(
            1
            for c in request.components
            if c.properties and c.properties.get("description", "").strip()
        )
        description_score = min(components_with_descriptions * 20, 80)

        base_score = min(component_count * 15, 60)
        if has_database:
            base_score += 10
        if has_load_balancer:
            base_score += 15

        # Create list of components missing descriptions (strip HTML before checking)
        missing_descriptions = [
            c.label
            for c in request.components
            if not self._has_meaningful_description(
                (c.properties or {}).get("description", "")
            )
        ]

        return AssessmentResponse(
            is_valid=base_score >= 50,
            overall_score=base_score,
            scores=ScoreBreakdown(
                scalability=base_score,
                reliability=base_score,
                security=max(base_score - 20, 20),
                maintainability=base_score,
                component_justification=description_score,
                connection_clarity=50 if request.connections else 20,
            ),
            feedback=[
                ValidationFeedback(
                    type="warning",
                    message=f"AI assessment failed: {error}. Using fallback assessment.",
                    category="maintainability",
                )
            ],
            strengths=["Basic architecture components present"],
            improvements=[
                "Add detailed component documentation and connection reasoning"
            ],
            missing_components=[],
            missing_descriptions=missing_descriptions,
            unclear_connections=(
                [] if request.connections else ["No connections defined"]
            ),
            suggestions=[
                "Consider adding monitoring and caching layers",
                "Provide detailed component descriptions",
            ],
        )
