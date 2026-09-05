"""Validation for generated dashboard builds."""

from __future__ import annotations

from collections.abc import Mapping
import csv
from datetime import datetime
from hashlib import sha256
from html import escape
from io import StringIO
import json
from pathlib import Path
from typing import Any

from .export import VULNERABILITY_FIELDS


_REQUIRED_FILES = frozenset(
    {
        Path("index.html"),
        Path("data/kev_snapshot.json"),
        Path("data/metadata.json"),
        Path("data/summary.json"),
        Path("data/vulnerabilities.csv"),
        Path("data/vendor_summary.csv"),
        Path("data/year_summary.csv"),
        Path("data/ransomware_summary.csv"),
        Path("data/forensic_triage_summary.csv"),
        Path("data/remediation_window_summary.csv"),
        Path("data/review_signal_summary.csv"),
    }
)

_ALLOWED_ENTRIES = (
    _REQUIRED_FILES
    | frozenset({Path("data")})
)


class BuildValidationError(ValueError):
    """Raised when a generated build is unsafe to publish."""


def _read_bytes(
    path: Path,
    relative_path: Path,
) -> bytes:
    """Read one build file with a stable validation error."""

    try:
        return path.read_bytes()
    except OSError:
        raise BuildValidationError(
            "could not read build file: "
            f"{relative_path.as_posix()}"
        ) from None


def _load_json_object(
    path: Path,
    relative_path: Path,
    *,
    raw_bytes: bytes | None = None,
) -> Mapping[str, Any]:
    """Load one UTF-8 JSON object from the candidate build."""

    content = (
        raw_bytes
        if raw_bytes is not None
        else _read_bytes(path, relative_path)
    )

    try:
        value = json.loads(content)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise BuildValidationError(
            "invalid JSON file: "
            f"{relative_path.as_posix()}"
        ) from None

    if not isinstance(value, Mapping):
        raise BuildValidationError(
            "JSON file must contain an object: "
            f"{relative_path.as_posix()}"
        )

    return value


def _retrieved_at_text(
    metadata: Mapping[str, Any],
) -> str:
    """Return a validated timezone-aware retrieval timestamp."""

    value = metadata.get("retrieved_at")

    error_message = (
        "metadata retrieved_at must be a "
        "timezone-aware ISO 8601 timestamp"
    )

    if not isinstance(value, str):
        raise BuildValidationError(
            error_message
        )

    try:
        retrieved_at = datetime.fromisoformat(
            value
        )
    except ValueError:
        raise BuildValidationError(
            error_message
        ) from None

    if (
        retrieved_at.tzinfo is None
        or retrieved_at.utcoffset() is None
    ):
        raise BuildValidationError(
            error_message
        )

    return value


def _valid_record_count(
    value: object,
) -> bool:
    """Return whether a value is a nonnegative integer count."""

    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _vulnerability_csv_record_count(
    path: Path,
    relative_path: Path,
) -> int:
    """Validate the primary CSV and return its data-row count."""

    content = _read_bytes(
        path,
        relative_path,
    )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise BuildValidationError(
            "invalid UTF-8 file: "
            f"{relative_path.as_posix()}"
        ) from None

    try:
        rows = list(
            csv.reader(
                StringIO(
                    text,
                    newline="",
                ),
                strict=True,
            )
        )
    except csv.Error:
        raise BuildValidationError(
            "invalid CSV file: "
            f"{relative_path.as_posix()}"
        ) from None

    if (
        not rows
        or tuple(rows[0])
        != VULNERABILITY_FIELDS
    ):
        raise BuildValidationError(
            "vulnerability CSV header does "
            "not match export contract"
        )

    if any(
        len(row) != len(VULNERABILITY_FIELDS)
        for row in rows[1:]
    ):
        raise BuildValidationError(
            "vulnerability CSV rows do not "
            "match export contract"
        )

    return len(rows) - 1


def validate_build(
    output_dir: Path,
) -> None:
    """Validate a generated build before publication."""

    if output_dir.is_symlink():
        raise BuildValidationError(
            "build output must not contain "
            "symbolic links: ."
        )

    if not output_dir.exists():
        raise BuildValidationError(
            "build output directory does not exist"
        )

    if not output_dir.is_dir():
        raise BuildValidationError(
            "build output path must be a directory"
        )

    entries = sorted(
        output_dir.rglob("*"),
        key=lambda path: path.relative_to(
            output_dir
        ).as_posix(),
    )

    for path in entries:
        relative_path = path.relative_to(
            output_dir
        )

        if path.is_symlink():
            raise BuildValidationError(
                "build output must not contain "
                "symbolic links: "
                f"{relative_path.as_posix()}"
            )

    for relative_path in sorted(
        _REQUIRED_FILES,
        key=Path.as_posix,
    ):
        if not (
            output_dir / relative_path
        ).is_file():
            raise BuildValidationError(
                "missing required file: "
                f"{relative_path.as_posix()}"
            )

    for path in entries:
        relative_path = path.relative_to(
            output_dir
        )

        if relative_path not in _ALLOWED_ENTRIES:
            raise BuildValidationError(
                "unexpected build entry: "
                f"{relative_path.as_posix()}"
            )

    metadata_relative = Path(
        "data/metadata.json"
    )
    snapshot_relative = Path(
        "data/kev_snapshot.json"
    )
    summary_relative = Path(
        "data/summary.json"
    )
    report_relative = Path("index.html")

    metadata = _load_json_object(
        output_dir / metadata_relative,
        metadata_relative,
    )

    retrieved_at = _retrieved_at_text(
        metadata
    )

    snapshot_bytes = _read_bytes(
        output_dir / snapshot_relative,
        snapshot_relative,
    )

    actual_digest = sha256(
        snapshot_bytes
    ).hexdigest()

    if (
        metadata.get("snapshot_sha256")
        != actual_digest
    ):
        raise BuildValidationError(
            "snapshot SHA-256 does not match "
            "metadata"
        )

    snapshot = _load_json_object(
        output_dir / snapshot_relative,
        snapshot_relative,
        raw_bytes=snapshot_bytes,
    )

    summary = _load_json_object(
        output_dir / summary_relative,
        summary_relative,
    )

    summary_metadata = summary.get(
        "metadata"
    )

    shared_metadata_fields = (
        "source",
        "catalog_version",
        "date_released",
        "as_of",
    )

    if (
        not isinstance(
            summary_metadata,
            Mapping,
        )
        or any(
            metadata.get(field)
            != summary_metadata.get(field)
            for field in shared_metadata_fields
        )
    ):
        raise BuildValidationError(
            "metadata and summary do not "
            "agree"
        )

    snapshot_records = snapshot.get(
        "vulnerabilities"
    )

    summary_headline = summary.get(
        "headline"
    )

    vulnerability_csv_relative = Path(
        "data/vulnerabilities.csv"
    )

    vulnerability_csv_count = (
        _vulnerability_csv_record_count(
            (
                output_dir
                / vulnerability_csv_relative
            ),
            vulnerability_csv_relative,
        )
    )

    record_counts: tuple[object, ...] = (
        metadata.get("record_count"),
        snapshot.get("count"),
        (
            len(snapshot_records)
            if isinstance(
                snapshot_records,
                list,
            )
            else None
        ),
        (
            summary_headline.get(
                "total_vulnerabilities"
            )
            if isinstance(
                summary_headline,
                Mapping,
            )
            else None
        ),
        vulnerability_csv_count,
    )

    if (
        not all(
            _valid_record_count(value)
            for value in record_counts
        )
        or len(set(record_counts)) != 1
    ):
        raise BuildValidationError(
            "record counts do not agree "
            "across build artifacts"
        )

    report_bytes = _read_bytes(
        output_dir / report_relative,
        report_relative,
    )

    try:
        report_text = report_bytes.decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise BuildValidationError(
            "invalid UTF-8 file: index.html"
        ) from None

    if (
        not report_text.startswith(
            "<!doctype html>"
        )
        or (
            "<title>CISA KEV Prioritization "
            "Dashboard</title>"
        )
        not in report_text
        or not report_text.rstrip().endswith(
            "</html>"
        )
    ):
        raise BuildValidationError(
            "report is not a complete "
            "dashboard document"
        )

    expected_markup = (
        f'datetime="{escape(retrieved_at, quote=True)}"'
    )

    if expected_markup not in report_text:
        raise BuildValidationError(
            "report refresh timestamp does "
            "not match metadata"
        )

    return None
