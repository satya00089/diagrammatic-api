"""Offline contract checks are not evidence that a live AI score passed."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.walkthrough_models import GuidedWalkthrough
from app.models.request_models import AssessmentRequest
from app.services.walkthrough_reference import compare_walkthrough_structure, get_fallback_reference_checks

CANDIDATES = Path(__file__).resolve().parents[1] / "data/assessment-reference-candidates/walkthroughs"


@pytest.mark.parametrize("path", sorted(CANDIDATES.glob("*.json")), ids=lambda path: path.stem)
def test_candidates_preserve_graph_and_explicit_updates(path):
    guide = GuidedWalkthrough.model_validate_json(path.read_text(encoding="utf-8"))
    assert len(guide.steps) == guide.totalSteps
    assert len({step.id for step in guide.steps}) == guide.totalSteps
    node_ids = set()
    edge_ids = set()
    for step in guide.steps:
        if step.component:
            assert step.component.nodeId not in node_ids
            node_ids.add(step.component.nodeId)
        if step.connection:
            assert step.connection.sourceNodeId in node_ids
            assert step.connection.targetNodeId in node_ids
            assert step.connection.edgeId not in edge_ids
            edge_ids.add(step.connection.edgeId)
        if step.componentUpdate:
            assert step.componentUpdate.nodeId in node_ids
            assert step.componentUpdate.properties


def test_reference_checks_match_roles_not_positions_or_reference_ids():
    raw = {"steps": [
        {"type": "add_component", "component": {"nodeId": "reference-db", "componentType": "database", "label": "Database"}},
    ]}
    request = AssessmentRequest(components=[{"id": "user-node", "type": "database", "label": "Postgres replica", "position": {"x": 100, "y": 900}}])
    checks = compare_walkthrough_structure(request, raw)
    assert checks[0]["status"] == "supported"
    assert "behavior" in checks[0]["explanation"]
    assert all("score" not in check for check in checks)


def test_document_reference_does_not_claim_client_ip_affinity_or_efs():
    raw = json.loads((CANDIDATES / "6901ef1b9420d83630aca871.json").read_text(encoding="utf-8"))
    components = {step["component"]["nodeId"]: step["component"] for step in raw["steps"] if step.get("component")}
    assert components["guided_loadbalancer"]["properties"]["routingKey"] == "document_id"
    assert components["guided_file_storage"]["componentType"] == "object-storage"
    assert components["guided_file_storage"]["properties"]["provider"] == "S3"
    assert "deduplicate" in components["guided_collab_server"]["properties"]["reconnectProtocol"]


def test_scheduler_backoff_is_an_explicit_persisted_recovery_action():
    guide = json.loads((CANDIDATES / "6901ef1b9420d83630aca869.json").read_text(encoding="utf-8"))
    components = {step["component"]["nodeId"]: step["component"] for step in guide["steps"] if step.get("component")}
    assert "full-jitter exponential backoff" in components["guided_worker_pool"]["properties"]["retryBackoff"]
    assert "outbox" in components["guided_job_store"]["properties"]["retryState"]
    retry_step = next(step for step in guide["steps"] if step["stepNumber"] == 23)
    assert retry_step["type"] == "update_component"
    assert retry_step["componentUpdate"]["nodeId"] == "guided_scheduler"
    assert "next_run_at is due" in retry_step["componentUpdate"]["properties"]["retryPromotion"]


@pytest.mark.asyncio
@pytest.mark.parametrize("requested,reference,compatible", [
    (None, None, True), ("r1", "r1", True),
    ("r2", None, False), (None, "r2", False), ("r2", "r1", False),
])
async def test_fallback_never_compares_a_different_or_unversioned_brief(monkeypatch, requested, reference, compatible):
    with patch("boto3.resource"):
        from app.services import dynamodb_service as database_module
    guide = {"requirementRevision": reference, "steps": [{
        "type": "add_component", "component": {"nodeId": "ref", "componentType": "database", "label": "DB"},
    }]}
    monkeypatch.setattr(database_module, "dynamodb_service", SimpleNamespace(
        get_walkthrough_by_problem_id=lambda _: guide,
    ))
    request = AssessmentRequest(components=[{"id": "db", "type": "database", "label": "DB"}],
                                problem={"id": "catalog-id", "title": "Database", "description": "Design storage",
                                         "requirementRevision": requested})
    checks = await get_fallback_reference_checks(request)
    assert bool(checks) is compatible
