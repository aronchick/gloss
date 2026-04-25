"""AcidSlide CLI — benchmark grading tool."""

from pathlib import Path

import click
from rich.console import Console

from acidslide import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """AcidSlide benchmark grader — ECMA-376 slide generation fidelity testing."""


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
@click.option("--format", "fmt", type=click.Choice(["json", "html"]), default="json")
def grade(
    submission: Path,
    tier: str,
    benchmark_dir: Path | None,
    output: Path | None,
    fmt: str,
) -> None:
    """Grade a .pptx submission against the AcidSlide benchmark."""
    from acidslide.pipeline import run_pipeline

    result = run_pipeline(
        submission=submission,
        tier=int(tier),
        benchmark_dir=benchmark_dir,
        output_format=fmt,
    )

    if output:
        output.write_text(result.to_json())
        console.print(f"Report written to {output}")
    else:
        console.print(result.summary())


@main.command()
@click.argument("submission", type=click.Path(exists=True, path_type=Path))
def validate(submission: Path) -> None:
    """Run quarantine checks and ECMA-376 schema validation only (no grading)."""
    from acidslide.quarantine import quarantine_check
    from acidslide.schema_validate import validate_schema

    console.print(f"[bold]Validating:[/bold] {submission}")

    qresult = quarantine_check(submission)
    if not qresult.passed:
        console.print(f"[red]Quarantine FAILED:[/red] {qresult.reason}")
        raise SystemExit(1)
    console.print("[green]Quarantine passed[/green]")

    sresult = validate_schema(submission)
    status = "[green]valid[/green]" if sresult.valid else "[yellow]invalid[/yellow]"
    console.print(f"ECMA-376 schema: {status}")
    if sresult.violations:
        for v in sresult.violations[:10]:
            console.print(f"  - {v}")
        if len(sresult.violations) > 10:
            console.print(f"  ... and {len(sresult.violations) - 10} more")


@main.command()
@click.argument("submission", type=click.Path(exists=True, path_type=Path))
@click.option("--outdir", type=click.Path(path_type=Path), default=Path("./exports"))
def export(submission: Path, outdir: Path) -> None:
    """Export .pptx slides to PNG using LibreOffice headless."""
    from acidslide.export import export_slides

    outdir.mkdir(parents=True, exist_ok=True)
    slides = export_slides(submission, outdir)
    console.print(f"Exported {len(slides)} slides to {outdir}")
    for s in slides:
        console.print(f"  {s.name}")
