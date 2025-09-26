"""Utility functions to generate prompts for system design assessment."""
from app.models.request_models import AssessmentRequest


def get_assessment_prompt(request: AssessmentRequest) -> str:
    """Generate the assessment prompt for the given request."""
    components_text = "\n".join(
        [
            f'- {comp.type.value}: "{comp.label}"'
            + (f" (Properties: {comp.properties})" if comp.properties else "")
            for comp in request.components
        ]
    )

    connections_text = (
        "\n".join(
            [
                f"- {conn.source} → {conn.target}"
                + (f" ({conn.label})" if conn.label else "")
                for conn in (request.connections or [])
            ]
        )
        or "No explicit connections defined"
    )

    # Build problem context section
    problem_context = ""
    if request.problem:
        problem_context = f"""
**PROBLEM CONTEXT:**
- Title: {request.problem.title}
- Description: {request.problem.description}
- Difficulty: {request.problem.difficulty or 'Not specified'}
- Category: {request.problem.category or 'Not specified'}
- Estimated Time: {request.problem.estimatedTime or 'Not specified'}
"""

    return f"""
You are assessing a system design solution. Please evaluate the architecture comprehensively.
{problem_context}
**COMPONENTS:**
{components_text}

**CONNECTIONS:**
{connections_text}

**USER EXPLANATION:**
{request.explanation or 'No explanation provided'}

**KEY POINTS:**
{chr(10).join(f'- {point}' for point in (request.keyPoints or [])) or 'No key points provided'}

**REQUIREMENTS:**
{request.problem.requirements if request.problem and request.problem.requirements else request.requirements or 'No specific requirements provided'}

**CONSTRAINTS:**
{request.problem.constraints if request.problem and request.problem.constraints else request.constraints or 'No constraints specified'}

**ASSESSMENT CRITERIA:**
Rate each aspect from 0-100, considering the problem context and requirements:

1. **Scalability**: Can this handle growth in users, data, and traffic as required by the problem?
2. **Reliability**: Will this remain available during failures and meet the reliability requirements?
3. **Security**: Are proper security measures implemented for this type of system?
4. **Maintainability**: Is this manageable, well-documented, and appropriate for the problem complexity?
5. **Requirements Alignment**: How well does this solution address the specific problem requirements?
6. **Constraint Compliance**: Does this solution respect the given constraints (budget, time, technology, etc.)?

**RESPONSE FORMAT:**
Respond with a valid JSON object in this exact structure:

{{
  "scores": {{
    "scalability": 75,
    "reliability": 80,
    "security": 65,
    "maintainability": 70,
    "requirements_alignment": 85,
    "constraint_compliance": 90
  }},
  "feedback": [
    {{
      "type": "success|warning|error|info",
      "message": "Specific feedback message",
      "category": "scalability|reliability|security|maintainability|performance|cost|requirements|constraints",
      "priority": 1
    }}
  ],
  "strengths": [
    "List of architectural strengths and good patterns"
  ],
  "improvements": [
    "Specific actionable improvements with clear steps"
  ],
  "missing_components": [
    "Components that should be added to improve the design"
  ],
  "suggestions": [
    "Additional recommendations and best practices"
  ]
}}

Focus on practical, actionable feedback that helps improve the system design.
"""


def get_specialized_prompt(domain: str, request: AssessmentRequest) -> str:
    """Generate domain-specific prompts for specialized assessments"""
    base_prompt = get_assessment_prompt(request)

    domain_contexts = {
        "microservices": "Focus on service boundaries, data consistency, and inter-service communication patterns.",
        "data_intensive": "Emphasize data modeling, storage solutions, and data flow patterns.",
        "real_time": "Prioritize latency, throughput, and real-time processing capabilities.",
        "security_critical": "Deep dive into security controls, authentication, authorization, and compliance.",
    }

    if domain in domain_contexts:
        return base_prompt + f"\n\n**DOMAIN FOCUS:**\n{domain_contexts[domain]}"

    return base_prompt
