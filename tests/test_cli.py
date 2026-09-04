"""Tests for the complete command-line workflow."""

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from kev_dashboard.cli import main
from kev_dashboard.fetch import (
    DEFAULT_FEED_URL,
    load_local_json,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kev_sample.json"


class CliTests(unittest.TestCase):
    """Verify command-line parsing and complete builds."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_local_json(
            FIXTURE_PATH
        )

    def run_cli(
        self,
        arguments: list[str],
    ) -> tuple[int, str, str]:
        """Run the CLI while capturing output and exit status."""

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

    def test_local_cli_builds_complete_dashboard(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = (
                Path(temporary_directory)
                / "sample"
            )

            exit_code, stdout, stderr = self.run_cli(
                [
                    "--input",
                    str(FIXTURE_PATH),
                    "--as-of",
                    "2026-09-03",
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn(
                "Validated 6 KEV records.",
                stdout,
            )
            self.assertIn(
                "Analysis date: 2026-09-03",
                stdout,
            )
            self.assertTrue(
                (output_dir / "index.html").is_file()
            )
            self.assertTrue(
                (
                    output_dir
                    / "data"
                    / "kev_snapshot.json"
                ).is_file()
            )
            self.assertTrue(
                (
                    output_dir
                    / "data"
                    / "vulnerabilities.csv"
                ).is_file()
            )

    def test_explicit_analysis_date_is_exported(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            exit_code, _, _ = self.run_cli(
                [
                    "--input",
                    str(FIXTURE_PATH),
                    "--as-of",
                    "2026-08-20",
                    "--output-dir",
                    str(output_dir),
                ]
            )

            metadata = json.loads(
                (
                    output_dir
                    / "data"
                    / "metadata.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                metadata["as_of"],
                "2026-08-20",
            )

    def test_display_limits_reach_the_report(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            exit_code, _, _ = self.run_cli(
                [
                    "--input",
                    str(FIXTURE_PATH),
                    "--output-dir",
                    str(output_dir),
                    "--top-vendors",
                    "2",
                    "--queue-limit",
                    "3",
                ]
            )

            html = (
                output_dir / "index.html"
            ).read_text(encoding="utf-8")

            self.assertEqual(exit_code, 0)
            self.assertIn(
                "Top 2 vendors by catalog entries",
                html,
            )
            self.assertIn(
                "Displaying the first\n        3\n"
                "        of 6 records.",
                html,
            )
            self.assertNotIn(
                "CVE-2099-0006",
                html,
            )

    def test_default_mode_uses_live_fetcher(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            with patch(
                "kev_dashboard.cli.fetch_live_json",
                return_value=self.document,
            ) as mocked_fetch:
                exit_code, stdout, stderr = self.run_cli(
                    [
                        "--output-dir",
                        str(output_dir),
                        "--timeout",
                        "12.5",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn(
                "Validated 6 KEV records.",
                stdout,
            )

            mocked_fetch.assert_called_once_with(
                DEFAULT_FEED_URL,
                timeout=12.5,
            )

    def test_invalid_date_is_rejected(self) -> None:
        exit_code, _, stderr = self.run_cli(
            [
                "--input",
                str(FIXTURE_PATH),
                "--as-of",
                "09/03/2026",
            ]
        )

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "date must use YYYY-MM-DD format",
            stderr,
        )

    def test_nonpositive_values_are_rejected(
        self,
    ) -> None:
        cases = (
            ("--top-vendors", "0"),
            ("--queue-limit", "-1"),
            ("--timeout", "0"),
            ("--timeout", "nan"),
        )

        for option, value in cases:
            with self.subTest(
                option=option,
                value=value,
            ):
                exit_code, _, stderr = self.run_cli(
                    [
                        "--input",
                        str(FIXTURE_PATH),
                        option,
                        value,
                    ]
                )

                self.assertEqual(exit_code, 2)
                self.assertIn(
                    "greater than zero",
                    stderr,
                )

    def test_source_options_are_mutually_exclusive(
        self,
    ) -> None:
        exit_code, _, stderr = self.run_cli(
            [
                "--input",
                str(FIXTURE_PATH),
                "--source-url",
                DEFAULT_FEED_URL,
            ]
        )

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "not allowed with argument",
            stderr,
        )

    def test_load_failure_returns_exit_code_two(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            missing_path = (
                Path(temporary_directory)
                / "missing.json"
            )

            exit_code, _, stderr = self.run_cli(
                [
                    "--input",
                    str(missing_path),
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "could not inspect local file",
            stderr,
        )

    def test_version_flag_reports_version(self) -> None:
        exit_code, stdout, stderr = self.run_cli(
            ["--version"]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout.strip(),
            "python -m kev_dashboard 0.7.0",
        )

    def test_help_describes_the_workflow(self) -> None:
        exit_code, stdout, stderr = self.run_cli(
            ["--help"]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("--input", stdout)
        self.assertIn("--source-url", stdout)
        self.assertIn("--output-dir", stdout)
        self.assertIn("--as-of", stdout)
        self.assertIn("--top-vendors", stdout)
        self.assertIn("--queue-limit", stdout)
        self.assertIn("--timeout", stdout)


if __name__ == "__main__":
    unittest.main()