"""Tests for generated dashboard build validation."""

from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kev_dashboard.analysis import analyze_catalog
from kev_dashboard.build_validation import (
    BuildValidationError,
    validate_build,
)
from kev_dashboard.export import export_build
from kev_dashboard.fetch import load_local_json
from kev_dashboard.models import parse_catalog
from kev_dashboard.report import render_report


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "kev_sample.json"
)


class BuildValidationTests(unittest.TestCase):
    """Verify the boundary of a publishable build."""

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()

        self.addCleanup(
            self.temporary_directory.cleanup
        )

        self.output_dir = (
            Path(self.temporary_directory.name)
            / "candidate"
        )

        loaded_document = load_local_json(
            FIXTURE_PATH
        )

        self.document = replace(
            loaded_document,
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

        catalog = parse_catalog(
            self.document.payload,
            source=self.document.source,
        )

        self.analysis = analyze_catalog(
            catalog,
            as_of=date(2026, 9, 3),
        )

        export_build(
            self.document,
            self.analysis,
            self.output_dir,
        )

        render_report(
            self.analysis,
            self.output_dir / "index.html",
            retrieved_at=self.document.retrieved_at,
        )

    def test_complete_generated_build_is_accepted(
        self,
    ) -> None:
        self.assertIsNone(
            validate_build(self.output_dir)
        )

    def test_output_directory_must_exist(
        self,
    ) -> None:
        missing_directory = (
            self.output_dir.parent
            / "missing"
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            "build output directory does not exist",
        ):
            validate_build(missing_directory)

    def test_missing_required_file_is_rejected(
        self,
    ) -> None:
        metadata_path = (
            self.output_dir
            / "data"
            / "metadata.json"
        )

        metadata_path.unlink()

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "missing required file: "
                r"data/metadata\.json"
            ),
        ):
            validate_build(self.output_dir)

    def test_unexpected_file_is_rejected(
        self,
    ) -> None:
        unexpected_path = (
            self.output_dir
            / "data"
            / "stale.txt"
        )

        unexpected_path.write_text(
            "test-only stale output\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "unexpected build entry: "
                r"data/stale\.txt"
            ),
        ):
            validate_build(self.output_dir)

    def test_symbolic_link_is_rejected(
        self,
    ) -> None:
        metadata_path = (
            self.output_dir
            / "data"
            / "metadata.json"
        )

        metadata_path.unlink()

        metadata_path.symlink_to(
            self.output_dir
            / "data"
            / "summary.json"
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "build output must not contain "
                "symbolic links: "
                r"data/metadata\.json"
            ),
        ):
            validate_build(self.output_dir)

    def test_invalid_metadata_json_is_rejected(
        self,
    ) -> None:
        metadata_path = (
            self.output_dir
            / "data"
            / "metadata.json"
        )

        metadata_path.write_text(
            "{invalid JSON\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "invalid JSON file: "
                r"data/metadata\.json"
            ),
        ):
            validate_build(self.output_dir)

    def test_naive_retrieval_timestamp_is_rejected(
        self,
    ) -> None:
        metadata_path = (
            self.output_dir
            / "data"
            / "metadata.json"
        )

        metadata = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )

        metadata["retrieved_at"] = (
            "2026-09-05T03:36:25"
        )

        metadata_path.write_text(
            json.dumps(
                metadata,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "metadata retrieved_at must be a "
                "timezone-aware ISO 8601 timestamp"
            ),
        ):
            validate_build(self.output_dir)

    def test_snapshot_digest_mismatch_is_rejected(
        self,
    ) -> None:
        snapshot_path = (
            self.output_dir
            / "data"
            / "kev_snapshot.json"
        )

        snapshot_path.write_bytes(
            snapshot_path.read_bytes()
            + b"\n"
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "snapshot SHA-256 does not match "
                "metadata"
            ),
        ):
            validate_build(self.output_dir)

    def test_record_count_mismatch_is_rejected(
        self,
    ) -> None:
        metadata_path = (
            self.output_dir
            / "data"
            / "metadata.json"
        )

        metadata = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )

        metadata["record_count"] += 1

        metadata_path.write_text(
            json.dumps(
                metadata,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "record counts do not agree "
                "across build artifacts"
            ),
        ):
            validate_build(self.output_dir)

    def test_report_refresh_timestamp_must_match_metadata(
        self,
    ) -> None:
        report_path = (
            self.output_dir
            / "index.html"
        )

        expected_timestamp = (
            self.document.retrieved_at.isoformat()
        )

        report_text = report_path.read_text(
            encoding="utf-8"
        )

        original_markup = (
            f'datetime="{expected_timestamp}"'
        )

        altered_markup = (
            'datetime="2026-09-05T03:36:26+00:00"'
        )

        self.assertIn(
            original_markup,
            report_text,
        )

        report_path.write_text(
            report_text.replace(
                original_markup,
                altered_markup,
                1,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            BuildValidationError,
            (
                "report refresh timestamp does "
                "not match metadata"
            ),
        ):
            validate_build(self.output_dir)


if __name__ == "__main__":
    unittest.main()
