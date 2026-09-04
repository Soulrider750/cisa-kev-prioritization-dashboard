"""Command-line interface for building KEV dashboards."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite
from pathlib import Path

from . import __version__
from .analysis import analyze_catalog
from .export import export_build
from .fetch import (
    CatalogLoadError,
    DEFAULT_FEED_URL,
    DEFAULT_TIMEOUT_SECONDS,
    fetch_live_json,
    load_local_json,
)
from .models import (
    CatalogValidationError,
    parse_catalog,
)
from .report import render_report


@dataclass(frozen=True, slots=True)
class BuildResult:
    """Important outputs from one successful dashboard build."""

    source: str
    analysis_date: str
    record_count: int
    report_path: Path
    data_paths: tuple[Path, ...]


def _iso_date(value: str) -> date:
    """Parse a command-line date in YYYY-MM-DD format."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "date must use YYYY-MM-DD format"
        ) from error


def _positive_integer(value: str) -> int:
    """Parse an integer greater than zero."""

    try:
        parsed_value = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "value must be an integer"
        ) from error

    if parsed_value < 1:
        raise argparse.ArgumentTypeError(
            "value must be greater than zero"
        )

    return parsed_value


def _positive_float(value: str) -> float:
    """Parse a finite floating-point number greater than zero."""

    try:
        parsed_value = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "value must be a number"
        ) from error

    if (
        not isfinite(parsed_value)
        or parsed_value <= 0
    ):
        raise argparse.ArgumentTypeError(
            "value must be a finite number greater than zero"
        )

    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    """Create the project's command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="python -m kev_dashboard",
        description=(
            "Validate, analyze, and report the CISA Known "
            "Exploited Vulnerabilities catalog."
        ),
        epilog=(
            "When no source option is provided, the command "
            "downloads CISA's official JSON feed."
        ),
    )

    source_group = parser.add_mutually_exclusive_group()

    source_group.add_argument(
        "--input",
        type=Path,
        help=(
            "use a local KEV JSON file instead of "
            "downloading live data"
        ),
    )

    source_group.add_argument(
        "--source-url",
        help=(
            "approved CISA HTTPS URL to download; defaults "
            "to the official KEV JSON feed"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/latest"),
        help=(
            "directory for index.html and exported data "
            "(default: build/latest)"
        ),
    )

    parser.add_argument(
        "--as-of",
        type=_iso_date,
        metavar="YYYY-MM-DD",
        help=(
            "analysis date; defaults to the catalog's "
            "release date"
        ),
    )

    parser.add_argument(
        "--top-vendors",
        type=_positive_integer,
        default=10,
        metavar="COUNT",
        help=(
            "number of vendors displayed in the chart "
            "(default: 10)"
        ),
    )

    parser.add_argument(
        "--queue-limit",
        type=_positive_integer,
        default=20,
        metavar="COUNT",
        help=(
            "number of review-queue rows displayed in HTML "
            "(default: 20)"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "live-download timeout in seconds "
            f"(default: {DEFAULT_TIMEOUT_SECONDS:g})"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def run_build(
    arguments: argparse.Namespace,
) -> BuildResult:
    """Run the complete dashboard pipeline."""

    if arguments.input is not None:
        document = load_local_json(
            arguments.input
        )
    else:
        source_url = (
            arguments.source_url
            or DEFAULT_FEED_URL
        )

        document = fetch_live_json(
            source_url,
            timeout=arguments.timeout,
        )

    catalog = parse_catalog(
        document.payload,
        source=document.source,
    )

    analysis = analyze_catalog(
        catalog,
        as_of=arguments.as_of,
    )

    data_paths = export_build(
        document,
        analysis,
        arguments.output_dir,
    )

    report_path = render_report(
        analysis,
        arguments.output_dir / "index.html",
        top_vendors=arguments.top_vendors,
        queue_limit=arguments.queue_limit,
    )

    return BuildResult(
        source=document.source,
        analysis_date=analysis["metadata"]["as_of"],
        record_count=len(catalog.vulnerabilities),
        report_path=report_path,
        data_paths=data_paths,
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Parse arguments, run the build, and report the result."""

    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        result = run_build(arguments)
    except (
        CatalogLoadError,
        CatalogValidationError,
        OSError,
        ValueError,
    ) as error:
        parser.exit(
            2,
            f"error: {error}\n",
        )

    print(
        f"Validated {result.record_count:,} KEV records."
    )
    print(f"Source: {result.source}")
    print(
        f"Analysis date: {result.analysis_date}"
    )
    print(f"Dashboard: {result.report_path}")
    print(
        f"Data files: {len(result.data_paths)} "
        f"in {result.report_path.parent / 'data'}"
    )

    return 0