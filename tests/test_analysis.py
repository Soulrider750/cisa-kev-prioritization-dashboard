"""Tests for deterministic KEV analysis."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import unittest

from kev_dashboard.analysis import analyze_catalog
from kev_dashboard.models import parse_catalog


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kev_sample.json"


class AnalysisTests(unittest.TestCase):
    """Verify metrics, grouping, and review ordering."""

    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
            cls.original_payload = json.load(fixture_file)

        cls.catalog = parse_catalog(
            deepcopy(cls.original_payload),
            source="kev_sample.json",
        )

    def setUp(self) -> None:
        self.analysis = analyze_catalog(
            self.catalog,
            as_of=date(2026, 9, 3),
        )

    def test_default_date_uses_catalog_release_date(self) -> None:
        analysis = analyze_catalog(self.catalog)

        self.assertEqual(
            analysis["metadata"]["as_of"],
            "2026-09-03",
        )

    def test_headline_metrics_are_correct(self) -> None:
        headline = self.analysis["headline"]

        self.assertEqual(
            headline["total_vulnerabilities"],
            6,
        )
        self.assertEqual(
            headline["unique_vendors"],
            4,
        )
        self.assertEqual(
            headline["known_ransomware"],
            2,
        )
        self.assertEqual(
            headline["known_ransomware_percent"],
            33.3,
        )
        self.assertEqual(
            headline["forensic_triage"],
            2,
        )
        self.assertEqual(
            headline["forensic_triage_percent"],
            33.3,
        )
        self.assertEqual(
            headline["median_remediation_days"],
            25.5,
        )

    def test_vendor_counts_are_sorted(self) -> None:
        vendor_counts = [
            (row["vendor"], row["count"])
            for row in self.analysis["vendors"]
        ]

        self.assertEqual(
            vendor_counts,
            [
                ("Blue Meadow", 2),
                ("Northstar Software", 2),
                ("Cedar Systems", 1),
                ("Harbor Tech", 1),
            ],
        )

    def test_year_counts_are_chronological(self) -> None:
        year_counts = [
            (row["year"], row["count"])
            for row in self.analysis["years"]
        ]

        self.assertEqual(
            year_counts,
            [
                (2023, 1),
                (2024, 1),
                (2025, 1),
                (2026, 3),
            ],
        )

    def test_ransomware_and_forensic_counts(self) -> None:
        ransomware = {
            row["status"]: row["count"]
            for row in self.analysis["ransomware"]
        }

        forensic = {
            row["status"]: row["count"]
            for row in self.analysis["forensic_triage"]
        }

        self.assertEqual(
            ransomware,
            {
                "Known": 2,
                "Unknown": 4,
            },
        )

        self.assertEqual(
            forensic,
            {
                "Yes": 2,
                "No": 4,
                "Not supplied": 0,
            },
        )

    def test_remediation_statistics_are_correct(self) -> None:
        statistics = self.analysis[
            "remediation_window_statistics"
        ]

        self.assertEqual(statistics["minimum_days"], 3)
        self.assertEqual(statistics["maximum_days"], 90)
        self.assertEqual(statistics["mean_days"], 33.8)
        self.assertEqual(statistics["median_days"], 25.5)

    def test_remediation_buckets_cover_every_record(self) -> None:
        buckets = {
            row["window"]: row["count"]
            for row in self.analysis["remediation_buckets"]
        }

        self.assertEqual(
            buckets,
            {
                "0-7 days": 1,
                "8-14 days": 1,
                "15-21 days": 1,
                "22-30 days": 1,
                "31-60 days": 1,
                "More than 60 days": 1,
            },
        )

        self.assertEqual(sum(buckets.values()), 6)

    def test_primary_review_signal_counts(self) -> None:
        signals = {
            row["signal"]: row["count"]
            for row in self.analysis["review_signals"]
        }

        self.assertEqual(
            signals,
            {
                "Forensic triage indicated": 2,
                "Known ransomware use": 1,
                "Catalog due date passed": 2,
                "Catalog due within 7 days": 1,
                "Catalog due within 30 days": 0,
                "Routine review": 0,
            },
        )

        self.assertEqual(sum(signals.values()), 6)

    def test_review_queue_order_is_deterministic(self) -> None:
        ordered_cves = [
            row["cve_id"]
            for row in self.analysis["vulnerabilities"]
        ]

        self.assertEqual(
            ordered_cves,
            [
                "CVE-2099-0001",
                "CVE-2099-0003",
                "CVE-2099-0004",
                "CVE-2099-0006",
                "CVE-2099-0005",
                "CVE-2099-0002",
            ],
        )

    def test_review_row_retains_all_reasons(self) -> None:
        first = self.analysis["vulnerabilities"][0]

        self.assertEqual(
            first["cve_id"],
            "CVE-2099-0001",
        )
        self.assertEqual(
            first["days_until_due"],
            1,
        )
        self.assertEqual(
            first["primary_review_signal"],
            "Forensic triage indicated",
        )
        self.assertEqual(
            first["review_reasons"],
            [
                "Forensic triage indicated",
                "Known ransomware use",
                "Catalog due within 7 days",
            ],
        )

    def test_historical_date_changes_due_status(self) -> None:
        analysis = analyze_catalog(
            self.catalog,
            as_of=date(2026, 8, 20),
        )

        rows_by_cve = {
            row["cve_id"]: row
            for row in analysis["vulnerabilities"]
        }

        filebridge = rows_by_cve["CVE-2099-0002"]

        self.assertEqual(
            filebridge["days_until_due"],
            19,
        )
        self.assertEqual(
            filebridge["due_status"],
            "Catalog due within 30 days",
        )

    def test_missing_forensic_value_is_counted_separately(
        self,
    ) -> None:
        payload = deepcopy(self.original_payload)

        del payload["vulnerabilities"][0]["forensicTriage"]

        catalog = parse_catalog(
            payload,
            source="kev_sample.json",
        )

        analysis = analyze_catalog(
            catalog,
            as_of=date(2026, 9, 3),
        )

        forensic = {
            row["status"]: row["count"]
            for row in analysis["forensic_triage"]
        }

        self.assertEqual(
            forensic,
            {
                "Yes": 1,
                "No": 4,
                "Not supplied": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()