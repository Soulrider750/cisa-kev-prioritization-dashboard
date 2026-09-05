"""Operational command for one live dashboard refresh."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
import sys

from . import __version__
from . import live_refresh
from .fetch import DEFAULT_TIMEOUT_SECONDS


LIVE_REFRESH_BUSY_EXIT_CODE = 75


def _emit_json_record(
    record: dict[str, object],
    *,
    error: bool = False,
) -> None:
    """Emit one compact JSON record to the selected stream."""

    stream = (
        sys.stderr
        if error
        else sys.stdout
    )

    print(
        json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
        ),
        file=stream,
    )


def _absolute_path(
    value: str,
) -> Path:
    """Parse an absolute path without resolving symbolic links."""

    parsed_path = Path(value)

    if not parsed_path.is_absolute():
        raise argparse.ArgumentTypeError(
            "deployment root must be an absolute path"
        )

    return parsed_path


def _positive_integer(
    value: str,
) -> int:
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


def _positive_float(
    value: str,
) -> float:
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


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(
        timezone.utc
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the operational refresh argument parser."""

    parser = argparse.ArgumentParser(
        prog="kev-dashboard-refresh",
        description=(
            "Fetch the official CISA KEV catalog and "
            "atomically publish one live dashboard release."
        ),
    )

    parser.add_argument(
        "--deployment-root",
        required=True,
        type=_absolute_path,
        metavar="ABSOLUTE_PATH",
        help=(
            "trusted deployment directory containing "
            "candidates, releases, and current"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "official-feed download timeout in seconds "
            f"(default: {DEFAULT_TIMEOUT_SECONDS:g})"
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
            "number of review-queue rows displayed "
            "(default: 20)"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run one live refresh and report structured evidence."""

    parser = build_parser()
    arguments = parser.parse_args(argv)

    now = _utc_now()

    try:
        result = (
            live_refresh.refresh_live_dashboard(
                arguments.deployment_root,
                now=now,
                timeout=arguments.timeout,
                top_vendors=arguments.top_vendors,
                queue_limit=arguments.queue_limit,
            )
        )
    except live_refresh.LiveRefreshBusyError as error:
        _emit_json_record(
            {
                "code": "refresh_busy",
                "error_type": type(error).__name__,
                "event": "kev_dashboard.refresh",
                "message": str(error),
                "schema_version": 1,
                "status": "busy",
                "timestamp": now.isoformat(),
            },
            error=True,
        )

        return LIVE_REFRESH_BUSY_EXIT_CODE
    except (
        OSError,
        ValueError,
    ) as error:
        _emit_json_record(
            {
                "code": "refresh_failed",
                "error_type": type(error).__name__,
                "event": "kev_dashboard.refresh",
                "message": str(error),
                "schema_version": 1,
                "status": "failure",
                "timestamp": now.isoformat(),
            },
            error=True,
        )

        return 1

    _emit_json_record(
        {
            "analysis_date": result.analysis_date,
            "candidate_id": result.candidate_id,
            "code": "refresh_succeeded",
            "current_path": str(
                result.current_path
            ),
            "event": "kev_dashboard.refresh",
            "previous_release_id": (
                result.previous_release_id
            ),
            "record_count": result.record_count,
            "release_id": result.release_id,
            "release_path": str(
                result.release_path
            ),
            "schema_version": 1,
            "source": result.source,
            "status": "success",
            "timestamp": now.isoformat(),
        },
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
