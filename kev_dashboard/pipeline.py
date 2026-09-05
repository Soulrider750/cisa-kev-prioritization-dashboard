"""Reusable dashboard build pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import build_validation
from .analysis import analyze_catalog
from .export import export_build
from .fetch import CatalogDocument
from .models import parse_catalog
from .report import render_report


@dataclass(frozen=True, slots=True)
class BuildResult:
    """Important outputs from one successful dashboard build."""

    source: str
    analysis_date: str
    record_count: int
    report_path: Path
    data_paths: tuple[Path, ...]


def build_dashboard(
    document: CatalogDocument,
    output_dir: Path,
    *,
    as_of: date | None = None,
    top_vendors: int = 10,
    queue_limit: int = 20,
) -> BuildResult:
    """Build and validate a dashboard from one loaded document."""

    catalog = parse_catalog(
        document.payload,
        source=document.source,
    )

    analysis = analyze_catalog(
        catalog,
        as_of=as_of,
    )

    data_paths = export_build(
        document,
        analysis,
        output_dir,
    )

    report_path = render_report(
        analysis,
        output_dir / "index.html",
        top_vendors=top_vendors,
        queue_limit=queue_limit,
        retrieved_at=document.retrieved_at,
    )

    build_validation.validate_build(
        output_dir
    )

    return BuildResult(
        source=document.source,
        analysis_date=analysis["metadata"]["as_of"],
        record_count=len(catalog.vulnerabilities),
        report_path=report_path,
        data_paths=data_paths,
    )
