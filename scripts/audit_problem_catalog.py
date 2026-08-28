"""Audit and optionally remove duplicate DynamoDB problem records.

The default mode is read-only. Deletion requires both --apply and the explicit
--confirm-duplicate-deletes flag after reviewing the printed plan.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.config import get_settings


def _identity(item: dict[str, Any]) -> tuple[str, str]:
    slug = str(item.get("slug") or "").strip().lower()
    if slug:
        return "slug", slug
    title = re.sub(r"[^a-z0-9]+", " ", str(item.get("title") or "").lower()).strip()
    return "title", title


def _completeness(item: dict[str, Any]) -> tuple[int, int, str]:
    fields = ("description", "requirements", "constraints", "hints", "solution", "guide")
    present = sum(bool(item.get(field)) for field in fields)
    return present, len(str(item.get("description") or "")), str(item.get("createdAt") or "")


def scan_all(table: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    response = table.scan()
    items.extend(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete duplicate records")
    parser.add_argument(
        "--confirm-duplicate-deletes",
        action="store_true",
        help="Required with --apply to permit deletion",
    )
    args = parser.parse_args()

    if args.apply and not args.confirm_duplicate_deletes:
        parser.error("--apply requires --confirm-duplicate-deletes")

    settings = get_settings()
    table = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    ).Table(settings.dynamodb_problems_table)

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in scan_all(table):
        groups.setdefault(_identity(item), []).append(item)

    duplicate_groups = [items for items in groups.values() if len(items) > 1]
    plan: list[dict[str, Any]] = []
    for items in duplicate_groups:
        ordered = sorted(items, key=_completeness, reverse=True)
        keep = ordered[0]
        remove = ordered[1:]
        plan.append(
            {
                "identity": _identity(keep),
                "keep_id": keep.get("id"),
                "remove_ids": [item.get("id") for item in remove],
                "records": [
                    {
                        "id": item.get("id"),
                        "slug": item.get("slug"),
                        "title": item.get("title"),
                        "completeness": _completeness(item),
                    }
                    for item in ordered
                ],
            }
        )

    print(json.dumps({"table": settings.dynamodb_problems_table, "duplicate_groups": plan}, indent=2, default=str))

    if args.apply:
        for group in plan:
            for problem_id in group["remove_ids"]:
                if not problem_id:
                    raise RuntimeError(f"Cannot delete duplicate without an id: {group}")
                table.delete_item(Key={"id": problem_id})
        print(f"Deleted {sum(len(group['remove_ids']) for group in plan)} duplicate record(s).")
    else:
        print("Dry run only; no records were changed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
