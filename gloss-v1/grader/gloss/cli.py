"""Gloss CLI — native presentation challenge and checker."""

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from gloss import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Gloss — the open challenge for native AI-made presentations."""


@main.command()
@click.argument(
    "submission",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--reference",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Reference .pptx; defaults to the bundled Gloss v1 deck",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def check(submission: Path, reference: Path | None, fmt: str) -> None:
    """Report native objects changed from the public Gloss deck."""
    import zipfile

    from lxml import etree

    from gloss.compare import compare_native_decks
    from gloss.mce import MCEProfileError
    from gloss.resources import BenchmarkDataError, resolve_benchmark_dir

    try:
        resolved_reference = reference
        if resolved_reference is None:
            resolved_reference = resolve_benchmark_dir() / "deck" / "gold" / "gloss-v1-gold.pptx"
        if not resolved_reference.is_file():
            raise FileNotFoundError(f"Reference deck is missing: {resolved_reference}")
        changes = compare_native_decks(submission, resolved_reference)
    except (
        BenchmarkDataError,
        FileNotFoundError,
        MCEProfileError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
        etree.XMLSyntaxError,
    ) as exc:
        console.print(f"[red]Check could not run:[/red] {exc}")
        raise click.exceptions.Exit(2) from exc

    if fmt == "json":
        click.echo(
            json.dumps(
                {
                    "status": "exact" if not changes else "changed",
                    "changed_objects": len(changes),
                    "changes": [change.as_dict() for change in changes],
                },
                indent=2,
            )
        )
    elif not changes:
        console.print("[green]Exact match.[/green] No native objects changed.")
    else:
        noun = "object" if len(changes) == 1 else "objects"
        console.print(f"[yellow]{len(changes)} native {noun} changed:[/yellow]")
        for change in changes:
            location = "Deck" if change.slide_number == 0 else f"Slide {change.slide_number:02d}"
            fields = ", ".join(change.changed_fields)
            console.print(
                f"  [bold]{location}[/bold] · {change.label} · {change.change_type}: {fields}"
            )

    if changes:
        raise click.exceptions.Exit(1)


@main.command("build-environment-candidate")
@click.option(
    "--oci-image-digest",
    required=True,
    help="RepoDigest verified outside the network-isolated candidate container",
)
@click.option(
    "--attested-at",
    required=True,
    help="Explicit RFC 3339 UTC timestamp; never inferred from the frozen runtime clock",
)
@click.option("--canary-id", required=True, help="Stable identifier for the real canary pair")
@click.option(
    "--canary-input",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    required=True,
    help="Exact canary input bytes",
)
@click.option(
    "--canary-report",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    required=True,
    help="Exact score-semantic canary report bytes",
)
@click.option(
    "--schema-dir",
    type=click.Path(exists=True, file_okay=False, readable=True, path_type=Path),
    default=Path("/opt/gloss/schemas"),
    show_default=True,
)
@click.option(
    "--font-manifest",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=Path("/opt/gloss/benchmark/fonts/manifest.json"),
    show_default=True,
)
@click.option(
    "--dockerfile",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=Path("/opt/gloss/build/Dockerfile"),
    show_default=True,
)
@click.option(
    "--grader-lockfile",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=Path("/opt/gloss/grader/uv.lock"),
    show_default=True,
)
@click.option(
    "--grader-root",
    type=click.Path(exists=True, file_okay=False, readable=True, path_type=Path),
    default=Path("/opt/gloss/grader"),
    show_default=True,
)
def build_environment_candidate(
    oci_image_digest: str,
    attested_at: str,
    canary_id: str,
    canary_input: Path,
    canary_report: Path,
    schema_dir: Path,
    font_manifest: Path,
    dockerfile: Path,
    grader_lockfile: Path,
    grader_root: Path,
) -> None:
    """Reconstruct a non-final candidate from a network-isolated linux/amd64 image."""
    import rfc8785

    from gloss.environment import (
        EnvironmentAttestationError,
        construct_environment_attestation_candidate,
        environment_attestation_sha256,
        runtime_freeze_input,
    )

    try:
        payload, source_manifest = construct_environment_attestation_candidate(
            oci_image_digest=oci_image_digest,
            attested_at=attested_at,
            canary_id=canary_id,
            canary_input_path=canary_input,
            canary_report_path=canary_report,
            schema_dir=schema_dir,
            font_manifest_path=font_manifest,
            dockerfile_path=dockerfile,
            grader_lockfile_path=grader_lockfile,
            grader_root=grader_root,
        )
        envelope: dict[str, Any] = {
            "candidate": True,
            "environment_attestation": payload,
            "environment_attestation_sha256": environment_attestation_sha256(payload),
            "grader_source_tree_manifest": source_manifest,
            "runtime_freeze_input": runtime_freeze_input(payload),
        }
    except (OSError, ValueError, EnvironmentAttestationError) as exc:
        console.print(f"[red]Environment candidate failed:[/red] {exc}")
        raise click.exceptions.Exit(2) from exc
    click.echo(rfc8785.dumps(envelope).decode("utf-8"))


@main.command("attest-environment")
@click.option(
    "--expected-json",
    required=True,
    help="Frozen schema-valid environment attestation JSON",
)
@click.option(
    "--oci-image-digest",
    required=True,
    help="RepoDigest verified by the worker before starting this container",
)
@click.option(
    "--schema",
    "schema_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Explicit environment-attestation schema",
)
@click.option(
    "--font-manifest",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=Path("/opt/gloss/benchmark/fonts/manifest.json"),
    show_default=True,
    help="Exact font manifest installed in the grader image",
)
def attest_environment(
    expected_json: str,
    oci_image_digest: str,
    schema_path: Path | None,
    font_manifest: Path,
) -> None:
    """Reconstruct and verify the frozen attestation inside the live container."""
    import rfc8785

    from gloss.environment import (
        EnvironmentAttestationError,
        environment_attestation_sha256,
        reconstruct_environment_attestation,
    )

    try:
        expected = json.loads(expected_json)
        if not isinstance(expected, dict):
            raise EnvironmentAttestationError("Expected environment attestation must be an object")
        payload = reconstruct_environment_attestation(
            expected,
            oci_image_digest=oci_image_digest,
            schema_path=schema_path,
            font_manifest_path=font_manifest,
        )
        envelope: dict[str, Any] = {
            "environment_attestation": payload,
            "environment_attestation_sha256": environment_attestation_sha256(payload),
        }
    except (json.JSONDecodeError, OSError, EnvironmentAttestationError) as exc:
        console.print(f"[red]Environment attestation failed:[/red] {exc}")
        raise click.exceptions.Exit(2) from exc
    click.echo(rfc8785.dumps(envelope).decode("utf-8"))


@main.command()
@click.argument("submission", type=click.Path(exists=True, path_type=Path))
@click.option("--tier", type=click.Choice(["1", "2", "3"]), required=True, help="Difficulty tier")
@click.option(
    "--benchmark-dir",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to benchmark data directory",
)
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Report output")
@click.option(
    "--artifacts",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory for private visual diff artifacts",
)
@click.option(
    "--artifact-context",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    required=True,
    help="Complete caller-supplied ArtifactReportContext JSON",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "html"]),
    default="text",
    show_default=True,
    help="Report serialization for stdout or --output",
)
def grade(
    submission: Path,
    tier: str,
    benchmark_dir: Path | None,
    output: Path | None,
    artifacts: Path | None,
    artifact_context: Path,
    fmt: str,
) -> None:
    """Grade a .pptx submission against the Gloss benchmark."""
    from gloss.models import ArtifactReportContext
    from gloss.pipeline import run_pipeline
    from gloss.provenance import ReleaseProvenanceError
    from gloss.resources import BenchmarkDataError

    try:
        raw_context: Any = json.loads(artifact_context.read_text(encoding="utf-8"))
        if not isinstance(raw_context, dict):
            raise ValueError("artifact report context must be a JSON object")
        context = ArtifactReportContext.from_dict(raw_context)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise click.BadParameter(str(exc), param_hint="--artifact-context") from exc

    try:
        result = run_pipeline(
            submission=submission,
            tier=int(tier),
            benchmark_dir=benchmark_dir,
            output_format=fmt,
            artifact_dir=artifacts,
            artifact_context=context,
        )
    except (BenchmarkDataError, ReleaseProvenanceError) as exc:
        console.print(f"[red]Release provenance verification failed:[/red] {exc}")
        raise click.exceptions.Exit(2) from exc
    except ValueError as exc:
        console.print(f"[red]Artifact context verification failed:[/red] {exc}")
        raise click.exceptions.Exit(2) from exc

    if fmt == "json":
        rendered = result.to_json()
    elif fmt == "html":
        rendered = result.to_html()
    else:
        rendered = result.summary()

    if output:
        output.write_text(rendered, encoding="utf-8")
        console.print(f"Report written to {output}")
    else:
        if fmt == "text":
            console.print(rendered)
        else:
            click.echo(rendered)

    if not result.verification_complete:
        raise click.exceptions.Exit(2)


@main.command()
@click.argument("submission", type=click.Path(exists=True, path_type=Path))
def validate(submission: Path) -> None:
    """Run quarantine checks and ECMA-376 schema validation only (no grading)."""
    from gloss.quarantine import quarantine_check
    from gloss.schema_validate import validate_schema

    console.print(f"[bold]Validating:[/bold] {submission}")

    qresult = quarantine_check(submission)
    if not qresult.passed:
        console.print(f"[red]Quarantine FAILED:[/red] {qresult.reason}")
        raise SystemExit(1)
    console.print("[green]Quarantine passed[/green]")

    sresult = validate_schema(submission)
    if not sresult.performed:
        console.print("ECMA-376 schema: [red]not performed[/red]")
        for violation in sresult.violations:
            console.print(f"  - {violation}")
        raise click.exceptions.Exit(2)

    status = "[green]valid[/green]" if sresult.valid else "[yellow]invalid[/yellow]"
    console.print(f"ECMA-376 schema: {status}")
    if sresult.violations:
        for v in sresult.violations[:10]:
            console.print(f"  - {v}")
        if len(sresult.violations) > 10:
            console.print(f"  ... and {len(sresult.violations) - 10} more")
    if not sresult.valid:
        raise click.exceptions.Exit(1)


@main.command()
@click.argument("submission", type=click.Path(exists=True, path_type=Path))
@click.option("--outdir", type=click.Path(path_type=Path), default=Path("./exports"))
@click.option(
    "--pdf-output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Optional retained canonical PDF used for release reproducibility evidence",
)
def export(submission: Path, outdir: Path, pdf_output: Path | None) -> None:
    """Export .pptx slides to PNG using LibreOffice headless."""
    from gloss.export import export_slides

    outdir.mkdir(parents=True, exist_ok=True)
    slides = export_slides(submission, outdir, pdf_output=pdf_output)
    console.print(f"Exported {len(slides)} slides to {outdir}")
    for s in slides:
        console.print(f"  {s.path.name}")


@main.command("scene-graph")
@click.argument("resolved_package", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="RFC 8785 canonical deck scene-graph JSON; stdout when omitted",
)
@click.option(
    "--slides-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Optional directory for independently schema-valid per-slide JSON",
)
@click.option(
    "--profile",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Explicit scene-graph profile; defaults to the packaged v1 profile",
)
def scene_graph(
    resolved_package: Path,
    output: Path | None,
    slides_dir: Path | None,
    profile: Path | None,
) -> None:
    """Extract deterministic structural evidence from an MCE-resolved PPTX."""
    from gloss.scene_graph import (
        SceneGraphError,
        canonical_scene_graph_bytes,
        extract_normative_scene_graph,
        per_slide_scene_graphs,
    )

    try:
        graph = extract_normative_scene_graph(resolved_package, profile_path=profile)
        encoded = canonical_scene_graph_bytes(graph)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(encoded)
        if slides_dir is not None:
            slides_dir.mkdir(parents=True, exist_ok=True)
            for number, fixture in per_slide_scene_graphs(graph).items():
                (slides_dir / f"slide-{number:02d}.json").write_bytes(
                    canonical_scene_graph_bytes(fixture)
                )
    except (OSError, SceneGraphError) as exc:
        console.print(f"[red]Scene-graph extraction failed:[/red] {exc}")
        raise click.exceptions.Exit(2) from exc

    if output is None:
        click.echo(encoded.decode("utf-8"))
    else:
        console.print(f"Scene graph written to {output}")
    if slides_dir is not None:
        console.print(f"Per-slide scene graphs written to {slides_dir}")
