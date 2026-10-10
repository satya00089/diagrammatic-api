"""Export public problem/guide inputs using AWS CLI, without remote mutations.

These snapshots support offline migrations and reproducible assessment fixtures.
No user attempts, credentials, or private diagrams are exported.
"""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path
import subprocess

from boto3.dynamodb.types import TypeDeserializer


def scan(table: str, region: str) -> list[dict]:
    env = {**os.environ, "AWS_PAGER": "", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    result = subprocess.run(
        ["aws", "dynamodb", "scan", "--table-name", table, "--region", region,
         "--output", "json"],
        check=True, capture_output=True, env=env,
    )
    deserialize = TypeDeserializer().deserialize
    return [{key: deserialize(value) for key, value in item.items()}
            for item in json.loads(result.stdout.decode("utf-8"))["Items"]]


def encode_number(value: object) -> object:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--region", default="ap-south-1")
    args = parser.parse_args()
    problems = scan("diagrammatic_problems", args.region)
    walkthroughs = scan("diagrammatic_guided_walkthroughs", args.region)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "problems.json").write_text(
        json.dumps(sorted(problems, key=lambda p: p["id"]), indent=2,
                   ensure_ascii=False, default=encode_number) + "\n", encoding="utf-8",
    )
    for guide in walkthroughs:
        (args.output / f"{guide['problem_id']}.json").write_text(
            json.dumps(guide, indent=2, ensure_ascii=False, default=encode_number) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"problems": len(problems), "walkthroughs": len(walkthroughs),
                      "output": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
