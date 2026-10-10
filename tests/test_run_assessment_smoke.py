"""The live smoke runner must assess the same explicit guide actions as fixture replay."""

import json
from pathlib import Path

import pytest

from scripts.run_assessment_smoke import build_request
from scripts.walkthrough_fixtures import FixtureError, build_architecture, make_request


ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = ROOT / "data/assessment-reference-candidates/walkthroughs/6901ef1b9420d83630aca871.json"
PROBLEMS_PATH = ROOT / "tests/fixtures/walkthroughs/problems.json"


def matching_spec(revision):
    return {
        "schemaVersion": 1,
        "revision": revision,
        "functional": [{"id": "document-create", "text": "Create and edit documents", "scope": "core"}],
        "nonFunctional": [],
        "assumptions": [],
    }


def test_smoke_request_matches_applied_walkthrough_actions():
    guide = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    problems = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    problem = next(row for row in problems if row["id"] == guide["problem_id"])
    spec = matching_spec(guide["requirementRevision"])

    request = build_request(problem, guide, spec)
    expected = make_request(problem, guide, build_architecture(guide), spec)

    assert request == expected
    assert request["problem"]["requirementRevision"] == spec["revision"]
    assert request["problem"]["requirementSpec"] == spec
    assert all("originalComponentId" in row["properties"] for row in request["components"])


def test_candidate_cannot_claim_a_missing_requirement_revision():
    guide = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    problems = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    problem = next(row for row in problems if row["id"] == guide["problem_id"])

    with pytest.raises(FixtureError, match="matching requirement spec"):
        build_request(problem, guide)


def test_published_legacy_fixture_still_builds_without_a_manifest():
    path = ROOT / "tests/fixtures/walkthroughs/6901ef1b9420d83630aca871.json"
    guide = json.loads(path.read_text(encoding="utf-8"))
    problems = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    problem = next(row for row in problems if row["id"] == guide["problem_id"])

    request = build_request(problem, guide)

    assert request["problem"]["requirementRevision"].startswith("legacy-")
    assert "requirementSpec" not in request["problem"]
