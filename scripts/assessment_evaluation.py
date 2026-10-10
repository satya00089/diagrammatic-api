"""Prepare public fixtures and evaluate recorded AI results locally; no SDK/network calls."""

from __future__ import annotations

import argparse
from copy import deepcopy
import inspect
import json
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.requirements_migration import digest, read_json, write_json
from scripts.walkthrough_fixtures import FixtureError, prepare_bundle, validate_architecture


FROZEN_KEYS = ("model", "modelConfigHash", "promptVersion", "rubricVersion")


def validate_bundle(bundle: dict) -> None:
    if bundle.get("formatVersion") != 1 or bundle.get("kind") != "local-assessment-evaluation-bundle" or bundle.get("repeats") != 5:
        raise FixtureError("Versioned bundle must have exactly five planned repeats")
    if bundle.get("fixtureScope") != "public-reference-only":
        raise FixtureError("Only public reference fixtures are supported")
    ids = [case.get("id") for case in bundle.get("cases", [])]
    if not ids or len(ids) != len(set(ids)):
        raise FixtureError("Missing/duplicate evaluation case IDs")
    for case in bundle["cases"]:
        validate_architecture(case["request"])
        if case.get("inputHash") != digest(case["request"]):
            raise FixtureError(f"{case['id']}: changed input hash")
        if case.get("kind") not in ("complete", "negative", "alternative"):
            raise FixtureError("Unknown fixture kind")
        if case["kind"] != "complete" and case.get("counterpart") not in ids:
            raise FixtureError("Negative/alternative needs a known counterpart")
        context = case["request"].get("problem", {})
        provenance = case.get("provenance", {})
        if provenance.get("requirementRevision") != context.get("requirementRevision") or provenance.get("requirementHash") != digest(context):
            raise FixtureError("Frozen requirement context/provenance mismatch")


def evaluation_plan(bundle: dict) -> dict:
    validate_bundle(bundle)
    return {"formatVersion": 1, "bundleHash": digest(bundle), "langfuseSdkBaseline": "4.15.2",
            "runs": [{"caseId": case["id"], "repeat": repeat, "inputHash": case["inputHash"],
                      "provenance": case["provenance"], "request": deepcopy(case["request"])}
                     for case in bundle["cases"] for repeat in range(1, 6)]}


def _score(result: dict) -> float | None:
    value = result.get("overall_score", result.get("overallScore"))
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
        return None
    return float(value)


def evaluate_results(bundle: dict, recorded: dict) -> dict:
    """All failures survive in the report. Extra attempts/duplicates cannot replace failures."""
    validate_bundle(bundle)
    if recorded.get("bundleHash") != digest(bundle):
        raise FixtureError("Recorded results must match the exact frozen bundle hash")
    experiment = recorded.get("experiment", {})
    failures = []
    if any(not experiment.get(key) for key in FROZEN_KEYS):
        failures.append({"kind": "provenance", "message": "Frozen model/config/prompt/rubric versions required"})
    if recorded.get("langfuseSdkBaseline", "4.15.2") != "4.15.2":
        failures.append({"kind": "provenance", "message": "SDK baseline changed"})
    cases = {case["id"]: case for case in bundle["cases"]}
    runs = {}
    evaluated = []
    fallback_count = 0
    for row in recorded.get("runs", []):
        key = (row.get("caseId"), row.get("repeat"))
        if key[0] not in cases or type(key[1]) is not int or key[1] not in range(1, 6):
            failures.append({"kind": "unexpected_run", "caseId": key[0], "repeat": key[1]})
            continue
        if key in runs:
            failures.append({"kind": "duplicate_run", "caseId": key[0], "repeat": key[1],
                             "message": "Retries/cherry-picked replacements are prohibited"})
            continue
        runs[key] = row
        case = cases[key[0]]
        problems = []
        provenance = row.get("provenance", {})
        if row.get("inputHash") != case["inputHash"]:
            problems.append("Input hash mismatch")
        for field in FROZEN_KEYS:
            if provenance.get(field) != experiment.get(field):
                problems.append(f"Frozen {field} mismatch")
        for field in ("requirementRevision", "walkthroughVersion", "requirementHash", "walkthroughHash"):
            if not case["provenance"].get(field) or provenance.get(field) != case["provenance"].get(field):
                problems.append(f"Fixture {field} mismatch")
        if row.get("error"):
            problems.append("Review failed: " + str(row["error"]))
        result = row.get("result", {})
        if not isinstance(result, dict):
            result = {}
            problems.append("Malformed assessment result")
        ai = result.get("source") == "ai" and result.get("scoreAvailable", result.get("score_available")) is True
        if not ai:
            fallback_count += 1
            problems.append("Acceptance requires source=ai and explicit scoreAvailable=true")
        score = _score(result) if ai else None
        if score is None:
            problems.append("Missing/invalid AI architecture score")
        findings = result.get("findings")
        if not isinstance(findings, list) or any(not isinstance(finding, dict) for finding in findings):
            findings = []
            problems.append("Missing/malformed structured findings")
        expected = case.get("expected", {})
        text = " ".join(str(finding.get(field, "")) for finding in findings
                        for field in ("title", "explanation", "recommendation")).lower()
        if any(term.lower() in text for term in expected.get("forbiddenFindingTerms", [])):
            problems.append("Forbidden unsupported claim in findings")
        ids = {component["id"] for component in case["request"]["components"]}
        ids.update(connection["id"] for connection in case["request"]["connections"])
        spec = case["request"]["problem"].get("requirementSpec", {})
        requirement_ids = {entry["id"] for bucket in ("functional", "nonFunctional") for entry in spec.get(bucket, [])}
        for finding in findings:
            for field, alternate in (("componentIds", "component_ids"), ("connectionIds", "connection_ids"),
                                     ("evidenceIds", "evidence_ids")):
                references = finding.get(field, finding.get(alternate, []))
                if not isinstance(references, list) or any(reference not in ids for reference in references):
                    problems.append("Finding references unknown architecture evidence")
            references = finding.get("requirementIds", finding.get("requirement_ids", []))
            if not isinstance(references, list) or any(reference not in requirement_ids for reference in references):
                problems.append("Finding references unknown requirement IDs")
            if finding.get("unsupported") is True:
                problems.append("Unsupported finding")
        if case["kind"] in ("complete", "alternative"):
            if score is not None and score < max(96, expected.get("minScore") or 96):
                problems.append("Complete/alternative acceptance score must be at least 96")
            if any(finding.get("severity") == "critical" for finding in findings):
                problems.append("Critical finding on complete/valid alternative")
            required = set(expected.get("requiredCoreIds", [])) | {
                entry["id"] for bucket in ("functional", "nonFunctional")
                for entry in spec.get(bucket, []) if entry.get("scope") == "core"}
            coverage = result.get("requirement_coverage", result.get("requirementCoverage", result.get("requirementStatuses", [])))
            if isinstance(coverage, dict):
                covered = coverage
            elif isinstance(coverage, list):
                covered = {entry.get("requirement_id", entry.get("requirementId", entry.get("id"))): entry.get("status")
                           for entry in coverage if isinstance(entry, dict)}
            else:
                covered = {}
            if isinstance(coverage, list):
                seen_coverage = set()
                for entry in coverage:
                    if not isinstance(entry, dict):
                        problems.append("Malformed requirement coverage")
                        continue
                    requirement_id = entry.get("requirement_id", entry.get("requirementId", entry.get("id")))
                    if requirement_id not in requirement_ids or requirement_id in seen_coverage:
                        problems.append("Unknown/duplicate coverage requirement ID")
                    seen_coverage.add(requirement_id)
                    references = entry.get("evidence_ids", entry.get("evidenceIds", []))
                    if not isinstance(references, list) or any(reference not in ids for reference in references):
                        problems.append("Coverage references unknown architecture evidence")
            if any(covered.get(req_id) not in ("supported", "supported_by_design") for req_id in required):
                problems.append("Missing core capability/evidence coverage")
        else:
            terms = expected.get("requiredFindingTerms", [])
            if not terms or not all(term.lower() in text for term in terms):
                problems.append("Intended negative defect not detected")
            severity = expected.get("requiredSeverity")
            if severity and not any(finding.get("severity") == severity for finding in findings):
                problems.append("Negative finding severity does not match reviewed expectation")
        latency = row.get("latencyMs", result.get("processing_time_ms"))
        if latency is not None and (isinstance(latency, bool) or not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency < 0):
            problems.append("Invalid latency")
        evaluated.append({"caseId": key[0], "repeat": key[1], "score": score,
                          "latencyMs": latency, "provenance": deepcopy(provenance),
                          "traceId": result.get("trace_id"), "failures": problems,
                          "result": deepcopy(result)})
    for case_id in cases:
        for repeat in range(1, 6):
            if (case_id, repeat) not in runs:
                failures.append({"kind": "missing_run", "caseId": case_id, "repeat": repeat})
    by_key = {(row["caseId"], row["repeat"]): row for row in evaluated}
    for row in evaluated:
        case = cases[row["caseId"]]
        if case["kind"] == "negative":
            complete = by_key.get((case["counterpart"], row["repeat"]))
            if not complete or complete["score"] is None or row["score"] is None or row["score"] >= complete["score"]:
                row["failures"].append("Negative must score below its complete counterpart on the same repeat")
        failures.extend({"kind": "run_failure", "caseId": row["caseId"], "repeat": row["repeat"],
                         "message": message} for message in row["failures"])
    counts = {kind: sum(case["kind"] == kind for case in cases.values()) for kind in ("complete", "negative", "alternative")}
    labels_reviewed = all(case.get("expected", {}).get("labelStatus") == "reviewed" and
                          case["expected"].get("reviewer") for case in cases.values())
    publication_blockers = []
    if not labels_reviewed:
        publication_blockers.append("Generated expectations are drafts, not human truth")
    if counts != {"complete": 5, "negative": 5, "alternative": 2}:
        publication_blockers.append("Release development dataset needs five complete, five negative and two valid alternatives")
    if any("candidate" in case["provenance"].get("walkthroughVersion", "") for case in cases.values()):
        publication_blockers.append("Candidate walkthrough versions are not published human-approved references")
    if any(case["provenance"].get("requirementStatus") == "draft" for case in cases.values()):
        publication_blockers.append("Exercise specification is a migration draft")
    if any(case.get("transformation") for case in cases.values()):
        publication_blockers.append("Generated ID/geometry representations need replacement by reviewed design/provider alternatives")
    scores_by_case = {}
    for case_id in cases:
        values = [row["score"] for row in evaluated if row["caseId"] == case_id and row["score"] is not None]
        scores_by_case[case_id] = {"scores": values, "range": max(values) - min(values) if values else None,
                                  "mean": statistics.mean(values) if values else None}
    return {"formatVersion": 1, "bundleHash": digest(bundle), "experiment": experiment,
            "acceptancePassed": not failures, "releaseEligible": not failures and not publication_blockers,
            "publicationBlockers": publication_blockers, "failures": failures,
            "runs": evaluated, "scores": scores_by_case, "fallbackCount": fallback_count,
            "caseCounts": counts, "langfuseSdkBaseline": "4.15.2",
            "note": "Local recorded results only. No upload, score override, repair, or retry. Small development data is not an accuracy claim."}


async def run_evaluation(bundle: dict, reviewer: Callable[[dict], Any], experiment: dict) -> dict:
    """Parent-authorized runner hook. Send only the request; invoke once per planned run."""
    planned = evaluation_plan(bundle)
    recorded = {"bundleHash": planned["bundleHash"], "experiment": deepcopy(experiment),
                "langfuseSdkBaseline": "4.15.2", "runs": []}
    for row in planned["runs"]:
        result_row = {key: deepcopy(row[key]) for key in ("caseId", "repeat", "inputHash")}
        result_row["provenance"] = {**row["provenance"], **experiment}
        started = time.monotonic()
        try:
            result = reviewer(deepcopy(row["request"]))
            if inspect.isawaitable(result):
                result = await result
            if hasattr(result, "model_dump"):
                result = result.model_dump(mode="json")
            result_row["result"] = result
        except Exception as error:
            result_row["error"] = type(error).__name__ + ": " + str(error)
        result_row["latencyMs"] = (time.monotonic() - started) * 1000
        recorded["runs"].append(result_row)
    return recorded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "prepare"):
        command = sub.add_parser(name)
        command.add_argument("--fixture-dir", type=Path, default=Path("tests/fixtures/walkthroughs"))
        command.add_argument("--walkthrough-dir", type=Path)
        command.add_argument("--manifest", type=Path)
        command.add_argument("--alternative-dir", type=Path)
        command.add_argument("--output", type=Path, required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--bundle", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--bundle", type=Path, required=True)
    evaluate.add_argument("--results", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("check", "prepare"):
            bundle = prepare_bundle(args.fixture_dir, args.walkthrough_dir,
                                    read_json(args.manifest) if args.manifest else None, args.alternative_dir)
            validate_bundle(bundle)
            result = bundle if args.command == "prepare" else {
                "structurallyValid": True, "structures": bundle["structures"],
                "aiAcceptance": "not_run", "labelStatus": "draft", "brokenEdges": []}
        elif args.command == "plan":
            result = evaluation_plan(read_json(args.bundle))
        else:
            result = evaluate_results(read_json(args.bundle), read_json(args.results))
        write_json(args.output, result)
        print(json.dumps({"command": args.command, "output": str(args.output),
                          "acceptancePassed": result.get("acceptancePassed"),
                          "structures": result.get("structures")}))
        return 1 if result.get("acceptancePassed") is False else 0
    except (FixtureError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
