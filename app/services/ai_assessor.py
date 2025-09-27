"""Service for assessing system design diagrams using AI and rule-based methods."""

from typing import Dict, Any
import json
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

    async def assess_design(self, request: AssessmentRequest) -> AssessmentResponse:
        """Assess the system design using AI and fallback to rule-based if needed."""
        start_time = time.time()

        try:
            # Generate structured prompt
            prompt = get_assessment_prompt(request)

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict senior system architect and technical lead with 15+ years of experience in distributed systems, microservices, and cloud architecture. You have high standards and provide tough but fair assessments. Be critical of incomplete designs, missing descriptions, and poor architectural justification. Only award high scores (70+) when designs demonstrate clear understanding and proper documentation. Penalize missing component descriptions heavily.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            # Parse AI response
            ai_result = json.loads(response.choices[0].message.content)

            # Transform to response model
            assessment = self._transform_ai_response(ai_result)

            # Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)
            assessment.processing_time_ms = processing_time

            return assessment

        except Exception as e:
            # Fallback to rule-based assessment
            return self._fallback_assessment(request, str(e))

    def _transform_ai_response(self, ai_result: Dict[str, Any]) -> AssessmentResponse:
        # Transform AI JSON response to Pydantic model
        scores = ScoreBreakdown(**ai_result.get("scores", {}))

        feedback = [ValidationFeedback(**fb) for fb in ai_result.get("feedback", [])]

        # Calculate overall score including new criteria if available
        core_scores = [
            scores.scalability,
            scores.reliability,
            scores.security,
            scores.maintainability,
        ]

        # Add optional scores if they exist and weight them appropriately
        if scores.requirements_alignment is not None:
            core_scores.append(scores.requirements_alignment)
        if scores.constraint_compliance is not None:
            core_scores.append(scores.constraint_compliance)
        if scores.component_justification is not None:
            core_scores.append(scores.component_justification)
        if scores.connection_clarity is not None:
            core_scores.append(scores.connection_clarity)

        overall_score = sum(core_scores) // len(core_scores)

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
            1 for c in request.components 
            if c.properties and c.properties.get('description', '').strip()
        )
        description_score = min(components_with_descriptions * 20, 80)

        base_score = min(component_count * 15, 60)
        if has_database:
            base_score += 10
        if has_load_balancer:
            base_score += 15

        # Create list of components missing descriptions
        missing_descriptions = [
            c.label for c in request.components 
            if not (c.properties and c.properties.get('description', '').strip())
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
            improvements=["Add detailed component documentation and connection reasoning"],
            missing_components=[],
            missing_descriptions=missing_descriptions,
            unclear_connections=[] if request.connections else ["No connections defined"],
            suggestions=["Consider adding monitoring and caching layers", "Provide detailed component descriptions"],
        )
