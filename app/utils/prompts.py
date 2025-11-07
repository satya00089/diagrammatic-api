"""Utility functions to generate prompts for system design assessment."""

from app.models.request_models import AssessmentRequest


def get_assessment_prompt(request: AssessmentRequest) -> str:
    """Generate the assessment prompt for the given request."""

    # Enhanced component description with detailed properties analysis
    components_text = []
    for comp in request.components:
        comp_desc = f'- **{comp.type.value.upper()}**: "{comp.label}"'

        if comp.properties:
            # Extract and format component description if available
            description = comp.properties.get("description", "")
            if description:
                comp_desc += f"\n  Description: {description}"

            # Include other relevant properties
            other_props = {
                k: v for k, v in comp.properties.items() if k != "description"
            }
            if other_props:
                comp_desc += f"\n  Additional Properties: {other_props}"
        else:
            comp_desc += "\n  ⚠️ No description provided - component purpose unclear"

        components_text.append(comp_desc)

    components_text = "\n".join(components_text)

    # Enhanced connection descriptions with reasoning
    connections_text = []
    if request.connections:
        for conn in request.connections:
            conn_desc = f"- **{conn.source} → {conn.target}**"
            if conn.label:
                conn_desc += f": {conn.label}"
            if conn.type:
                conn_desc += f" (Type: {conn.type})"
            connections_text.append(conn_desc)
        connections_text = "\n".join(connections_text)
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

1. **Scalability**: Can this handle growth in users, data, and traffic as required by the problem? Consider if component descriptions justify scaling decisions and if connections support distributed architecture.

2. **Reliability**: Will this remain available during failures and meet the reliability requirements? Evaluate if component descriptions explain redundancy, failover mechanisms, and reliability measures.

3. **Security**: Are proper security measures implemented for this type of system? Check if component descriptions address security concerns, authentication, authorization, and data protection.

4. **Maintainability**: Is this manageable, well-documented, and appropriate for the problem complexity? Consider the clarity of component descriptions and whether they explain maintenance considerations.

5. **Requirements Alignment**: How well does this solution address the specific problem requirements? Evaluate if component descriptions clearly justify why each component is needed for the specific problem.

6. **Constraint Compliance**: Does this solution respect the given constraints (budget, time, technology, etc.)? Consider if component choices and descriptions show awareness of constraints.

7. **Component Justification**: Are component purposes clearly explained? Do descriptions provide sufficient detail about why each component is necessary and how it contributes to the solution?

8. **Connection Clarity**: Are the relationships between components well-defined? Do connection labels explain the data flow and interaction patterns?

**EVALUATION GUIDELINES:**

**Component Description Quality:**
- **SEVERELY PENALIZE** missing or empty descriptions (HTML tags like `<p></p>` count as empty)
- **DEDUCT 30-50 points** from component_justification for each component lacking proper description
- **DEDUCT 10-20 points** from overall scores when component purposes are unclear
- Award higher scores (80+) ONLY when descriptions clearly explain the component's role, technology choices, and architectural decisions
- Consider whether descriptions address scalability, reliability, security aspects of each component

**Connection Reasoning:**
- **SEVERELY PENALIZE** missing connections in complex systems
- **DEDUCT 20-40 points** from connection_clarity when no connections are defined
- **DEDUCT points** from scalability and reliability when data flow is unclear
- Evaluate if connection types and protocols are appropriate
- Check if data flow and communication patterns are well-justified

**STRICT SCORING RULES:**
- Empty explanations should result in scores below 50 for most criteria
- Missing component descriptions should significantly impact component_justification (0-30 range)
- No connections should result in very low connection_clarity scores (0-20 range)
- Vague or placeholder text should be treated as missing information

**RESPONSE FORMAT:**
Respond with a valid JSON object in this exact structure:

{{
  "scores": {{
    "scalability": 75,
    "reliability": 80,
    "security": 65,
    "maintainability": 70,
    "requirements_alignment": 85,
    "constraint_compliance": 90,
    "component_justification": 80,
    "connection_clarity": 75
  }},
  "feedback": [
    {{
      "type": "success|warning|error|info",
      "message": "Specific feedback message addressing component descriptions and connections",
      "category": "scalability|reliability|security|maintainability|performance|cost|requirements|constraints|component_description|connection_reasoning",
      "priority": 1
    }}
  ],
  "strengths": [
    "List of architectural strengths, well-described components, and clear connection reasoning"
  ],
  "improvements": [
    "Specific actionable improvements including better component descriptions and connection justifications"
  ],
  "missing_components": [
    "Components that should be added with explanations of why they're needed"
  ],
  "missing_descriptions": [
    "Components that lack proper descriptions or justification"
  ],
  "unclear_connections": [
    "Connections that need better explanation or justification"
  ],
  "suggestions": [
    "Additional recommendations for improving component descriptions and architectural clarity"
  ]
}}

**SPECIAL FOCUS AREAS:**
- Evaluate component description quality and completeness
- Assess whether each component's purpose and technology choices are well-justified  
- Check if connections between components are clearly explained with proper reasoning
- Consider whether the architecture explanation demonstrates understanding of why specific components are needed
- Flag missing or inadequate component descriptions as areas for improvement

**CRITICAL SCORING INSTRUCTIONS:**
🚨 **BE STRICT**: This is a technical assessment, not participation trophy
- Empty descriptions (`<p></p>`, empty strings, placeholder text) = MAJOR point deductions
- Missing connections in multi-component systems = MAJOR point deductions
- Vague explanations = LOW scores (30-50 range)
- No justification for component choices = component_justification should be 0-30
- For the given URL shortener problem, missing critical components (cache, load balancer, analytics) should significantly impact scores

**MINIMUM REQUIREMENTS FOR DECENT SCORES (60+):**
- Each component must have meaningful description explaining its role
- Connections must be defined showing data flow
- User explanation should justify architectural choices
- Component types should match their intended purpose

Focus on practical, actionable feedback that helps improve both the system design and the quality of architectural documentation and reasoning.
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
