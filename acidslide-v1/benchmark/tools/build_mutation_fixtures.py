#!/usr/bin/env python3
"""Generate and execute the candidate operator-level mutation fixture matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ACIDSLIDE_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ACIDSLIDE_ROOT / "benchmark"
GRADER = ACIDSLIDE_ROOT / "grader"
sys.path.insert(0, str(GRADER))

from acidslide.checklist import load_checklist  # noqa: E402
from acidslide.mutation_fixtures import (  # noqa: E402
    build_fixture_index,
    build_mutation_expectations,
    execute_fixture_matrix,
)


def _documents() -> dict[str, dict[str, Any]]:
    items = load_checklist(BENCHMARK / "checklist", tier=3)
    inventory = json.loads(
        (BENCHMARK / "requirements" / "scored-assertion-inventory.json").read_text(encoding="utf-8")
    )
    fixture_index = build_fixture_index(items, inventory)
    expectations = build_mutation_expectations(fixture_index)
    execution = execute_fixture_matrix(items, fixture_index)
    return {
        "fixture-index-v1.json": fixture_index,
        "mutation-expectations-v1.json": expectations,
        "execution-report-v1.json": execution,
    }


def _encoded(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BENCHMARK / "fixtures" / "mutations",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if checked-in generated documents are absent or stale.",
    )
    args = parser.parse_args()

    documents = _documents()
    if args.check:
        stale = [
            name
            for name, document in documents.items()
            if not (args.output_dir / name).is_file()
            or (args.output_dir / name).read_text(encoding="utf-8") != _encoded(document)
        ]
        if stale:
            raise SystemExit(f"Generated mutation documents are stale: {', '.join(stale)}")
    else:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, document in documents.items():
            (args.output_dir / name).write_text(_encoded(document), encoding="utf-8")

    summary = documents["execution-report-v1.json"]["summary"]
    print(
        "AcidSlide mutation fixtures: "
        f"{summary['killed_mutants']}/{summary['executed_single_fault_negative_fixtures']} "
        "mutants killed; "
        f"{summary['unimplemented_items']} unimplemented; "
        "0 release-evidence claims"
    )


if __name__ == "__main__":
    main()
