"""Integrity tests for the synthetic KEV test fixture."""

from datetime import date
import json
from pathlib import Path
import unittest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kev_sample.json"

REQUIRED_FILES = {
    "cveID",
    "vendorProject",
    "product",
    "vulnerabilityName",
    "dateAdded",
    "shortDescription",
    "requiredAction",
    "dueDate",
    "knownRansomwareCampaignUse",
    "forensicTriage",
}

class FixtureTests(unittest.TestCase):
    """Confirm that the learning fixture is intentionally consistent."""

    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
            cls.catalog = json.load(fixture_file)

    def test_declared_count_matches_records(self) -> None:
        records = self.catalog["vulnerabilities"]

        self.assertEqual(self.catalog["count"], len(records))

    def test_records_contain_required_fields(self) -> None:
        for record in self.catalog["vulnerabilities"]:
            missing_fields = REQUIRED_FILES - record.keys()

            self.assertFalse(
                missing_fields,
                f'{record.get("cveID", "unknown record")} is missing {missing_fields}',
            )

    def test_dates_are_valid_and_ordered(self) -> None:
        for record in self.catalog["vulnerabilities"]:
            date_added = date.fromisoformat(record["dateAdded"])
            due_date = date.fromisoformat(record["dueDate"])

            self.assertGreaterEqual(due_date, date_added)

    def test_fixture_covers_expected_categories(self) -> None:
        records = self.catalog["vulnerabilities"]

        ransomware_values = {record["knownRansomwareCampaignUse"] for record in records}
        forensic_values = {record["forensicTriage"] for record in records}

        self.assertEqual(ransomware_values, {"Known", "Unknown"})
        self.assertEqual(forensic_values, {"Yes", "No"})

    def test_records_are_clearly_synthetic(self) -> None:
        for record in self.catalog["vulnerabilities"]:
            self.assertTrue(record["cveID"].startswith("CVE-2099-"))
            self.assertIn("Synthetic fixture record", record["notes"])


if __name__ == "__main__":
    unittest.main()