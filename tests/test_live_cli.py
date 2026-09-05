"""Tests for the operational live-refresh command."""

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from io import StringIO
import json
from pathlib import Path
import tomllib
import unittest
from unittest.mock import patch

from kev_dashboard import (
    __version__,
    live_cli,
)
from kev_dashboard.fetch import (
    CatalogLoadError,
    DEFAULT_FEED_URL,
    DEFAULT_TIMEOUT_SECONDS,
)
from kev_dashboard.live_cli import (
    build_parser,
    main,
)
from kev_dashboard.live_refresh import (
    LiveRefreshBusyError,
    LiveRefreshError,
    LiveRefreshResult,
)
from kev_dashboard.build_validation import (
    BuildValidationError,
)
from kev_dashboard.models import (
    CatalogValidationError,
)
from kev_dashboard.publication import (
    PublicationError,
)


PROJECT_ROOT = (
    Path(__file__).parent.parent
)

DEPLOYMENT_ROOT = Path(
    "/srv/kev-dashboard"
)


class LiveCliTests(unittest.TestCase):
    """Verify the one-shot operational refresh command."""

    def setUp(self) -> None:
        self.now = datetime(
            2026,
            9,
            5,
            4,
            5,
            tzinfo=timezone.utc,
        )

        self.release_id = (
            "20260905T035500000000Z-"
            "73ce6d3b673fe700"
        )

        self.result = LiveRefreshResult(
            candidate_id=(
                "candidate-"
                "0123456789abcdef0123456789abcdef"
            ),
            source=DEFAULT_FEED_URL,
            analysis_date="2026-09-04",
            record_count=6,
            release_id=self.release_id,
            release_path=(
                DEPLOYMENT_ROOT
                / "releases"
                / self.release_id
            ),
            current_path=(
                DEPLOYMENT_ROOT
                / "current"
            ),
            previous_release_id=None,
        )

    def run_cli(
        self,
        arguments: list[str],
    ) -> tuple[int, str, str]:
        """Run the command while capturing output and status."""

        stdout = StringIO()
        stderr = StringIO()

        try:
            with (
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = main(arguments)
        except SystemExit as error:
            exit_code = int(error.code)

        return (
            exit_code,
            stdout.getvalue(),
            stderr.getvalue(),
        )

    def test_utc_now_is_timezone_aware_utc(
        self,
    ) -> None:
        observed_now = live_cli._utc_now()

        self.assertIs(
            observed_now.tzinfo,
            timezone.utc,
        )
        self.assertEqual(
            observed_now.utcoffset(),
            timedelta(0),
        )

    def test_help_describes_only_operational_controls(
        self,
    ) -> None:
        exit_code, stdout, stderr = self.run_cli(
            ["--help"]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")

        for option in (
            "--deployment-root",
            "--timeout",
            "--top-vendors",
            "--queue-limit",
            "--version",
        ):
            with self.subTest(option=option):
                self.assertIn(
                    option,
                    stdout,
                )

        for excluded_option in (
            "--input",
            "--source-url",
            "--output-dir",
            "--as-of",
            "--now",
            "--candidate-id",
            "--max-age",
        ):
            with self.subTest(
                option=excluded_option
            ):
                self.assertNotIn(
                    excluded_option,
                    stdout,
                )

    def test_parser_uses_fixed_safe_defaults(
        self,
    ) -> None:
        arguments = build_parser().parse_args(
            [
                "--deployment-root",
                str(DEPLOYMENT_ROOT),
            ]
        )

        self.assertEqual(
            arguments.deployment_root,
            DEPLOYMENT_ROOT,
        )
        self.assertEqual(
            arguments.timeout,
            DEFAULT_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            arguments.top_vendors,
            10,
        )
        self.assertEqual(
            arguments.queue_limit,
            20,
        )

    def test_missing_or_relative_root_is_rejected(
        self,
    ) -> None:
        cases = (
            (
                [],
                "required",
            ),
            (
                [
                    "--deployment-root",
                    "relative/deployment",
                ],
                "absolute path",
            ),
        )

        with patch(
            (
                "kev_dashboard.live_cli."
                "live_refresh.refresh_live_dashboard"
            )
        ) as mocked_refresh:
            for arguments, expected_message in cases:
                with self.subTest(
                    arguments=arguments
                ):
                    exit_code, stdout, stderr = (
                        self.run_cli(arguments)
                    )

                    self.assertEqual(
                        exit_code,
                        2,
                    )
                    self.assertEqual(
                        stdout,
                        "",
                    )
                    self.assertIn(
                        expected_message,
                        stderr,
                    )

        mocked_refresh.assert_not_called()

    def test_invalid_numeric_values_are_rejected(
        self,
    ) -> None:
        cases = (
            ("--timeout", "0"),
            ("--timeout", "nan"),
            ("--timeout", "inf"),
            ("--top-vendors", "0"),
            ("--queue-limit", "-1"),
        )

        with patch(
            (
                "kev_dashboard.live_cli."
                "live_refresh.refresh_live_dashboard"
            )
        ) as mocked_refresh:
            for option, value in cases:
                with self.subTest(
                    option=option,
                    value=value,
                ):
                    exit_code, stdout, stderr = (
                        self.run_cli(
                            [
                                "--deployment-root",
                                str(DEPLOYMENT_ROOT),
                                option,
                                value,
                            ]
                        )
                    )

                    self.assertEqual(
                        exit_code,
                        2,
                    )
                    self.assertEqual(
                        stdout,
                        "",
                    )
                    self.assertIn(
                        "greater than zero",
                        stderr,
                    )

        mocked_refresh.assert_not_called()

    def test_nonlive_controls_are_rejected(
        self,
    ) -> None:
        cases = (
            ("--input", "sample.json"),
            ("--source-url", DEFAULT_FEED_URL),
            ("--output-dir", "/tmp/output"),
            ("--as-of", "2026-09-05"),
            ("--now", "2026-09-05T04:05:00Z"),
            ("--candidate-id", "candidate-manual"),
            ("--max-age", "120"),
        )

        with patch(
            (
                "kev_dashboard.live_cli."
                "live_refresh.refresh_live_dashboard"
            )
        ) as mocked_refresh:
            for option, value in cases:
                with self.subTest(
                    option=option
                ):
                    exit_code, stdout, stderr = (
                        self.run_cli(
                            [
                                "--deployment-root",
                                str(DEPLOYMENT_ROOT),
                                option,
                                value,
                            ]
                        )
                    )

                    self.assertEqual(
                        exit_code,
                        2,
                    )
                    self.assertEqual(
                        stdout,
                        "",
                    )
                    self.assertIn(
                        "unrecognized arguments",
                        stderr,
                    )

        mocked_refresh.assert_not_called()

    def test_success_delegates_and_emits_one_json_record(
        self,
    ) -> None:
        with (
            patch(
                "kev_dashboard.live_cli._utc_now",
                return_value=self.now,
            ) as mocked_now,
            patch(
                (
                    "kev_dashboard.live_cli."
                    "live_refresh.refresh_live_dashboard"
                ),
                return_value=self.result,
            ) as mocked_refresh,
        ):
            exit_code, stdout, stderr = self.run_cli(
                [
                    "--deployment-root",
                    str(DEPLOYMENT_ROOT),
                    "--timeout",
                    "12.5",
                    "--top-vendors",
                    "2",
                    "--queue-limit",
                    "3",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")

        mocked_now.assert_called_once_with()

        mocked_refresh.assert_called_once_with(
            DEPLOYMENT_ROOT,
            now=self.now,
            timeout=12.5,
            top_vendors=2,
            queue_limit=3,
        )

        output_lines = stdout.splitlines()

        self.assertEqual(
            len(output_lines),
            1,
        )

        self.assertEqual(
            json.loads(output_lines[0]),
            {
                "analysis_date": "2026-09-04",
                "candidate_id": (
                    "candidate-"
                    "0123456789abcdef0123456789abcdef"
                ),
                "code": "refresh_succeeded",
                "current_path": str(
                    DEPLOYMENT_ROOT / "current"
                ),
                "event": "kev_dashboard.refresh",
                "previous_release_id": None,
                "record_count": 6,
                "release_id": self.release_id,
                "release_path": str(
                    DEPLOYMENT_ROOT
                    / "releases"
                    / self.release_id
                ),
                "schema_version": 1,
                "source": DEFAULT_FEED_URL,
                "status": "success",
                "timestamp": self.now.isoformat(),
            },
        )

    def test_busy_refresh_returns_temporary_failure(
        self,
    ) -> None:
        busy_error = LiveRefreshBusyError(
            "live refresh already in progress"
        )

        with (
            patch(
                "kev_dashboard.live_cli._utc_now",
                return_value=self.now,
            ) as mocked_now,
            patch(
                (
                    "kev_dashboard.live_cli."
                    "live_refresh.refresh_live_dashboard"
                ),
                side_effect=busy_error,
            ) as mocked_refresh,
        ):
            exit_code, stdout, stderr = self.run_cli(
                [
                    "--deployment-root",
                    str(DEPLOYMENT_ROOT),
                ]
            )

        self.assertEqual(exit_code, 75)
        self.assertEqual(stdout, "")

        output_lines = stderr.splitlines()

        self.assertEqual(
            len(output_lines),
            1,
        )

        self.assertEqual(
            json.loads(output_lines[0]),
            {
                "code": "refresh_busy",
                "error_type": "LiveRefreshBusyError",
                "event": "kev_dashboard.refresh",
                "message": (
                    "live refresh already in progress"
                ),
                "schema_version": 1,
                "status": "busy",
                "timestamp": self.now.isoformat(),
            },
        )

    def test_expected_operational_failures_return_one_json_record(
        self,
    ) -> None:
        refresh_errors = (
            LiveRefreshError(
                'unsafe "deployment"\nsecond line'
            ),
            CatalogLoadError(
                "catalog download failed\nsecond line"
            ),
            CatalogValidationError(
                [
                    (
                        "catalog validation failed\n"
                        "second line"
                    ),
                ]
            ),
            BuildValidationError(
                "candidate build failed\nsecond line"
            ),
            PublicationError(
                "publication failed\nsecond line"
            ),
            OSError(
                "filesystem operation failed\nsecond line"
            ),
        )

        for refresh_error in refresh_errors:
            with self.subTest(
                error_type=type(
                    refresh_error
                ).__name__,
            ):
                with (
                    patch(
                        "kev_dashboard.live_cli._utc_now",
                        return_value=self.now,
                    ) as mocked_now,
                    patch(
                        (
                            "kev_dashboard.live_cli."
                            "live_refresh."
                            "refresh_live_dashboard"
                        ),
                        side_effect=refresh_error,
                    ) as mocked_refresh,
                ):
                    (
                        exit_code,
                        stdout,
                        stderr,
                    ) = self.run_cli(
                        [
                            "--deployment-root",
                            str(DEPLOYMENT_ROOT),
                        ]
                    )

                self.assertEqual(exit_code, 1)
                self.assertEqual(stdout, "")

                mocked_now.assert_called_once_with()

                mocked_refresh.assert_called_once_with(
                    DEPLOYMENT_ROOT,
                    now=self.now,
                    timeout=(
                        DEFAULT_TIMEOUT_SECONDS
                    ),
                    top_vendors=10,
                    queue_limit=20,
                )

                output_lines = stderr.splitlines()

                self.assertEqual(
                    len(output_lines),
                    1,
                )

                self.assertEqual(
                    json.loads(output_lines[0]),
                    {
                        "code": "refresh_failed",
                        "error_type": type(
                            refresh_error
                        ).__name__,
                        "event": (
                            "kev_dashboard.refresh"
                        ),
                        "message": str(
                            refresh_error
                        ),
                        "schema_version": 1,
                        "status": "failure",
                        "timestamp": (
                            self.now.isoformat()
                        ),
                    },
                )

    def test_unexpected_failures_propagate_without_json(
        self,
    ) -> None:
        unexpected_errors = (
            RuntimeError(
                "unexpected programming failure"
            ),
            KeyboardInterrupt(),
        )

        for unexpected_error in unexpected_errors:
            with self.subTest(
                error_type=type(
                    unexpected_error
                ).__name__,
            ):
                stdout = StringIO()
                stderr = StringIO()

                with (
                    patch(
                        "kev_dashboard.live_cli._utc_now",
                        return_value=self.now,
                    ) as mocked_now,
                    patch(
                        (
                            "kev_dashboard.live_cli."
                            "live_refresh."
                            "refresh_live_dashboard"
                        ),
                        side_effect=unexpected_error,
                    ) as mocked_refresh,
                ):
                    with self.assertRaises(
                        type(unexpected_error)
                    ) as raised:
                        with (
                            redirect_stdout(stdout),
                            redirect_stderr(stderr),
                        ):
                            main(
                                [
                                    "--deployment-root",
                                    str(
                                        DEPLOYMENT_ROOT
                                    ),
                                ]
                            )

                self.assertIs(
                    raised.exception,
                    unexpected_error,
                )
                self.assertEqual(
                    stdout.getvalue(),
                    "",
                )
                self.assertEqual(
                    stderr.getvalue(),
                    "",
                )

                mocked_now.assert_called_once_with()

                mocked_refresh.assert_called_once_with(
                    DEPLOYMENT_ROOT,
                    now=self.now,
                    timeout=(
                        DEFAULT_TIMEOUT_SECONDS
                    ),
                    top_vendors=10,
                    queue_limit=20,
                )

    def test_version_reports_project_version(
        self,
    ) -> None:
        exit_code, stdout, stderr = self.run_cli(
            ["--version"]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout.strip(),
            (
                "kev-dashboard-refresh "
                f"{__version__}"
            ),
        )

    def test_console_script_metadata_is_registered(
        self,
    ) -> None:
        metadata = tomllib.loads(
            (
                PROJECT_ROOT
                / "pyproject.toml"
            ).read_text(
                encoding="utf-8"
            )
        )

        scripts = metadata[
            "project"
        ][
            "scripts"
        ]

        self.assertIn(
            "kev-dashboard-refresh",
            scripts,
        )
        self.assertEqual(
            scripts["kev-dashboard-refresh"],
            "kev_dashboard.live_cli:main",
        )


if __name__ == "__main__":
    unittest.main()
