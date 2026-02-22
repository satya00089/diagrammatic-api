"""Utility functions to generate prompts for system design assessment."""

import re

from app.models.request_models import AssessmentRequest

# Properties that are purely frontend/layout state and should not be sent to the AI
_INTERNAL_PROPS = frozenset({"x", "y", "width", "height", "selected", "dragging", "zIndex", "parentId", "expandParent"})


def _has_meaningful_description(text: str | None) -> bool:
    """Return True if text contains substantive content beyond empty HTML tags."""
    if not text:
        return False
    stripped = re.sub(r"<[^>]+>", "", text).strip()
    return len(stripped) >= 10


def get_assessment_prompt(request: AssessmentRequest) -> str:
    """Generate the assessment prompt for the given request."""

    # --- Coverage analysis (done before building the prompt text) ---
    total_components = len(request.components)
    components_with_desc = sum(
        1 for c in request.components
        if _has_meaningful_description(
            (c.properties or {}).get("description", "")
        )
    )
    total_connections = len(request.connections) if request.connections else 0
    connections_with_desc = sum(
        1 for conn in (request.connections or [])
        if _has_meaningful_description(conn.description)
    )

    comp_coverage = (components_with_desc / total_components * 100) if total_components else 0
    conn_coverage = (connections_with_desc / total_connections * 100) if total_connections else 0
    desc_threshold_met = comp_coverage >= 70
    conn_threshold_met = conn_coverage >= 70 or total_connections == 0

    # Coverage note injected into the prompt so the AI reasons from the same numbers
    coverage_note = (
        f"Coverage analysis: {components_with_desc}/{total_components} components have descriptions "
        f"({comp_coverage:.0f}%), {connections_with_desc}/{total_connections} connections have descriptions "
        f"({conn_coverage:.0f}%)."
    )
    if desc_threshold_met:
        coverage_note += (
            f" Component description coverage meets the 70% quality threshold — "
            f"do NOT penalise missing descriptions heavily; treat this as acceptable coverage."
        )
    if conn_threshold_met and total_connections > 0:
        coverage_note += (
            f" Connection description coverage meets the 70% threshold — "
            f"connection clarity should not be heavily penalised."
        )

    # Enhanced component description with detailed properties analysis
    components_text_parts = []
    for comp in request.components:
        comp_desc = f'- **{comp.type.value.upper()}**: "{comp.label}"'

        if comp.properties:
            # Extract and format component description if available
            description = comp.properties.get("description", "")
            if description:
                comp_desc += f"\n  Description: {description}"

            # Include other relevant properties, excluding internal frontend-only keys
            other_props = {
                k: v for k, v in comp.properties.items()
                if k != "description" and k not in _INTERNAL_PROPS
            }
            if other_props:
                comp_desc += f"\n  Additional Properties: {other_props}"
        else:
            comp_desc += "\n  ⚠️ No description provided - component purpose unclear"

        components_text_parts.append(comp_desc)

    components_text = "\n".join(components_text_parts)

    # Enhanced connection descriptions with reasoning
    conn_parts = []
    if request.connections:
        for conn in request.connections:
            conn_desc = f"- **{conn.source} → {conn.target}**"
            if conn.label:
                conn_desc += f": {conn.label}"
            if conn.type:
                conn_desc += f" (Type: {conn.type})"
            if conn.description and conn.description.strip():
                conn_desc += f"\n  Description: {conn.description}"
            else:
                conn_desc += "\n  ⚠️ No description - connection purpose unclear"
            conn_parts.append(conn_desc)
        connections_text = "\n".join(conn_parts)
    else:
        connections_text = "⚠️ No explicit connections defined - data flow unclear"

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

**DESCRIPTION COVERAGE REPORT (use this when applying scoring rules below):**
{coverage_note}
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
Rate each aspect from 0-100, considering the problem context, requirements, and component descriptions:

1. **Scalability**: Can this handle growth in users, data, and traffic as required by the problem? Consider horizontal/vertical scaling strategies, stateless design, partitioning, and whether component descriptions justify scaling decisions.

2. **Reliability**: Will this remain available during failures and meet the reliability requirements? Evaluate redundancy, failover mechanisms, health checks, circuit breakers, data replication, and SLA targets.

3. **Security**: Are proper security measures implemented? Check authentication (AuthN), authorization (AuthZ), encryption in-transit and at-rest, secret management, network segmentation, WAF/DDoS protection, and input validation.

4. **Maintainability**: Is this manageable and evolvable? Consider separation of concerns, modularity, logging quality, documentation clarity, API versioning, and whether the architecture is easy for a new engineer to understand.

5. **Performance**: Does the design meet latency and throughput requirements? Evaluate caching layers (CDN, in-memory), database query optimisation, async processing, connection pooling, and any performance bottlenecks.

6. **Cost Efficiency**: Is the infrastructure cost-conscious? Assess over-provisioning risks, use of managed vs self-hosted services, auto-scaling to avoid idle capacity, data transfer costs, and storage tier choices.

7. **Observability**: Can engineers understand system behaviour in production? Check for distributed tracing, structured logging, metrics/dashboards, alerting strategy, error tracking, and SLO/SLI definitions.

8. **Deliverability**: How implementation-ready is this HLD? Score based on: completeness of component coverage for all stated requirements, specificity of technology choices, clarity for a team to start building, handling of edge cases (auth, failure modes, data migration), and absence of hand-wavy "magic" steps.

9. **Requirements Alignment**: How well does this solution address the specific problem requirements? Evaluate if component descriptions clearly justify why each component is needed for the specific problem.

10. **Constraint Compliance**: Does this solution respect the given constraints (budget, time, technology, etc.)? Consider if component choices and descriptions show awareness of constraints.

11. **Component Justification**: Are component purposes clearly explained? Do descriptions provide sufficient detail about why each component is necessary and how it contributes to the solution?

12. **Connection Clarity**: Are the relationships between components well-defined? Do connection labels and descriptions explain the data flow, protocols, and interaction patterns?

**EVALUATION GUIDELINES:**

**Component Description Quality:**
- Coverage threshold is 70%. If ≥70% of components have meaningful descriptions, do NOT flag missing descriptions as serious issues.
- When coverage is below 70%: deduct 20-40 points from component_justification.
- When coverage is ≥70%: component_justification should start from 70+ and be adjusted only by overall description quality.
- Descriptions with rich detail (purpose, tech choice, responsibilities) should score 85+.

**Connection Reasoning:**
- Coverage threshold is 70%. If ≥70% of connections have descriptions, do NOT penalise connection_clarity heavily.
- When coverage is below 70%: deduct 20-40 points from connection_clarity.
- When coverage is ≥70%: connection_clarity should start from 70+ and reflect quality of described connections.
- Missing connections in a multi-component system still impact scalability/reliability.

**Performance:**
- Look for caching (Redis, Memcached), CDN, async queues, read replicas, connection pooling.
- If none of these are present and the problem is read-heavy or high-traffic, score ≤50.

**Cost Efficiency:**
- Penalise designs that use large dedicated servers where managed/serverless options are appropriate.
- Reward auto-scaling, spot instances, tiered storage, and cost-aware technology choices.

**Observability:**
- Reward presence of monitoring, logging, alerting, or tracing components.
- A design with zero observability components should score ≤40 for production systems.

**Deliverability:**
- Score based on completeness: does every stated requirement map to ≥1 component?
- Penalise vague "services" without clear technology or responsibility boundaries.
- Reward clear data flow, failure handling, auth flow, and migration/deployment notes.

**STRICT SCORING RULES (apply ONLY when coverage thresholds are NOT met):**
- Empty explanations (when coverage thresholds are not met) should result in scores below 50
- Missing component descriptions when coverage < 70% should significantly impact component_justification (0-30 range)
- No connections should result in very low connection_clarity scores (0-20 range)
- Connections without descriptions when coverage < 70% should reduce connection_clarity (cap at 60)
- Vague or placeholder text should be treated as missing information
- When coverage thresholds ARE met, penalise only architecture-level issues, not documentation gaps

**RESPONSE FORMAT:**
Respond with a valid JSON object in this exact structure:

{{
  "scores": {{
    "scalability": 75,
    "reliability": 80,
    "security": 65,
    "maintainability": 70,
    "performance": 60,
    "cost_efficiency": 55,
    "observability": 50,
    "deliverability": 70,
    "requirements_alignment": 85,
    "constraint_compliance": 90,
    "component_justification": 80,
    "connection_clarity": 75
  }},
  "feedback": [
    {{
      "type": "success|warning|error|info",
      "message": "Specific feedback message",
      "category": "scalability|reliability|security|maintainability|performance|cost|observability|deliverability|requirements|constraints|component_description|connection_reasoning",
      "priority": 1
    }}
  ],
  "detailed_analysis": {{
    "scalability": "2-3 sentence analysis of scalability strengths and gaps in this specific design.",
    "reliability": "2-3 sentence analysis of reliability provisions and what is missing.",
    "security": "2-3 sentence analysis of security posture and vulnerabilities.",
    "maintainability": "2-3 sentence analysis of maintainability aspects.",
    "performance": "2-3 sentence analysis of performance design choices and bottlenecks.",
    "cost_efficiency": "2-3 sentence analysis of cost implications of the architecture choices.",
    "observability": "2-3 sentence analysis of monitoring, logging, and tracing coverage.",
    "deliverability": "2-3 sentence analysis of how implementation-ready this design is."
  }},
  "strengths": [
    "List of architectural strengths specific to this design"
  ],
  "improvements": [
    "Specific actionable improvements with concrete technology suggestions"
  ],
  "missing_components": [
    "Components that should be added with explanations of why they are needed"
  ],
  "missing_descriptions": [
    "Component labels that lack proper descriptions"
  ],
  "unclear_connections": [
    "Connection identifiers that need better explanation"
  ],
  "suggestions": [
    "Additional forward-looking recommendations"
  ],
  "interview_questions": [
    "How would you handle cache invalidation when data is updated in this design?",
    "Walk me through what happens when your primary database goes down.",
    "How would you scale this system to 10x current traffic?",
    "What monitoring alerts would you set up first for this system in production?",
    "How would you handle a security breach in the authentication layer?"
  ]
}}

**SPECIAL FOCUS AREAS:**
- Evaluate all 12 dimensions: scalability, reliability, security, maintainability, performance, cost_efficiency, observability, deliverability, requirements_alignment, constraint_compliance, component_justification, connection_clarity
- Write a `detailed_analysis` entry for EACH of the first 8 dimensions (2-3 sentences each, specific to THIS design — not generic advice)
- Generate 5-7 `interview_questions` that a technical interviewer would ask about THIS specific design — they must be tailored to the technology choices, architecture decisions, and requirements visible in the submission (NOT generic system design questions)
- Identify components truly missing from the design given the stated requirements
- Flag missing or inadequate component descriptions as areas for improvement

**INTERVIEW QUESTIONS GUIDANCE:**
- Questions must probe THIS design specifically (e.g. reference the actual components used)
- Cover at least: one failure/resilience scenario, one scaling scenario, one security/auth scenario, one operational/monitoring scenario, one trade-off or alternative design decision
- Make the candidate think, not just recite theory

**CRITICAL SCORING INSTRUCTIONS:**
🚨 **BE STRICT BUT FAIR**: High scores (85+) require excellent architecture across all dimensions
- Empty descriptions when coverage < 70% = MAJOR deductions from component_justification
- Missing connections in multi-component systems = MAJOR deductions from connection_clarity and deliverability
- No observability components in a production system = score ≤40 for observability
- Vague component choices ("a service") without specifics = low deliverability score (30-50)
- When coverage thresholds ARE met, penalise only architecture-level issues, not documentation gaps

**MINIMUM REQUIREMENTS FOR DECENT SCORES (60+):**
- At least 70% of components must have meaningful descriptions explaining their role
- Connections must be defined showing data flow
- User explanation should justify architectural choices
- Component types should match their intended purpose
- At least some consideration of failure handling, security, and observability

Focus on practical, actionable feedback that helps users improve their system design skills and pass real system design interviews.
"""


def get_specialized_prompt(domain: str, request: AssessmentRequest) -> str:
    """Generate domain-specific prompts for specialized assessments"""
    base_prompt = get_assessment_prompt(request)

    domain_contexts = {
        "microservices": """Focus on service boundaries, data consistency, and inter-service communication patterns. 
        Pay special attention to how component descriptions justify service decomposition and whether connection descriptions explain inter-service protocols and data exchange patterns.""",
        "data_intensive": """Emphasize data modeling, storage solutions, and data flow patterns. 
        Evaluate whether component descriptions explain data storage decisions, processing capabilities, and whether connections clearly show data flow and transformation steps.""",
        "real_time": """Prioritize latency, throughput, and real-time processing capabilities. 
        Check if component descriptions address performance characteristics and whether connection descriptions explain real-time data flow and processing pipelines.""",
        "security_critical": """Deep dive into security controls, authentication, authorization, and compliance. 
        Ensure component descriptions address security measures, encryption, and access controls, and that connections explain secure communication protocols and data protection.""",
    }

    if domain in domain_contexts:
        return base_prompt + f"\n\n**DOMAIN FOCUS:**\n{domain_contexts[domain]}"

    return base_prompt
