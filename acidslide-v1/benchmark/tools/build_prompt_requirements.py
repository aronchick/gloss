#!/usr/bin/env python3
"""Build the traceable candidate prompt-requirements inventory.

The output is intentionally not marked frozen: line-level extraction is a
starting inventory for the two independent reviewers, not a substitute for
their atomicity/completeness review or the required fixture/mutation evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmark"
PROMPTS = BENCHMARK / "prompts"
OUTPUT = BENCHMARK / "requirements" / "prompt-requirements.json"
SCHEMA = ROOT / "schemas" / "prompt-requirements.schema.json"
LIST_PREFIX = re.compile(r"^\s*(?:\d+\.|[-*])\s+(.*)$")
TABLE_DIVIDER = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")
CONTEXT_LABEL = re.compile(r"^\s*(?:\d+\.\s+)?\*\*(.+?):?\*\*:?\s*$")
CONTENT_BEARING_DECK_HEADINGS = frozenset(
    {
        '#### Master: "AcidSlide Master"',
        '#### Layout 1: "Title Slide"',
        '#### Layout 2: "Content Slide"',
        '#### Layout 3: "Two-Column"',
        '#### Layout 4: "Blank with Footer"',
    }
)
CONTENT_BEARING_TABLE_HEADERS = {
    "benchmark/prompts/variants/canonical/slide-03.md": (
        "| Metric | Q1 2024 | Q2 2024 | Q3 2024 | Target |"
    ),
    "benchmark/prompts/variants/canonical/slide-04.md": (
        "| Region | 2023 Revenue ($M) | 2024 Revenue ($M) |"
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source(path: Path, source_id: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_type": "prompt",
        "authority": "primary",
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path.read_bytes()),
    }


def _units(path: Path, *, deck: bool) -> list[tuple[int, int, str, str]]:
    """Return every directive clause, including adjudicated content-bearing labels.

    Unitization is intentionally source-shaped and deterministic:

    - fenced examples and wrapped prose paragraphs are inclusive multi-line units;
    - list items and table data rows are individual units;
    - the five named master/layout headings and Slide 3/4 native-data headers are
      requirements because their text is content, not merely Markdown context;
    - all other table headers, dividers, section headings, and numbered subsection
      labels provide context only and are never standalone requirements.
    """

    lines = path.read_text(encoding="utf-8").splitlines()
    units: list[tuple[int, int, str, str]] = []
    context: str | None = None
    index = 0

    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        line_number = index + 1

        if not deck and stripped.startswith("**Why this slide is hard"):
            break
        if not stripped or stripped == "---":
            index += 1
            continue
        if stripped.startswith("#"):
            if deck and stripped in CONTENT_BEARING_DECK_HEADINGS:
                statement = stripped.lstrip("#").strip()
                units.append((line_number, line_number, raw, statement))
            index += 1
            continue
        if stripped.startswith("The natural-language requirements below"):
            index += 1
            continue
        if stripped.startswith("**Tier:") or stripped == "**What to build:**":
            index += 1
            continue

        label = CONTEXT_LABEL.fullmatch(raw)
        if label:
            context = label.group(1).strip()
            index += 1
            continue

        if stripped.startswith("```"):
            end = index + 1
            while end < len(lines) and not lines[end].strip().startswith("```"):
                end += 1
            if end >= len(lines):
                raise RuntimeError(f"unterminated fenced block in {path}:{line_number}")
            excerpt = "\n".join(lines[index : end + 1])
            literal = "\n".join(lines[index + 1 : end]).strip("\n")
            statement = "Use this fenced prompt content as directed"
            if context:
                statement += f" for {context}"
            statement += f":\n{literal}"
            units.append((line_number, end + 1, excerpt, statement))
            index = end + 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            if index + 1 < len(lines) and TABLE_DIVIDER.fullmatch(
                lines[index + 1].strip().replace(" ", "")
            ):
                source_path = path.relative_to(ROOT).as_posix()
                if CONTENT_BEARING_TABLE_HEADERS.get(source_path) == stripped:
                    units.append(
                        (
                            line_number,
                            line_number,
                            raw,
                            f"Use this exact table header row: {stripped}",
                        )
                    )
                # Keep the header as context for the data rows and skip the
                # divider as syntax, whether or not it is also content-bearing.
                context = " / ".join(cell.strip() for cell in stripped.strip("|").split("|"))
                index += 2
                continue
            if TABLE_DIVIDER.fullmatch(stripped.replace(" ", "")):
                index += 1
                continue
            statement = f"Use this exact table data row: {stripped}"
            if context:
                statement = f"{context}: {statement}"
            units.append((line_number, line_number, raw, statement))
            index += 1
            continue

        list_match = LIST_PREFIX.match(raw)
        if list_match:
            statement = _strip_markdown(list_match.group(1).strip())
            if context and raw.startswith(("   -", "   *", "    -", "    *")):
                statement = f"{context}: {statement}"
            units.append((line_number, line_number, raw, statement))
            inline_label = re.match(r"^\*\*(.+?)\*\*:?", list_match.group(1).strip())
            if inline_label:
                context = inline_label.group(1).rstrip(":").strip()
            index += 1
            continue

        # A prose paragraph is one source clause, even when line-wrapped.
        end = index
        while end + 1 < len(lines):
            following = lines[end + 1]
            following_stripped = following.strip()
            if (
                not following_stripped
                or following_stripped == "---"
                or following_stripped.startswith(("#", "```", "|"))
                or following_stripped.startswith("**Tier:")
                or following_stripped == "**What to build:**"
                or LIST_PREFIX.match(following)
                or CONTEXT_LABEL.fullmatch(following)
            ):
                break
            end += 1
        excerpt = "\n".join(lines[index : end + 1])
        units.append((line_number, end + 1, excerpt, _strip_markdown(excerpt)))
        index = end + 1

    return units


def _strip_markdown(value: str) -> str:
    value = re.sub(r"^\*\*[^*]+\*\*:\s*", "", value)
    value = value.replace("**", "")
    return value.strip()


def _requirement(
    *,
    source_id: str,
    scope: str,
    sequence: int,
    line_start: int,
    line_end: int,
    excerpt: str,
    statement: str,
    slide: int | None,
) -> dict[str, Any]:
    lower = statement.lower()
    exact_tokens = ("`", "exact", "text", "font", "#", "cm", "pt", "%", "°", "|")
    mode = "exact" if any(token in statement for token in exact_tokens) else "structural_semantic"
    structural_tokens = (
        "native",
        "placeholder",
        "layout",
        "master",
        "group",
        "field",
        "rtl",
        "hyperlink",
        "editable",
        "ooxml",
        "inherit",
    )
    visual_tokens = (
        "position",
        "size",
        "fill",
        "color",
        "spacing",
        "align",
        "crop",
        "shadow",
        "opacity",
        "overlap",
        "z-order",
        "border",
        "gradient",
    )
    structural = any(token in lower for token in structural_tokens)
    visual = any(token in lower for token in visual_tokens)
    source_of_truth = "both" if structural and visual else "ooxml" if structural else "both"
    severity = (
        "critical"
        if any(token in statement for token in ("MUST", "CRITICAL", "ONLY", "Do NOT", "NO "))
        or "native" in lower
        else "major"
    )
    prefix = "deck" if scope == "deck" else f"slide-{slide:02d}"
    result: dict[str, Any] = {
        "requirement_id": f"{prefix}.prompt-r{sequence:03d}",
        "scope": scope,
        "mandatory": True,
        "statement": statement,
        "provenance": {
            "source_id": source_id,
            "source_type": "prompt",
            "line_start": line_start,
            "line_end": line_end,
            "excerpt": excerpt,
            "excerpt_sha256": _sha256(excerpt.encode("utf-8")),
        },
        "severity": severity,
        "source_of_truth": source_of_truth,
        "matching_policy": {
            "mode": mode,
            "normalization": (
                "Exact Unicode, numeric values, units, and named OOXML construct after only "
                "prompt-declared unit conversion."
                if mode == "exact"
                else "Match every named visible and structural property; do not infer from gold."
            ),
        },
        "equivalence_policy": {
            "allowed": [
                "Alternative native OOXML serialization preserving every property named by "
                "this clause."
            ],
            "forbidden": [
                "Gold-derived expectations, raster substitutes, or omission of a property named "
                "by this clause."
            ],
        },
        "assertion": {
            "operator": "satisfies_prompt_clause",
            "expected_clause": statement,
            "automation_status": "unimplemented",
        },
        "fixture_expectations": {
            "positive_fixture_ids": [],
            "single_fault_negative_fixture_ids": [],
            "mutation_ids": [],
        },
        "review_status": "pending",
    }
    if slide is not None:
        result["slide"] = slide
    return result


def build() -> dict[str, Any]:
    deck_path = PROMPTS / "deck.md"
    slide_paths = [
        PROMPTS / "variants" / "canonical" / f"slide-{number:02d}.md" for number in range(1, 21)
    ]
    sources = [_source(deck_path, "deck-prompt")]
    sources.extend(
        _source(path, f"slide-{number:02d}-prompt") for number, path in enumerate(slide_paths, 1)
    )
    requirements: list[dict[str, Any]] = []
    for sequence, unit in enumerate(_units(deck_path, deck=True), 1):
        requirements.append(
            _requirement(
                source_id="deck-prompt",
                scope="deck",
                sequence=sequence,
                line_start=unit[0],
                line_end=unit[1],
                excerpt=unit[2],
                statement=unit[3],
                slide=None,
            )
        )
    for slide, path in enumerate(slide_paths, 1):
        for sequence, unit in enumerate(_units(path, deck=False), 1):
            requirements.append(
                _requirement(
                    source_id=f"slide-{slide:02d}-prompt",
                    scope="slide",
                    sequence=sequence,
                    line_start=unit[0],
                    line_end=unit[1],
                    excerpt=unit[2],
                    statement=unit[3],
                    slide=slide,
                )
            )
    return {
        "schema_version": "1.0",
        "oracle_id": "acidslide-prompt-requirements-v1",
        "benchmark_version": "acidslide-v1.0.0",
        "freeze_status": "candidate_pending_independent_review",
        "sources": sources,
        "independent_reviews": [],
        "requirements": requirements,
    }


def main() -> None:
    document = build()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {
        scope: sum(1 for item in document["requirements"] if item["scope"] == scope)
        for scope in ("deck", "slide")
    }
    print(f"wrote {OUTPUT}: {counts['deck']} deck + {counts['slide']} slide requirements")


if __name__ == "__main__":
    main()
