"""Tests for auditable KEV data exports."""

from copy import deepcopy
import csv
from dataclasses import replace
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kev_dashboard.analysis import analyze_catalog
from kev_dashboard.export import export_build
from kev_dashboard.fetch import load_local_json
from kev_dashboard.models import parse_catalog


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kev_sample.json"


EXPECTED_FILES = {
    "data/kev_snapshot.json",
    "data/metadata.json",
    "data/summary.json",
    "data/vulnerabilities.csv",
    "data/vendor_summary.csv",
    "data/year_summary.csv",
    "data/ransomware_summary.csv",
    "data/forensic_triage_summary.csv",
    "data/remediation_window_summary.csv",
    "data/review_signal_summary.csv",
}


class ExportTests(unittest.TestCase):
    """Verify snapshot, JSON, and CSV generation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_local_json(FIXTURE_PATH)

        cls.catalog = parse_catalog(
            cls.document.payload,
            source=cls.document.source,
        )

        cls.analysis = analyze_catalog(
            cls.catalog,
            as_of=date(2026, 9, 3),
        )

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(
            self.temporary_directory.cleanup
        )

        self.output_dir = (
            Path(self.temporary_directory.name)
            / "output"
        )

        self.written_paths = export_build(
            self.document,
            self.analysis,
            self.output_dir,
        )

    def read_csv(
        self,
        filename: str,
    ) -> list[dict[str, str]]:
        """Read one generated CSV as dictionaries."""

        path = self.output_dir / "data" / filename

        with path.open(
            encoding="utf-8",
            newline="",
        ) as csv_file:
            return list(csv.DictReader(csv_file))

    def test_export_creates_expected_files(self) -> None:
        returned_files = {
            path.relative_to(
                self.output_dir
            ).as_posix()
            for path in self.written_paths
        }

        actual_files = {
            path.relative_to(
                self.output_dir
            ).as_posix()
            for path in self.output_dir.rglob("*")
            if path.is_file()
        }

        self.assertEqual(
            returned_files,
            EXPECTED_FILES,
        )
        self.assertEqual(
            actual_files,
            EXPECTED_FILES,
        )

        temporary_files = [
            path
            for path in self.output_dir.rglob("*")
            if path.name.startswith(".")
        ]

        self.assertEqual(temporary_files, [])

    def test_snapshot_preserves_original_bytes(self) -> None:
        snapshot_path = (
            self.output_dir
            / "data"
            / "kev_snapshot.json"
        )

        self.assertEqual(
            snapshot_path.read_bytes(),
            self.document.raw_bytes,
        )

    def test_metadata_records_provenance(self) -> None:
        metadata_path = (
            self.output_dir
            / "data"
            / "metadata.json"
        )

        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        self.assertEqual(
            metadata["source"],
            self.document.source,
        )
        self.assertEqual(
            metadata["retrieved_at"],
            self.document.retrieved_at.isoformat(),
        )
        self.assertEqual(
            metadata["snapshot_sha256"],
            sha256(
                self.document.raw_bytes
            ).hexdigest(),
        )
        self.assertEqual(
            metadata["catalog_version"],
            "Testing-1.0",
        )
        self.assertEqual(
            metadata["as_of"],
            "2026-09-03",
        )
        self.assertEqual(
            metadata["record_count"],
            6,
        )

    def test_summary_excludes_vulnerability_rows(self) -> None:
        summary_path = (
            self.output_dir
            / "data"
            / "summary.json"
        )

        summary = json.loads(
            summary_path.read_text(encoding="utf-8")
        )

        self.assertNotIn(
            "vulnerabilities",
            summary,
        )
        self.assertEqual(
            summary["headline"][
                "total_vulnerabilities"
            ],
            6,
        )
        self.assertEqual(
            summary["headline"][
                "median_remediation_days"
            ],
            25.5,
        )

    def test_vulnerability_csv_has_expected_contract(
        self,
    ) -> None:
        path = (
            self.output_dir
            / "data"
            / "vulnerabilities.csv"
        )

        with path.open(
            encoding="utf-8",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            fieldnames = reader.fieldnames

        self.assertEqual(len(rows), 6)

        self.assertEqual(
            fieldnames,
            [
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
            ],
        )

        self.assertEqual(
            rows[0]["cve_id"],
            "CVE-2099-0001",
        )

    def test_summary_csvs_have_expected_counts(self) -> None:
        vendor_rows = self.read_csv(
            "vendor_summary.csv"
        )
        review_rows = self.read_csv(
            "review_signal_summary.csv"
        )

        self.assertEqual(
            vendor_rows[0],
            {
                "vendor": "Blue Meadow",
                "count": "2",
                "percent": "33.3",
            },
        )

        review_total = sum(
            int(row["count"])
            for row in review_rows
        )

        self.assertEqual(review_total, 6)

    def test_list_values_are_flattened_for_csv(self) -> None:
        rows = self.read_csv(
            "vulnerabilities.csv"
        )

        first = rows[0]

        self.assertEqual(
            first["cwes"],
            "CWE-287",
        )

        self.assertEqual(
            first["review_reasons"],
            (
                "Forensic triage indicated; "
                "Known ransomware use; "
                "Catalog due within 7 days"
            ),
        )

    def test_spreadsheet_formulas_are_neutralized(
        self,
    ) -> None:
        altered_analysis = deepcopy(self.analysis)

        altered_analysis["vulnerabilities"][0][
            "vendor"
        ] = "=2+2"

        export_build(
            self.document,
            altered_analysis,
            self.output_dir,
        )

        rows = self.read_csv(
            "vulnerabilities.csv"
        )

        row = next(
            item
            for item in rows
            if item["cve_id"] == "CVE-2099-0001"
        )

        self.assertEqual(
            row["vendor"],
            "'=2+2",
        )

    def test_source_mismatch_is_rejected(self) -> None:
        altered_analysis = deepcopy(self.analysis)

        altered_analysis["metadata"][
            "source"
        ] = "different-source.json"

        with self.assertRaisesRegex(
            ValueError,
            "source does not match",
        ):
            export_build(
                self.document,
                altered_analysis,
                self.output_dir / "mismatch",
            )

    def test_digest_mismatch_is_rejected(self) -> None:
        altered_document = replace(
            self.document,
            sha256_digest="0" * 64,
        )

        with self.assertRaisesRegex(
            ValueError,
            "digest does not match",
        ):
            export_build(
                altered_document,
                self.analysis,
                self.output_dir / "bad-digest",
            )


if __name__ == "__main__":
    unittest.main()