from app.models.request_models import AssessmentRequest, SystemComponent
from typing import List, Tuple

def validate_system_components(components: List[SystemComponent]) -> Tuple[bool, List[str]]:
    """
    Validate system components for basic architectural principles
    Returns (is_valid, list_of_issues)
    """
    issues = []
    
    if not components:
        return False, ["No components provided for assessment"]
    
    # Check for essential components
    component_types = {comp.type.value for comp in components}
    
    # Basic validation rules
    if len(components) < 2:
        issues.append("System design should have at least 2 components")
    
    # Check for database in data-driven applications
    has_backend = "backend" in component_types
    has_database = "database" in component_types
    
    if has_backend and not has_database:
        issues.append("Backend service detected but no database component found")
    
    # Check for load balancer in scalable systems
    if len(components) > 3 and "load-balancer" not in component_types:
        issues.append("Consider adding a load balancer for better scalability")
    
    # Check for monitoring
    if len(components) > 2 and "monitoring" not in component_types:
        issues.append("Consider adding monitoring components for observability")
    
    return len(issues) == 0, issues

def validate_connections(request: AssessmentRequest) -> Tuple[bool, List[str]]:
    """
    Validate system connections for consistency
    Returns (is_valid, list_of_issues)
    """
    issues = []
    
    if not request.connections:
        return True, []  # No connections to validate
    
    component_ids = {comp.id for comp in request.components}
    
    for conn in request.connections:
        # Check if source and target components exist
        if conn.source not in component_ids:
            issues.append(f"Connection source '{conn.source}' does not exist in components")
        
        if conn.target not in component_ids:
            issues.append(f"Connection target '{conn.target}' does not exist in components")
    
    return len(issues) == 0, issues
