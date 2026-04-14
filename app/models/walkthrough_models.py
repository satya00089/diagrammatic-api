"""Models for guided walkthrough data."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class GuidedPropertyEntry(BaseModel):
    """A single canvas property: the value and an HTML explanation of why."""

    value: str
    description: str = ""


class GuidedComponentStep(BaseModel):
    """A component to be added to the canvas as part of a guided step."""

    nodeId: str
    componentType: str
    label: str
    description: Optional[str] = None
    position: Dict[str, float]
    iconUrl: Optional[str] = None
    properties: Dict[str, GuidedPropertyEntry] = {}
    highlightReason: str


class GuidedConnectionStep(BaseModel):
    """A connection (edge) to be added to the canvas as part of a guided step."""

    edgeId: str
    sourceNodeId: str
    targetNodeId: str
    connectionType: str
    label: str
    description: str


class GuidedDecisionAlternative(BaseModel):
    """An alternative option in a decision point step."""

    option: str
    tradeoff: str


class GuidedDecisionPoint(BaseModel):
    """A decision point step explaining why one option was chosen over alternatives."""

    question: str
    chosen: str
    chosenReason: str
    alternatives: List[GuidedDecisionAlternative] = []


class GuidedScaleTrigger(BaseModel):
    """A scale trigger step explaining when and how to scale a component."""

    metric: str
    action: str
    impact: str
    component: Optional[GuidedComponentStep] = None


class GuidedStep(BaseModel):
    """A single step in a guided walkthrough."""

    id: str
    stepNumber: int
    phase: str
    title: str
    type: str  # explanation | add_component | add_connection | decision_point | scale_trigger
    content: str
    component: Optional[GuidedComponentStep] = None
    connection: Optional[GuidedConnectionStep] = None
    decision: Optional[GuidedDecisionPoint] = None
    scaleTrigger: Optional[GuidedScaleTrigger] = None


class GuidedWalkthroughPhase(BaseModel):
    """A phase grouping steps in the walkthrough."""

    name: str
    stepRange: List[int]  # [start, end] inclusive
    description: str


class GuidedWalkthrough(BaseModel):
    """Full guided walkthrough for a problem."""

    problem_id: str
    version: str
    totalSteps: int
    phases: List[GuidedWalkthroughPhase] = []
    steps: List[GuidedStep] = []
