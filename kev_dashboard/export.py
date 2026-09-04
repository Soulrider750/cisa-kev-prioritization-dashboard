"""Auditable JSON and CSV exports for KEV analysis."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import csv
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .fetch import CatalogDocument


VULNERABILITY_FIELDS = (
    "cve_id",
    "vendor",
    "product",
    "vulnerability_name",
    "date_added",
    "due_date",
    "remediation_days",
    "days_until_due",
    "ransomware_use",
    "forensic_triage",
    "due_status",
    "primary_review_signal",
    "review_reasons",
    "short_description",
    "required_action",
    "notes",
    "cwes",
)


def _atomic_write_bytes(
    path: Path,
    data: bytes,
) -> None:
    """Write bytes to a temporary file and atomically replace the target."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        temporary_path.replace(path)

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()


def _atomic_write_text(
    path: Path,
    text: str,
) -> None:
    """Encode UTF-8 text and write it atomically."""

    _atomic_write_bytes(
        path,
        text.encode("utf-8"),
    )


def _json_text(value: Any) -> str:
    """Return stable, readable JSON ending with one newline."""

    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def _safe_csv_value(value: Any) -> Any:
    """Prepare one value for safe spreadsheet-compatible CSV output."""

    if value is None:
        return ""

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, (list, tuple)):
        text = "; ".join(str(item) for item in value)
    else:
        text = str(value)

    formula_candidate = text.lstrip()

    if formula_candidate.startswith(
        ("=", "+", "-", "@")
    ):
        return "'" + text

    return text


def _csv_text(
    rows: Iterable[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> str:
    """Serialize rows into deterministic CSV text."""

    buffer = StringIO(newline="")

    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )

    writer.writeheader()

    for row in rows:
        safe_row = {
            field: _safe_csv_value(row.get(field))
            for field in fieldnames
        }

        writer.writerow(safe_row)

    return buffer.getvalue()


def _validate_export_inputs(
    document: CatalogDocument,
    analysis: Mapping[str, Any],
) -> None:
    """Confirm that source evidence and analysis belong together."""

    metadata = analysis.get("metadata")
    headline = analysis.get("headline")
    vulnerability_rows = analysis.get("vulnerabilities")

    if not isinstance(metadata, Mapping):
        raise ValueError(
            "analysis metadata must be an object"
        )

    if not isinstance(headline, Mapping):
        raise ValueError(
            "analysis headline must be an object"
        )

    if not isinstance(vulnerability_rows, list):
        raise ValueError(
            "analysis vulnerabilities must be an array"
        )

    analysis_source = metadata.get("source")

    if analysis_source != document.source:
        raise ValueError(
            "analysis source does not match document source"
        )

    actual_digest = sha256(
        document.raw_bytes
    ).hexdigest()

    if actual_digest != document.sha256_digest:
        raise ValueError(
            "document SHA-256 digest does not match raw bytes"
        )

    reported_total = headline.get(
        "total_vulnerabilities"
    )

    if reported_total != len(vulnerability_rows):
        raise ValueError(
            "analysis vulnerability total does not match "
            "the exported rows"
        )


def export_build(
    document: CatalogDocument,
    analysis: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write an auditable KEV snapshot and analysis files."""

    _validate_export_inputs(
        document,
        analysis,
    )

    data_dir = output_dir / "data"
    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshot_path = data_dir / "kev_snapshot.json"
    metadata_path = data_dir / "metadata.json"
    summary_path = data_dir / "summary.json"

    export_metadata = {
        "source": document.source,
        "retrieved_at": document.retrieved_at.isoformat(),
        "snapshot_sha256": document.sha256_digest,
        "catalog_version": analysis["metadata"][
            "catalog_version"
        ],
        "date_released": analysis["metadata"][
            "date_released"
        ],
        "as_of": analysis["metadata"]["as_of"],
        "record_count": analysis["headline"][
            "total_vulnerabilities"
        ],
    }

    summary = {
        key: value
        for key, value in analysis.items()
        if key != "vulnerabilities"
    }

    # Preserve the original input bytes rather than reformatting the JSON.
    _atomic_write_bytes(
        snapshot_path,
        document.raw_bytes,
    )

    _atomic_write_text(
        metadata_path,
        _json_text(export_metadata),
    )

    _atomic_write_text(
        summary_path,
        _json_text(summary),
    )

    csv_exports = (
        (
            data_dir / "vulnerabilities.csv",
            analysis["vulnerabilities"],
            VULNERABILITY_FIELDS,
        ),
        (
            data_dir / "vendor_summary.csv",
            analysis["vendors"],
            ("vendor", "count", "percent"),
        ),
        (
            data_dir / "year_summary.csv",
            analysis["years"],
            ("year", "count"),
        ),
        (
            data_dir / "ransomware_summary.csv",
            analysis["ransomware"],
            ("status", "count", "percent"),
        ),
        (
            data_dir / "forensic_triage_summary.csv",
            analysis["forensic_triage"],
            ("status", "count", "percent"),
        ),
        (
            data_dir / "remediation_window_summary.csv",
            analysis["remediation_buckets"],
            ("window", "count"),
        ),
        (
            data_dir / "review_signal_summary.csv",
            analysis["review_signals"],
            ("signal", "count"),
        ),
    )

    written_paths: list[Path] = [
        snapshot_path,
        metadata_path,
        summary_path,
    ]

    for path, rows, fieldnames in csv_exports:
        _atomic_write_text(
            path,
            _csv_text(rows, fieldnames),
        )

        written_paths.append(path)

    return tuple(written_paths)