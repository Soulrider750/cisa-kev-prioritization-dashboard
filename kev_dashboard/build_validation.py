"""Validation for generated dashboard builds."""

from __future__ import annotations

from pathlib import Path


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

    return None
