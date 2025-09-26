#!/usr/bin/env python3
"""Test the updated request models with problem context."""

from app.models.request_models import AssessmentRequest, ProblemContext, SystemComponent

def test_problem_context():
    """Test the new problem context functionality."""
    
    # Create a problem context
    problem = ProblemContext(
        title="E-commerce Platform",
        description="Design a scalable e-commerce platform that can handle Black Friday traffic",
        requirements="Handle 1M+ concurrent users, 99.9% uptime",
        constraints="Budget $50K/month, must use AWS",
        difficulty="Hard", 
        category="System Design",
        estimatedTime="45 minutes"
    )
    
    # Create components
    components = [
        SystemComponent(id="web-1", type="frontend", label="Web Frontend"),
        SystemComponent(id="api-1", type="backend", label="API Gateway"),
        SystemComponent(id="db-1", type="database", label="Product Database")
    ]
    
    # Create assessment request with problem context
    request = AssessmentRequest(
        components=components,
        connections=[],
        explanation="Basic e-commerce architecture",
        problem=problem
    )
    
    print("✅ SUCCESS: Problem context integration works!")
    print(f"Problem Title: {request.problem.title}")
    print(f"Problem Description: {request.problem.description}")
    print(f"Difficulty: {request.problem.difficulty}")
    print(f"Requirements: {request.problem.requirements}")
    print(f"Constraints: {request.problem.constraints}")
    
    return True

if __name__ == "__main__":
    test_problem_context()
