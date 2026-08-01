#!/usr/bin/env python3
# ruff: noqa: E501
"""Build the deterministic, non-gold Gloss v1 benchmark corpus.

This tool intentionally owns only prompts, prompt validation records, manifests,
checklist YAML, and the explicitly non-frozen scored-assertion candidate. It
never creates the gold deck, exports, evidence fixtures, baselines, approvals,
or service data.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

BENCHMARK = Path(__file__).resolve().parents[1]
PROMPTS = BENCHMARK / "prompts"


@dataclass(frozen=True)
class SlideSpec:
    tier: int
    name: str
    key_text: str
    layout: str
    primary_selector: str
    primary_count: int
    primary_kind: str
    primary_description: str
    composition_selector: str
    composition_count: int
    composition: str
    focal_region: str
    hierarchy: str
    decorative_detail: str
    asset_id: str | None = None


SPECS: dict[int, SlideSpec] = {
    1: SlideSpec(
        1,
        "Cover / Title Stress Test",
        "Gloss v1",
        "Title Slide",
        "picture",
        1,
        "image-asset",
        "one approved hero image with a 20% left crop",
        "shape",
        3,
        "three overlapping translucent rounded rectangles",
        "the right-half hero image and title lockup",
        "the specified Rectangle C, Rectangle A, hero, Rectangle B, title, subtitle z-order",
        "the hero outer shadow and rounded-rectangle transparency",
        "hero-abstract",
    ),
    2: SlideSpec(
        1,
        "Dense Agenda with Layout Semantics",
        "Agenda",
        "Content Slide",
        "group",
        1,
        "grouping",
        "one native group containing the three icon-time rows",
        "shape",
        7,
        "the agenda placeholder plus three circle/time rows",
        "the agenda body and aligned time column",
        "two bullet levels and the grouped time-column relationship",
        "bullet indents, line spacing, and paragraph spacing",
    ),
    3: SlideSpec(
        1,
        "Native Table Stress Test",
        "Performance Metrics",
        "Blank with Footer",
        "table",
        1,
        "table",
        "one native 7-by-5 OOXML table",
        "shape",
        2,
        "the native table, annotation callout, and connector",
        "the full metrics table and throughput callout",
        "header, alternating rows, conditional target colors, and mixed border weights",
        "cell padding and the 0.5cm paragraph indent",
    ),
    4: SlideSpec(
        1,
        "Native Chart Stress Test",
        "Revenue Growth",
        "Content Slide",
        "chart",
        1,
        "chart",
        "one native clustered horizontal bar chart with the supplied data",
        "shape",
        3,
        "the chart, two callouts, connectors, and takeaway block",
        "the chart plot and overlaid YoY annotations",
        "the chart-to-callout connector and overlay relationships",
        "legend, gridline, axis-label, and transparent-background styling",
    ),
    5: SlideSpec(
        1,
        "Master Reuse Enforcement",
        "Our Team",
        "Content Slide",
        "group",
        3,
        "grouping",
        "three grouped team-member cards",
        "shape",
        12,
        "three equally sized and distributed cards",
        "the three-card team composition",
        "footer, accent bar, company name, and number inherited rather than copied",
        "card border, circle, typography, and equal spacing",
    ),
    6: SlideSpec(
        2,
        "Multilingual Editorial",
        "Global Perspectives",
        "Blank with Footer",
        "shape",
        4,
        "multilingual",
        "English, Arabic RTL, and Japanese text boxes plus the overlapping callout",
        "shape",
        6,
        "three editorial columns, two separators, and one callout",
        "the three-script editorial region",
        "RTL paragraph direction, CJK line breaking, and callout overlap",
        "separator opacity and script-specific font assignment",
    ),
    7: SlideSpec(
        2,
        "Image Crop and Mask",
        "Image Handling",
        "Blank with Footer",
        "picture",
        3,
        "image-asset",
        "three approved image instances with distinct crops and masks",
        "shape",
        5,
        "three pictures, three captions, title, and PREVIEW overlay",
        "the three-image crop comparison",
        "the overlay above Image B and the picture-to-caption relationships",
        "ellipse mask, rounded mask, crops, and italic captions",
        "cityscape",
    ),
    8: SlideSpec(
        2,
        "Overlap, Shadow, and Transparency",
        "Depth & Layering",
        "Blank with Footer",
        "group",
        2,
        "grouping",
        "two selective groups containing the five cards",
        "shape",
        6,
        "five cards plus one full-width gradient strip",
        "the cascading five-card stack",
        "Card 1 through Card 5 z-order with only the requested subgrouping",
        "per-card opacity, outer shadow, and bottom gradient",
    ),
    9: SlideSpec(
        2,
        "Dense Text Overflow",
        "API Reference",
        "Content Slide",
        "shape",
        2,
        "overflow",
        "two dense monospaced text boxes with different autofit modes",
        "shape",
        4,
        "two code columns and their labels",
        "the paired fixed-size and auto-shrink columns",
        "left clipping versus right auto-shrink semantics",
        "1.15 line spacing and exact indentation",
    ),
    10: SlideSpec(
        2,
        "Connector and Alignment Diagram",
        "System Architecture",
        "Blank with Footer",
        "connector",
        7,
        "structure",
        "seven native connectors with destination arrowheads",
        "group",
        3,
        "three nested groups covering processing, persistence, and backend",
        "the centered architecture network",
        "connector attachment, routing, and three-level backend grouping",
        "dashed group borders and connector labels",
    ),
    11: SlideSpec(
        2,
        "Theme vs Local Override",
        "Brand Colors",
        "Content Slide",
        "shape",
        6,
        "theme-consistency",
        "six swatches split between theme references and explicit RGB overrides",
        "shape",
        9,
        "six swatches, six labels, and explanatory copy",
        "the two-row swatch comparison",
        "theme scheme colors in the top row versus fixed sRGB values below",
        "swatch sizing, label color, and row spacing",
    ),
    12: SlideSpec(
        2,
        "Native Field Slide",
        "Document Fields",
        "Content Slide",
        "field",
        2,
        "fields",
        "native slide-number and fixed date/time fields",
        "shape",
        6,
        "three field demonstrations, labels, and static comparison",
        "the field demonstration stack",
        "live field runs and master footer versus static comparison text",
        "field labels, comparison alignment, and footer placement",
    ),
    13: SlideSpec(
        3,
        "Composite Stress",
        "Composite Stress",
        "Blank with Footer",
        "chart",
        1,
        "chart",
        "one native six-segment pie chart",
        "table",
        1,
        "a native chart, native table, approved image, Arabic annotation, and three callouts",
        "the chart-table-image composite",
        "callouts layered over the composite without obscuring data",
        "chart labels, table borders, image crop, and annotation styling",
        "cityscape",
    ),
    14: SlideSpec(
        3,
        "RTL-Heavy Comparison",
        "RTL Systems Review",
        "Two-Column",
        "shape",
        2,
        "multilingual",
        "two long-form text columns containing Arabic, English, and bidirectional runs",
        "shape",
        4,
        "two mirrored editorial columns plus title and divider",
        "the Arabic-heavy left and English right comparison",
        "native RTL direction and correct bidirectional run order",
        "mirrored padding, divider, and script-specific typography",
    ),
    15: SlideSpec(
        3,
        "Rotated Text",
        "Rotation Atlas",
        "Blank with Footer",
        "shape",
        10,
        "structure",
        "five text boxes and five supporting shapes at the specified rotations",
        "shape",
        10,
        "five label-and-shape pairs across a shared alignment grid",
        "the five-angle rotation sequence",
        "text and supporting shapes sharing exact rotation and anchor centers",
        "rotation angles, anchor points, and line alignment",
    ),
    16: SlideSpec(
        3,
        "Intentional Off-Canvas Bleed",
        "Beyond the Frame",
        "Blank with Footer",
        "shape",
        3,
        "structure",
        "three intentional bleed objects extending past left, top, and right edges",
        "shape",
        5,
        "off-canvas circle, right-bleed rectangle, title, and two on-canvas labels",
        "the visible portions of the bleed objects",
        "intentional negative coordinates retained without hidden-content cheating",
        "edge clipping, opacity, and on-canvas label spacing",
    ),
    17: SlideSpec(
        3,
        "Deep Grouping",
        "Nested Systems",
        "Blank with Footer",
        "group",
        6,
        "grouping",
        "at least six group objects spanning three nested levels",
        "shape",
        18,
        "three hierarchy levels with 18 or more leaf shapes",
        "the centered nested-group assembly",
        "outer, middle, and inner group transforms with preserved z-order",
        "group borders, internal spacing, and label alignment",
    ),
    18: SlideSpec(
        3,
        "Multi-Column Editorial",
        "Three Cities / 三つの都市",
        "Blank with Footer",
        "picture",
        3,
        "image-asset",
        "three approved header-image instances, one per editorial column",
        "shape",
        9,
        "three columns with images, body copy, and pull quotes",
        "the magazine-style three-column spread",
        "column-local image, copy, and quote relationships",
        "the patterned center column and consistent gutters",
        "texture-pattern",
    ),
    19: SlideSpec(
        3,
        "Repetition and Consistency",
        "Design System Audit",
        "Content Slide",
        "shape",
        5,
        "theme-consistency",
        "five repeated design-system samples including two internal hyperlinks",
        "shape",
        8,
        "master-accurate samples for typography, colors, spacing, lines, and navigation",
        "the design-token audit grid",
        "internal links target Slides 1 and 5 while master elements remain inherited",
        "exact token values and equal sample spacing",
    ),
    20: SlideSpec(
        3,
        "Final Torture Slide",
        "Gloss Synthesis",
        "Blank with Footer",
        "chart",
        1,
        "chart",
        "one native line chart with three series",
        "table",
        1,
        "chart, 3-by-6 table, approved image, multilingual copy, rotation, groups, gradient, bullets, and fields",
        "the full final composite",
        "nested group, overlap stack, field, and master footer relationships",
        "image crop, 45-degree label, gradient, bullet spacing, and multilingual typography",
        "hero-abstract",
    ),
}


PARAPHRASE_A = {
    "What to build": "Required construction",
    "must contain": "is required to include",
    "must use": "is required to use",
    "MUST be": "must remain",
    "MUST come": "must originate",
    "should have": "needs",
    "Do NOT": "Never",
    "Tests ": "Evaluates ",
    "Critical requirement": "Non-negotiable requirement",
    "Explicit v1 constraints": "Mandatory v1 requirements",
    "Use the": "Select the",
    "Use only": "Rely exclusively on",
    "Use ": "Employ ",
    "Add ": "Include ",
    "Insert ": "Place ",
    "Create ": "Construct ",
    "Apply ": "Set ",
    "Keep ": "Ensure ",
    "Place ": "Position ",
    "Preserve ": "Retain ",
    "positioned": "placed",
    "containing": "that includes",
    "exactly": "precisely",
    "below": "under",
    "above": "over",
}

PARAPHRASE_B = {
    "What to build": "Acceptance-target composition",
    "must contain": "needs to contain",
    "must use": "must employ",
    "MUST be": "must be implemented as",
    "MUST come": "must be inherited",
    "should have": "is expected to have",
    "Do NOT": "Do not ever",
    "Tests ": "Measures ",
    "Critical requirement": "Required invariant",
    "Explicit v1 constraints": "Fixed v1 acceptance constraints",
    "Use the": "Adopt the",
    "Use only": "Rely exclusively on",
    "Use ": "Choose ",
    "Add ": "Provide ",
    "Insert ": "Embed ",
    "Create ": "Produce ",
    "Apply ": "Assign ",
    "Keep ": "Maintain ",
    "Place ": "Set ",
    "Preserve ": "Maintain ",
    "positioned": "located",
    "containing": "composed of",
    "exactly": "with exact precision",
    "below": "beneath",
    "above": "over",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paraphrase(text: str, replacements: dict[str, str], label: str) -> str:
    protected: list[str] = []

    def hide(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\x00PROTECTED_{len(protected) - 1}\x00"

    result = re.sub(r"```.*?```|`[^`\n]+`", hide, text, flags=re.DOTALL)
    for source, replacement in replacements.items():
        result = result.replace(source, replacement)
    result = re.sub(
        r"^# Gloss v1 — Slide (\d{2}): (.+)$",
        rf"# Gloss v1 — Slide \1: \2 ({label})",
        result,
        flags=re.MULTILINE,
    )
    if label.endswith("A"):
        result = re.sub(
            r"The natural-language requirements .*?supplementary visual guidance\.",
            "The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.",
            result,
            count=1,
        )
    else:
        result = re.sub(
            r"The natural-language requirements .*?supplementary visual guidance\.",
            "The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.",
            result,
            count=1,
        )
    for index, original in enumerate(protected):
        result = result.replace(f"\x00PROTECTED_{index}\x00", original)
    return result


def canonical_sections() -> dict[int, str]:
    brief = (PROMPTS / "DESIGNER_BRIEF.md").read_text(encoding="utf-8")
    sections: dict[int, str] = {}
    starts = list(re.finditer(r"^### SLIDE (\d+): (.+)$", brief, re.MULTILINE))
    for index, match in enumerate(starts):
        number = int(match.group(1))
        end = (
            starts[index + 1].start()
            if index + 1 < len(starts)
            else brief.find("\n## Asset Manifest", match.start())
        )
        body = brief[match.end() : end].strip()
        heading = f"# Gloss v1 — Slide {number:02d}: {match.group(2)}"
        intro = (
            "\n\nThe natural-language requirements below are the primary directive. "
            "Use the reference image only as supplementary visual guidance.\n\n"
        )
        content = heading + intro + body
        sections[number] = content.strip() + "\n"
    if set(sections) != set(range(1, 21)):
        raise RuntimeError(f"expected slide sections 1-20, found {sorted(sections)}")
    return sections


def write_prompts() -> None:
    brief = (PROMPTS / "DESIGNER_BRIEF.md").read_text(encoding="utf-8")
    deck_start = brief.index("## Critical Rules")
    deck_end = brief.index("## Slide-by-Slide Instructions")
    deck_body = brief[deck_start:deck_end].strip()
    deck_prompt = (
        "# Gloss v1 — Deck-Level Prompt\n\n"
        "This prompt is the primary deck-wide requirements contract. It is authored independently of the reference deck; "
        "reference PNGs are supplementary guidance only. Build a new `.pptx` from these instructions in the pinned LibreOffice environment.\n\n"
        + deck_body
        + "\n"
    )
    (PROMPTS / "deck.md").write_text(deck_prompt, encoding="utf-8")

    sections = canonical_sections()
    for directory in ("canonical", "paraphrase-a", "paraphrase-b"):
        (PROMPTS / "variants" / directory).mkdir(parents=True, exist_ok=True)
    validation_dir = PROMPTS / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    token_pattern = re.compile(
        r"#[0-9A-Fa-f]{6}|[A-Za-z0-9_-]+\.(?:png|pptx)|\d+(?:\.\d+)?(?:cm|pt|px|mm|%|°|×)|`[^`\n]+`|\"[^\"\n]+\"|[\u0600-\u06ff]+|[\u3040-\u30ff\u3400-\u9fff]+"
    )
    for number, canonical in sections.items():
        variant_a = paraphrase(canonical, PARAPHRASE_A, "alternative wording A")
        variant_b = paraphrase(canonical, PARAPHRASE_B, "alternative wording B")
        paths = {
            "canonical": PROMPTS / "variants" / "canonical" / f"slide-{number:02d}.md",
            "paraphrase-a": PROMPTS / "variants" / "paraphrase-a" / f"slide-{number:02d}.md",
            "paraphrase-b": PROMPTS / "variants" / "paraphrase-b" / f"slide-{number:02d}.md",
        }
        texts = {
            "canonical": canonical,
            "paraphrase-a": variant_a,
            "paraphrase-b": variant_b,
        }
        for key, path in paths.items():
            path.write_text(texts[key], encoding="utf-8")
        canonical_tokens = sorted(token_pattern.findall(canonical))
        token_parity = all(
            sorted(token_pattern.findall(text)) == canonical_tokens for text in texts.values()
        )
        canonical_blocks = re.findall(r"```.*?```", canonical, re.DOTALL)
        block_parity = all(
            re.findall(r"```.*?```", text, re.DOTALL) == canonical_blocks for text in texts.values()
        )
        parity = token_parity and block_parity
        prompt_hashes = {
            "canonical": f"sha256:{sha256(paths['canonical'])}",
            "paraphrase-a": f"sha256:{sha256(paths['paraphrase-a'])}",
            "paraphrase-b": f"sha256:{sha256(paths['paraphrase-b'])}",
        }
        metadata = {
            "schema_version": "1.0",
            "record_id": f"gloss-prompt-validation-slide-{number:02d}",
            "slide": number,
            "prompt_hashes": prompt_hashes,
            "status": "pending",
            "round_id": None,
            "authors": [],
            "pairwise_similarity_diagnostics": [],
        }
        machine_record = json.dumps(metadata, indent=2, sort_keys=True)
        record = f"""<!-- gloss-prompt-validation-v1
{machine_record}
-->
# Slide {number:02d} prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: {"pass" if parity else "fail"}
- Canonical SHA-256: `{sha256(paths["canonical"])}`
- Paraphrase A SHA-256: `{sha256(paths["paraphrase-a"])}`
- Paraphrase B SHA-256: `{sha256(paths["paraphrase-b"])}`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
"""
        if not parity:
            raise RuntimeError(f"hard-constraint drift in slide {number:02d} variants")
        record_path = validation_dir / f"slide-{number:02d}.md"
        if record_path.is_file():
            existing = record_path.read_text(encoding="utf-8")
            match = re.match(
                r"\A<!-- gloss-prompt-validation-v1\n(.*?)\n-->\n",
                existing,
                re.DOTALL,
            )
            if match:
                existing_metadata = json.loads(match.group(1))
                if existing_metadata.get("status") == "completed":
                    if existing_metadata.get("prompt_hashes") != prompt_hashes:
                        raise RuntimeError(
                            f"completed prompt-validation evidence for slide {number:02d} "
                            "was invalidated by prompt hash drift; archive and reset it explicitly"
                        )
                    continue
        record_path.write_text(record, encoding="utf-8")


def verification(method: str, selector: str = "", expectation: dict | None = None) -> dict:
    data: dict = {"method": method}
    if selector:
        data["selector"] = selector
    if expectation:
        data["expectation"] = expectation
    return data


def pending_checklist_metadata(item_id: str) -> dict:
    """Return honest candidate metadata without fabricating frozen evidence."""
    prefix, suffix = item_id.split(".", maxsplit=1)
    return {
        "assertion_id": f"{prefix}.assert-{suffix}",
        "provenance": {
            "status": "pending",
            "reason": "Independent atomic source mapping, immutable hash, locator, and provenance-kind review are not complete.",
        },
        "evidence": {
            "status": "pending",
            "reason": "Independent positive, single-fault negative, and mutation evidence has not been authored and reviewed.",
            "positive_fixture_ids": [],
            "single_fault_negative_fixture_ids": [],
            "mutation_expectation_ids": [],
        },
        "lifecycle_state": "candidate",
    }


def item(
    number: int,
    suffix: str,
    title: str,
    description: str,
    kind: str,
    severity: str,
    source: str,
    check: dict,
    failure_mode: dict | None = None,
) -> dict:
    result = {
        "schema_version": "1.0",
        "id": f"slide-{number:02d}.{suffix}",
        "scope": "slide",
        "slide": number,
        "tier": SPECS[number].tier,
        "title": title,
        "description": description,
        "kind": kind,
        "severity": severity,
        "source_of_truth": source,
        "verification": check,
    }
    if failure_mode:
        failure_mode = dict(failure_mode)
        failure_mode["affected_slides"] = {
            "status": "complete",
            "mode": "current_slide",
            "slides": [number],
            "selector_id": None,
            "selector_sha256": None,
        }
        result["failure_mode"] = failure_mode
    result.update(pending_checklist_metadata(result["id"]))
    return result


def slide_items(number: int, asset_hashes: dict[str, str]) -> list[dict]:
    spec = SPECS[number]
    primary_check = verification(
        "object_compare",
        spec.primary_selector,
        {"min_count": spec.primary_count, "required": True},
    )
    if spec.primary_kind == "image-asset":
        if spec.asset_id is None:
            raise ValueError(
                f"Slide {number} has an image-asset primary without an approved asset ID"
            )
        primary_check = verification(
            "hash_match",
            "approved_asset",
            {"asset_id": spec.asset_id, "sha256": asset_hashes[spec.asset_id]},
        )
    layout_check = verification("layout_check", "master_ref", {"required": True})
    if spec.layout in {"Title Slide", "Content Slide", "Two-Column"}:
        layout_check = verification(
            "layout_check", "placeholder", {"placeholder_type": "title", "min_count": 1}
        )
    return [
        item(
            number,
            "key-text",
            "Required key text is present",
            f"The slide must preserve the exact key text `{spec.key_text}` as editable text.",
            "text",
            "critical",
            "ooxml",
            verification("text_match", "slide_text", {"contains": spec.key_text}),
        ),
        item(
            number,
            "native-primary",
            "Primary native construct is present",
            f"The primary structural requirement is {spec.primary_description}; raster or shape imitations do not qualify.",
            spec.primary_kind,
            "critical",
            "ooxml",
            primary_check,
        ),
        item(
            number,
            "layout-binding",
            f"{spec.layout} layout binding",
            f"The slide must be bound to the `{spec.layout}` master layout and use its required inherited content.",
            "master-layout",
            "critical",
            "ooxml",
            layout_check,
        ),
        item(
            number,
            "font-policy",
            "Bundled font policy",
            "Every rendered text run must use a bundled Liberation, Carlito, Caladea, or Noto family.",
            "typography",
            "critical",
            "ooxml",
            verification("anti_cheat", "font_policy"),
            {
                "automatic_fail_if": ["non_bundled_font_used"],
                "propagation": "zero_slide",
            },
        ),
        item(
            number,
            "composition",
            "Required composition inventory",
            f"The slide composition must include {spec.composition}.",
            "structure",
            "major",
            "both",
            verification(
                "object_compare",
                spec.composition_selector,
                {"min_count": spec.composition_count},
            ),
        ),
        item(
            number,
            "full-slide-fidelity",
            "Full-slide rendered fidelity",
            "The complete 1920×1080 LibreOffice export must meet the v1 SSIM threshold against the gold export.",
            "visual",
            "major",
            "render",
            verification("visual_ssim", "full_slide", {"min_ssim": 0.9999}),
        ),
        item(
            number,
            "focal-fidelity",
            "Focal region rendered fidelity",
            f"The full-slide SSIM gate must preserve the appearance of {spec.focal_region}; this label identifies the diagnostic focal region.",
            "visual",
            "major",
            "render",
            verification(
                "visual_ssim",
                "full_slide",
                {"min_ssim": 0.9999, "diagnostic_region": spec.focal_region},
            ),
        ),
        item(
            number,
            "hierarchy-z-order",
            "Hierarchy and z-order semantics",
            f"Preserve {spec.hierarchy} in native OOXML and in the rendered result.",
            "z-order",
            "major",
            "both",
            verification(
                "object_compare",
                spec.composition_selector,
                {"min_count": spec.composition_count},
            ),
        ),
        item(
            number,
            "semantic-structure",
            "Semantic structure matches prompt",
            f"The editable object graph must express {spec.primary_description} while remaining visually equivalent to the reference.",
            spec.primary_kind,
            "major",
            "both",
            verification(
                "object_compare",
                spec.primary_selector,
                {"min_count": spec.primary_count},
            ),
        ),
        item(
            number,
            "palette",
            "Palette fidelity",
            "The rendered slide must use the exact deck palette values in the regions specified by the prompt.",
            "visual",
            "minor",
            "render",
            verification(
                "visual_ssim",
                "full_slide",
                {"min_ssim": 0.9999, "diagnostic": "palette"},
            ),
        ),
        item(
            number,
            "typography",
            "Typography fidelity",
            "Font family, size, weight, line breaking, and visible text color must match in the full-slide export.",
            "typography",
            "minor",
            "render",
            verification(
                "visual_ssim",
                "full_slide",
                {"min_ssim": 0.9999, "diagnostic": "typography"},
            ),
        ),
        item(
            number,
            "spacing",
            "Geometry and spacing fidelity",
            "Object bounds, alignment, padding, and spacing must match the specified geometry and the reference export.",
            "spacing-autofit",
            "minor",
            "both",
            verification(
                "visual_ssim",
                "full_slide",
                {"min_ssim": 0.9999, "diagnostic": "geometry"},
            ),
        ),
        item(
            number,
            "decorative-detail",
            "Decorative and effect details",
            f"Preserve {spec.decorative_detail} as editable native detail.",
            "gradient-pattern",
            "minor",
            "ooxml",
            verification(
                "object_compare",
                spec.composition_selector,
                {"min_count": spec.composition_count},
            ),
        ),
    ]


def deck_item(
    suffix: str,
    tier: int,
    title: str,
    description: str,
    kind: str,
    severity: str,
    source: str,
    check: dict,
    failure_mode: dict | None = None,
) -> dict:
    result = {
        "schema_version": "1.0",
        "id": f"deck.{suffix}",
        "scope": "deck",
        "tier": tier,
        "title": title,
        "description": description,
        "kind": kind,
        "severity": severity,
        "source_of_truth": source,
        "verification": check,
    }
    if failure_mode:
        failure_mode = dict(failure_mode)
        failure_mode.setdefault(
            "affected_slides",
            {
                "status": "pending",
                "reason": "The content-addressed deck-level affected-slide selector and evidence are not frozen.",
            },
        )
        result["failure_mode"] = failure_mode
    result.update(pending_checklist_metadata(result["id"]))
    return result


def named_affected_slides(selector_id: str) -> dict:
    """Resolve one content-addressed selector binding from the candidate registry."""
    registry_path = BENCHMARK / "requirements" / "affected-slide-selectors-v1.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    matches = [entry for entry in registry["selectors"] if entry["selector_id"] == selector_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one affected-slide selector {selector_id!r}")
    return {
        "status": "complete",
        "mode": "named_selector",
        "slides": [],
        "selector_id": selector_id,
        "selector_sha256": matches[0]["selector_sha256"],
    }


def deck_items(asset_hashes: dict[str, str]) -> list[dict]:
    return [
        deck_item(
            "slide-count",
            1,
            "Exactly 20 slides",
            "The Level 3 deck contains exactly 20 ordered slides.",
            "structure",
            "critical",
            "ooxml",
            verification("object_compare", "slide_count", {"exact_count": 20}),
        ),
        deck_item(
            "master-present",
            1,
            "Gloss master exists",
            "At least one native slide master must own the shared background and footer elements.",
            "master-layout",
            "critical",
            "ooxml",
            verification("layout_check", "master_count", {"min_count": 1}),
        ),
        deck_item(
            "font-policy",
            1,
            "Only bundled fonts render",
            "All rendered text uses the bundled font inventory.",
            "typography",
            "critical",
            "ooxml",
            verification("anti_cheat", "font_policy"),
            {
                "automatic_fail_if": ["non_bundled_font_used"],
                "propagation": "zero_affected_slides",
                "affected_slides": named_affected_slides(
                    "gloss.affected-slides.non-bundled-font.v1"
                ),
            },
        ),
        deck_item(
            "no-notes",
            1,
            "No notes or comments",
            "The package contains no speaker notes or comments.",
            "structure",
            "critical",
            "ooxml",
            verification("anti_cheat", "no_notes"),
            {
                "automatic_fail_if": ["notes_or_comments_present"],
                "propagation": "zero_affected_slides",
                "affected_slides": named_affected_slides(
                    "gloss.affected-slides.notes-comments.v1"
                ),
            },
        ),
        deck_item(
            "layouts-defined",
            1,
            "Four canonical layouts",
            "Title Slide, Content Slide, Two-Column, and Blank with Footer layouts are defined.",
            "master-layout",
            "major",
            "ooxml",
            verification("layout_check", "layout_count", {"min_count": 4}),
        ),
        deck_item(
            "approved-assets",
            1,
            "Approved media inventory",
            "Every required benchmark asset hash occurs in embedded media and no unapproved external media is introduced.",
            "image-asset",
            "major",
            "ooxml",
            verification("hash_match", "asset_manifest", {"asset_hashes": asset_hashes}),
        ),
        deck_item(
            "native-slide-numbers",
            1,
            "Slide numbers are inherited fields",
            "Slide numbers originate in the master/layout field rather than copied local text.",
            "fields",
            "major",
            "ooxml",
            verification("layout_check", "master_count", {"min_count": 1}),
        ),
        deck_item(
            "ordered-tier-prefix",
            1,
            "Tier slide order is stable",
            "Level 1 and Level 2 remain ordered prefixes of the 20-slide Level 3 deck.",
            "structure",
            "major",
            "ooxml",
            verification("object_compare", "slide_count", {"exact_count": 20}),
        ),
        deck_item(
            "theme-structure",
            2,
            "Theme references remain semantic",
            "Theme-driven colors and local overrides remain distinct in OOXML across the deck.",
            "theme-consistency",
            "major",
            "ooxml",
            verification("layout_check", "master_count", {"min_count": 1}),
        ),
        deck_item(
            "native-object-coverage",
            2,
            "Native construct coverage",
            "The deck contains native charts, tables, fields, connectors, groups, placeholders, and pictures where prompted.",
            "structure",
            "major",
            "ooxml",
            verification("object_compare", "slide_count", {"exact_count": 20}),
        ),
        deck_item(
            "rtl-cjk-coverage",
            2,
            "RTL and CJK coverage",
            "Arabic RTL and Japanese CJK content remain editable and correctly encoded.",
            "multilingual",
            "major",
            "ooxml",
            verification("object_compare", "slide_count", {"exact_count": 20}),
        ),
        deck_item(
            "render-consistency",
            1,
            "Deck-wide render consistency",
            "All slide exports pass the official SSIM threshold against their corresponding gold exports.",
            "visual",
            "major",
            "render",
            verification("visual_ssim", "all_slides", {"min_ssim": 0.9999}),
        ),
        deck_item(
            "master-visual-consistency",
            1,
            "Inherited footer renders consistently",
            "The shared footer line, company label, and slide number align identically across applicable slides.",
            "theme-consistency",
            "major",
            "render",
            verification(
                "visual_ssim",
                "all_slides",
                {"min_ssim": 0.9999, "diagnostic": "footer"},
            ),
        ),
        deck_item(
            "palette-consistency",
            1,
            "Deck palette is coherent",
            "Repeated palette roles render consistently across all 20 slides.",
            "theme-consistency",
            "major",
            "render",
            verification(
                "visual_ssim",
                "all_slides",
                {"min_ssim": 0.9999, "diagnostic": "palette"},
            ),
        ),
        deck_item(
            "typography-consistency",
            1,
            "Deck typography is coherent",
            "Repeated type roles render with the same family, size, weight, and color throughout the deck.",
            "typography",
            "major",
            "render",
            verification(
                "visual_ssim",
                "all_slides",
                {"min_ssim": 0.9999, "diagnostic": "typography"},
            ),
        ),
        deck_item(
            "spacing-consistency",
            2,
            "Deck spacing is coherent",
            "Repeated margins, gutters, and title anchors align across slide layouts.",
            "spacing-autofit",
            "major",
            "render",
            verification(
                "visual_ssim",
                "all_slides",
                {"min_ssim": 0.9999, "diagnostic": "spacing"},
            ),
        ),
        deck_item(
            "cross-slide-hierarchy",
            3,
            "Cross-slide hierarchy matches",
            "Title, body, focal, and footer hierarchy remains structurally and visually consistent.",
            "theme-consistency",
            "minor",
            "both",
            verification("layout_check", "master_count", {"min_count": 1}),
        ),
        deck_item(
            "line-weight-detail",
            3,
            "Repeated line weights match",
            "Master rules, separators, borders, and connectors use the specified weights.",
            "visual",
            "minor",
            "both",
            verification(
                "visual_ssim",
                "all_slides",
                {"min_ssim": 0.9999, "diagnostic": "line_weights"},
            ),
        ),
        deck_item(
            "effect-detail",
            3,
            "Repeated effects match",
            "Shadows, transparency, gradients, and patterns render consistently where repeated.",
            "gradient-pattern",
            "minor",
            "both",
            verification(
                "visual_ssim",
                "all_slides",
                {"min_ssim": 0.9999, "diagnostic": "effects"},
            ),
        ),
        deck_item(
            "alignment-detail",
            3,
            "Repeated alignment anchors match",
            "Common title, footer, and grid anchors remain aligned throughout the deck.",
            "spacing-autofit",
            "minor",
            "both",
            verification(
                "visual_ssim",
                "all_slides",
                {"min_ssim": 0.9999, "diagnostic": "alignment"},
            ),
        ),
    ]


def write_yaml_documents(path: Path, documents: list[dict]) -> None:
    path.write_text(
        "\n---\n".join(json.dumps(doc, ensure_ascii=False, indent=2) for doc in documents) + "\n",
        encoding="utf-8",
    )


def write_checklist(asset_hashes: dict[str, str]) -> list[dict]:
    documents = deck_items(asset_hashes)
    write_yaml_documents(BENCHMARK / "checklist" / "deck.yaml", documents)
    slides_dir = BENCHMARK / "checklist" / "slides"
    for number in range(1, 21):
        slide_documents = slide_items(number, asset_hashes)
        write_yaml_documents(slides_dir / f"slide-{number:02d}.yaml", slide_documents)
        documents.extend(slide_documents)
    return documents


def _assertion_property_class(item: dict) -> str:
    kind = item["kind"]
    if kind == "master-layout":
        return "master" if "master" in item["id"] else "layout"
    return {
        "structure": "native_structure",
        "typography": "visual_typography",
        "image-asset": "asset_identity",
        "fields": "field",
        "theme-consistency": "theme",
        "multilingual": "text_content",
        "visual": "visual_appearance",
        "spacing-autofit": "visual_spacing",
        "gradient-pattern": "visual_color",
        "text": "text_content",
        "z-order": "native_structure",
        "grouping": "native_structure",
        "table": "table",
        "chart": "chart",
        "overflow": "editability",
    }[kind]


def write_scored_assertion_candidate(documents: list[dict]) -> None:
    """Write reviewable candidate assertions without inventing provenance or evidence."""

    pending_provenance = (
        "Atomic prompt/reference/asset provenance has not yet been independently reviewed."
    )
    pending_evidence = (
        "Positive, single-fault negative, and mutation evidence has not yet been observed."
    )
    assertions: list[dict] = []
    for item_document in documents:
        verification = item_document["verification"]
        expected = dict(verification.get("expectation", {}))
        if selector := verification.get("selector"):
            expected["selector"] = selector
        if not expected:
            expected["rule"] = item_document["id"]
        method = verification["method"]
        if method == "hash_match":
            method = "embedded_media_hash"
        assertions.append(
            {
                "schema_version": "1.0",
                "lifecycle_state": "candidate",
                "assertion_id": item_document["assertion_id"],
                "checklist_item_id": item_document["id"],
                "scope": item_document["scope"],
                **({"slide": item_document["slide"]} if item_document["scope"] == "slide" else {}),
                "tier": item_document["tier"],
                "statement": item_document["description"],
                "provenance": {"status": "pending", "reason": pending_provenance},
                "property_class": _assertion_property_class(item_document),
                "source_of_truth": item_document["source_of_truth"],
                "verification_method": method,
                "expected_observation": expected,
                "evidence": {"status": "pending", "reason": pending_evidence},
                "gold_ooxml_is_oracle": False,
            }
        )
    inventory = {
        "schema_version": "1.0",
        "inventory_id": "gloss-scored-assertion-inventory-v1",
        "lifecycle_state": "candidate",
        "benchmark_version": "gloss-v1.0.0",
        "prompt_bundle_sha256": "pending",
        "reference_image_bundle_sha256": "pending",
        "asset_manifest_sha256": f"sha256:{sha256(BENCHMARK / 'assets' / 'manifest.json')}",
        "review": {
            "status": "pending",
            "reason": "Assertion provenance and fixture evidence are not independently approved.",
        },
        "assertions": assertions,
    }
    destination = BENCHMARK / "requirements" / "scored-assertion-inventory.json"
    destination.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")


PACKAGES = {
    "Liberation": {
        "package": "fonts-liberation",
        "version": "1:1.07.4-11",
        "license": "GPL-2.0-with-font-exception",
        "source_url": "https://archive.ubuntu.com/ubuntu/pool/main/f/fonts-liberation/fonts-liberation_1.07.4-11_all.deb",
        "package_sha256": "d359cba9c3ac8a40fb57773881e20827845e9fab1b2d6fd25cde4b7bade7d57f",
        "license_file": "licenses/fonts-liberation-1.07.4-11.txt",
    },
    "Carlito": {
        "package": "fonts-crosextra-carlito",
        "version": "20130920-1.1",
        "license": "OFL-1.1",
        "source_url": "https://archive.ubuntu.com/ubuntu/pool/universe/f/fonts-crosextra-carlito/fonts-crosextra-carlito_20130920-1.1_all.deb",
        "package_sha256": "7385475cde807e1363c3361976576571870373032466c7f525d5900852b6f420",
        "license_file": "licenses/fonts-crosextra-carlito-20130920-1.1.txt",
    },
    "Caladea": {
        "package": "fonts-crosextra-caladea",
        "version": "20130214-2.1",
        "license": "Apache-2.0",
        "source_url": "https://archive.ubuntu.com/ubuntu/pool/universe/f/fonts-crosextra-caladea/fonts-crosextra-caladea_20130214-2.1_all.deb",
        "package_sha256": "1330d25dfa5bab2e9b712b4950d2855cdb63a2b2b9451e2ffb93618c77e1f242",
        "license_file": "licenses/fonts-crosextra-caladea-20130214-2.1.txt",
    },
    "Noto Sans CJK": {
        "package": "fonts-noto-cjk",
        "version": "1:20220127+repack1-1",
        "license": "OFL-1.1",
        "source_url": "https://archive.ubuntu.com/ubuntu/pool/main/f/fonts-noto-cjk/fonts-noto-cjk_20220127+repack1-1_all.deb",
        "package_sha256": "e804b3474a79bd70d5f03f590e2d06dbc5ce17f48be7cfaf6c48086471edd5be",
        "license_file": "licenses/fonts-noto-cjk-20220127+repack1-1.txt",
    },
    "Noto Sans": {
        "package": "fonts-noto-core",
        "version": "20201225-1build1",
        "license": "OFL-1.1",
        "source_url": "https://archive.ubuntu.com/ubuntu/pool/main/f/fonts-noto/fonts-noto-core_20201225-1build1_all.deb",
        "package_sha256": "653d237d5c4e8fcebb2710129ebbd7bf9bc248d03dfff23fcf261b0372fded69",
        "license_file": "licenses/fonts-noto-core-20201225-1build1.txt",
    },
}


def font_family(filename: str) -> str:
    if filename.startswith("Liberation"):
        return filename.split("-")[0].replace("Liberation", "Liberation ")
    if filename.startswith("NotoSansCJK"):
        return "Noto Sans CJK JP"
    if filename.startswith("NotoSansArabic"):
        return "Noto Sans Arabic"
    if filename.startswith("NotoSans"):
        return "Noto Sans"
    return filename.split("-")[0]


def package_for(filename: str) -> str:
    if filename.startswith("Liberation"):
        return "Liberation"
    if filename.startswith("Carlito"):
        return "Carlito"
    if filename.startswith("Caladea"):
        return "Caladea"
    if filename.startswith("NotoSansCJK"):
        return "Noto Sans CJK"
    return "Noto Sans"


def write_manifests() -> dict[str, str]:
    assets = [
        ("hero-abstract", "hero-abstract.png", ["slide-01", "slide-20"], [1920, 1080]),
        (
            "cityscape",
            "cityscape.png",
            ["slide-07", "slide-13", "slide-18"],
            [2400, 1600],
        ),
        (
            "texture-pattern",
            "texture-pattern.png",
            ["slide-07", "slide-18"],
            [800, 800],
        ),
    ]
    entries = []
    asset_hashes = {}
    for asset_id, filename, usage, dimensions in assets:
        local = BENCHMARK / "assets" / "mirrored" / filename
        source = BENCHMARK / "assets" / "sources" / filename.replace(".png", ".svg")
        digest = sha256(local)
        asset_hashes[asset_id] = digest
        entries.append(
            {
                "asset_id": asset_id,
                "filename": filename,
                "media_type": "image/png",
                "dimensions_px": dimensions,
                "source_url": None,
                "source_path": f"sources/{source.name}",
                "source_sha256": sha256(source),
                "local_path": f"mirrored/{filename}",
                "sha256": digest,
                "accepted_recompression_hashes": [],
                "recompression_status": "pending_gold_deck_extraction",
                "usage": usage,
                "license": "CC0-1.0",
                "license_file": "LICENSE",
                "attribution": "Gloss benchmark maintainers",
                "provenance": "hand-authored procedural SVG rendered locally with librsvg; no third-party or model-generated content",
            }
        )
    asset_manifest = {
        "schema_version": "1.0",
        "policy": "allowlist-only",
        "assets": entries,
    }
    (BENCHMARK / "assets" / "manifest.json").write_text(
        json.dumps(asset_manifest, indent=2) + "\n", encoding="utf-8"
    )

    files = []
    for path in sorted((BENCHMARK / "fonts" / "files").iterdir()):
        if path.suffix.lower() not in {".ttf", ".ttc", ".otf"}:
            continue
        package_key = package_for(path.name)
        package = PACKAGES[package_key]
        style = path.stem.split("-", 1)[1] if "-" in path.stem else "Regular"
        files.append(
            {
                "family": font_family(path.name),
                "style": style,
                "local_path": f"files/{path.name}",
                "sha256": sha256(path),
                "package": package["package"],
                "package_version": package["version"],
                "license": package["license"],
                "license_file": package["license_file"],
            }
        )
    font_manifest = {
        "schema_version": "1.0",
        "runtime": "Ubuntu 22.04 (jammy)",
        "policy": "only listed font files may be used in rendered text",
        "packages": list(PACKAGES.values()),
        "files": files,
    }
    (BENCHMARK / "fonts" / "manifest.json").write_text(
        json.dumps(font_manifest, indent=2) + "\n", encoding="utf-8"
    )
    return asset_hashes


def main() -> None:
    asset_hashes = write_manifests()
    write_prompts()
    documents = write_checklist(asset_hashes)
    write_scored_assertion_candidate(documents)
    print(
        "built prompts, validation records, manifests, 280 checklist items, "
        "and candidate scored assertions"
    )


if __name__ == "__main__":
    main()
