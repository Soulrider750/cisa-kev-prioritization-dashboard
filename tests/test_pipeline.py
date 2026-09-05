"""Tests for the reusable dashboard build pipeline."""

from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kev_dashboard.build_validation import (
    validate_build,
)
from kev_dashboard.fetch import load_local_json
from kev_dashboard.pipeline import build_dashboard


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "kev_sample.json"
)


class PipelineTests(unittest.TestCase):
    """Verify document-to-dashboard build behavior."""

    def test_build_dashboard_creates_valid_candidate(
        self,
    ) -> None:
        document = replace(
            load_local_json(FIXTURE_PATH),
            retrieved_at=datetime(
                2026,
                9,
                5,
                3,
                36,
                25,
                tzinfo=timezone.utc,
            ),
        )

        with TemporaryDirectory() as temporary_directory:
            output_dir = (
                Path(temporary_directory)
                / "candidate"
            )

            result = build_dashboard(
                document,
                output_dir,
                as_of=date(2026, 9, 3),
                top_vendors=2,
                queue_limit=3,
            )

            self.assertEqual(
                result.source,
                document.source,
            )
            self.assertEqual(
                result.analysis_date,
                "2026-09-03",
            )
            self.assertEqual(
                result.record_count,
                6,
            )
            self.assertEqual(
                result.report_path,
                output_dir / "index.html",
            )
            self.assertTrue(
                result.report_path.is_file()
            )
            self.assertEqual(
                len(result.data_paths),
                10,
            )
            self.assertIsNone(
                validate_build(output_dir)
            )

            report_text = (
                result.report_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "Top 2 vendors by catalog entries",
                report_text,
            )
            self.assertIn(
                (
                    "Displaying the first\n"
                    "        3\n"
                    "        of 6 records."
                ),
                report_text,
            )


if __name__ == "__main__":
    unittest.main()
