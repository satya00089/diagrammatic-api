"""
Prompt engineering for AI-powered recommendations.

Following SOLID principles:
- Single Responsibility: Each function builds specific prompt sections
- Open/Closed: Easy to extend with new prompt strategies
- Dependency Inversion: Abstract prompt building from concrete AI service
"""

from typing import List
from app.models.recommendation_models import (
    RecommendationRequest,
    ComponentInfo,
    ConnectionInfo,
)


def build_recommendation_prompt(request: RecommendationRequest) -> str:
    """
    Build a comprehensive prompt for AI recommendation generation.
    
    Focus on HIGH PRECISION by:
    1. Providing clear, detailed context
    2. Specifying strict relevance criteria
    3. Requesting confidence scores
    4. Emphasizing quality over quantity
    
    Args:
        request: The recommendation request with full context
        
    Returns:
        A well-structured prompt for the AI model
    """
    sections = [
        _build_system_role_section(),
        _build_user_intent_section(request),
        _build_canvas_state_section(request),
        _build_component_details_section(request),
        _build_connection_details_section(request),
        _build_output_format_section(request),
        _build_precision_guidelines_section(),
    ]
    
    return "\n\n".join(filter(None, sections))


def _build_system_role_section() -> str:
    """Define the AI's role and expectations for high precision."""
    return """You are an expert system design architect and UX assistant. Your role is to provide HIGHLY RELEVANT, ACTIONABLE recommendations for improving system architecture diagrams.

CRITICAL REQUIREMENTS FOR HIGH PRECISION:
1. Only suggest components/patterns that are CLEARLY relevant to the user's stated intent
2. Avoid generic suggestions - be specific and contextual
3. Each recommendation must have a clear, justified reason
4. Confidence score should reflect genuine relevance (be conservative)
5. Prioritize quality over quantity - fewer, better suggestions are preferred
6. Consider what's already on the canvas to avoid redundant suggestions"""


def _build_user_intent_section(request: RecommendationRequest) -> str:
    """Build section describing user's stated intent."""
    if not request.user_intent:
        return """USER INTENT: Not explicitly stated (blank canvas or free design mode)
⚠️ Without clear intent, be EXTRA conservative - only suggest foundational/universal components."""
    
    intent = request.user_intent
    return f"""USER INTENT:
Title: "{intent.title}"
Description: "{intent.description or 'Not provided'}"

⚠️ All recommendations MUST align with this stated intent. Irrelevant suggestions will reduce user trust."""


def _build_canvas_state_section(request: RecommendationRequest) -> str:
    """Build section describing current canvas state."""
    ctx = request.canvas_context
    
    if ctx.is_empty:
        return """CANVAS STATE: Empty (0 components, 0 connections)
💡 User is just starting - suggest foundational components that align with their intent."""
    
    # Calculate design maturity indicators
    avg_connections_per_node = ctx.edge_count / max(ctx.node_count, 1)
    
    maturity_level = "early stage"
    if ctx.node_count > 10:
        maturity_level = "advanced"
    elif ctx.node_count > 5:
        maturity_level = "intermediate"
    
    return f"""CANVAS STATE: {maturity_level.title()} Design
- Components: {ctx.node_count}
- Connections: {ctx.edge_count}
- Avg Connections per Component: {avg_connections_per_node:.1f}
- Component Types Present: {', '.join(ctx.component_types) if ctx.component_types else 'None'}

💡 Design is in {maturity_level} phase - tailor recommendations accordingly."""


def _build_component_details_section(request: RecommendationRequest) -> str:
    """Build section with detailed component information for pattern detection."""
    if not request.components:
        return ""
    
    # Group components by type for analysis
    components_by_type = {}
    undocumented_components = []
    
    for comp in request.components:
        comp_type = comp.type
        components_by_type[comp_type] = components_by_type.get(comp_type, 0) + 1
        
        if not comp.has_description:
            undocumented_components.append(comp.label)
    
    # Build detailed summary
    details = ["DETAILED COMPONENT ANALYSIS:"]
    details.append("Component Type Distribution:")
    for comp_type, count in sorted(components_by_type.items(), key=lambda x: -x[1]):
        details.append(f"  - {comp_type}: {count}")
    
    if undocumented_components:
        details.append(f"\n⚠️ Components Missing Descriptions: {', '.join(undocumented_components[:5])}")
        if len(undocumented_components) > 5:
            details.append(f"   ...and {len(undocumented_components) - 5} more")
    
    return "\n".join(details)


def _build_connection_details_section(request: RecommendationRequest) -> str:
    """Build section analyzing connections for architectural patterns."""
    if not request.connections:
        return "CONNECTIONS: None defined yet\n⚠️ If design has multiple components, suggest connecting them with clear labels."
    
    unlabeled_count = sum(1 for conn in request.connections if not conn.has_label)
    
    details = [f"CONNECTIONS: {len(request.connections)} total"]
    
    if unlabeled_count > 0:
        details.append(f"⚠️ {unlabeled_count} connections lack descriptive labels")
    
    return "\n".join(details)


def _build_output_format_section(request: RecommendationRequest) -> str:
    """Specify the exact JSON output format required."""
    return f"""OUTPUT FORMAT:
You MUST respond with valid JSON in this EXACT format:

{{
  "recommendations": [
    {{
      "id": "unique-id-1",
      "title": "Short, clear title (max 100 chars)",
      "description": "Specific, actionable description (max 500 chars)",
      "icon": "📦",
      "category": "component|pattern|tip|best-practice|optimization",
      "priority": 1-10,
      "confidence": 0.0-1.0,
      "action_type": "add-component|add-pattern|info-only|connect|refactor",
      "component_id": "component-id (optional, for add-component)",
      "component_ids": ["id1", "id2"] (optional, for add-pattern),
      "reasoning": "Why this is relevant (max 300 chars, helps transparency)"
    }}
  ],
  "context_summary": "Brief summary of the analysis (max 200 chars)"
}}

GUIDELINES:
- Return maximum {request.max_suggestions} recommendations
- Order by priority (highest first)
- Only include recommendations with confidence >= 0.6 (HIGH PRECISION requirement)
- Each recommendation must have clear reasoning
- Be specific with component_id when suggesting components"""


def _build_precision_guidelines_section() -> str:
    """Additional guidelines to ensure high precision."""
    return """PRECISION GUIDELINES (CRITICAL):

✅ GOOD RECOMMENDATIONS:
- Directly address a gap in the current design
- Align perfectly with user's stated intent
- Have clear, specific reasoning
- Reference actual components on canvas
- Provide actionable next steps

❌ AVOID:
- Generic suggestions that apply to any design
- Recommending components already present
- Vague tips without specific context
- Suggestions unrelated to user intent
- Low-confidence hunches (confidence < 0.6)

CONFIDENCE SCORING:
- 0.9-1.0: Perfect match to intent, clear gap identified
- 0.7-0.9: Strong relevance, good architectural fit
- 0.6-0.7: Moderate relevance, could be useful
- < 0.6: DO NOT INCLUDE (too uncertain)

Remember: It's better to return 2-3 highly relevant suggestions than 10 mediocre ones!"""


def get_system_message() -> str:
    """Get the system message for the AI chat completion."""
    return """You are an expert system design architect specializing in creating clear, well-documented architecture diagrams. 

You provide precise, contextual recommendations that help users build better system designs. You prioritize quality over quantity and always justify your suggestions with clear reasoning.

Your recommendations should be:
1. Highly relevant to the user's specific intent and current design
2. Actionable with clear next steps
3. Justified with transparent reasoning
4. Conservative in confidence scoring (precision over recall)
5. Specific to the actual context, not generic advice"""


def get_fallback_recommendations() -> dict:
    """
    Get fallback recommendations when AI is unavailable.
    
    These are conservative, high-precision suggestions for common scenarios.
    """
    return {
        "recommendations": [
            {
                "id": "fallback-start",
                "title": "Start with Core Components",
                "description": "Add the foundational components for your system design",
                "icon": "🏗️",
                "category": "tip",
                "priority": 8,
                "confidence": 0.7,
                "action_type": "info-only",
                "reasoning": "Empty canvas - suggesting foundational start"
            },
            {
                "id": "fallback-document",
                "title": "Document Your Components",
                "description": "Add descriptions to your components for better clarity",
                "icon": "📝",
                "category": "best-practice",
                "priority": 7,
                "confidence": 0.8,
                "action_type": "info-only",
                "reasoning": "Good documentation improves design communication"
            }
        ],
        "context_summary": "AI service unavailable - showing fallback suggestions"
    }
