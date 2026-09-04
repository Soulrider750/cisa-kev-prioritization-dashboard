"""Tests for KEV catalog validation and normalization."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import unittest

from kev_dashboard.models import (
    CatalogValidationError,
    Vulnerability,
    parse_catalog,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kev_sample.json"


class ModelTests(unittest.TestCase):
    """Verify valid and invalid catalog behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
            cls.original_payload = json.load(fixture_file)

    def fresh_payload(self) -> dict:
        """Return an independent copy that each test may safely modify."""

        return deepcopy(self.original_payload)

    def assert_validation_error(
        self,
        payload: dict,
        expected_message: str,
    ) -> None:
        """Confirm that invalid data produces a useful error."""

        with self.assertRaises(CatalogValidationError) as context:
            parse_catalog(payload, source="kev_sample.json")

        self.assertIn(expected_message, str(context.exception))

    def test_valid_fixture_is_normalized(self) -> None:
        catalog = parse_catalog(
            self.fresh_payload(),
            source="kev_sample.json",
        )

        self.assertEqual(catalog.catalog_version, "Testing-1.0")
        self.assertEqual(catalog.released_date, date(2026, 9, 3))
        self.assertEqual(catalog.source, "kev_sample.json")
        self.assertEqual(len(catalog.vulnerabilities), 6)

        first = catalog.vulnerabilities[0]

        self.assertIsInstance(first, Vulnerability)
        self.assertEqual(first.cve_id, "CVE-2099-0001")
        self.assertEqual(first.vendor, "Northstar Software")
        self.assertEqual(first.ransomware_use, "Known")
        self.assertEqual(first.forensic_triage, "Yes")
        self.assertEqual(first.cwes, ("CWE-287",))

    def test_remediation_days_is_derived(self) -> None:
        catalog = parse_catalog(
            self.fresh_payload(),
            source="kev_sample.json",
        )

        first = catalog.vulnerabilities[0]

        self.assertEqual(first.remediation_days, 3)

    def test_missing_forensic_triage_is_allowed(self) -> None:
        payload = self.fresh_payload()
        del payload["vulnerabilities"][0]["forensicTriage"]

        catalog = parse_catalog(
            payload,
            source="kev_sample.json",
        )

        self.assertIsNone(
            catalog.vulnerabilities[0].forensic_triage
        )

    def test_count_mismatch_is_rejected(self) -> None:
        payload = self.fresh_payload()
        payload["count"] = 99

        self.assert_validation_error(
            payload,
            "count declares 99 records",
        )

    def test_duplicate_cve_is_rejected(self) -> None:
        payload = self.fresh_payload()

        payload["vulnerabilities"][1]["cveID"] = (
            payload["vulnerabilities"][0]["cveID"]
        )

        self.assert_validation_error(
            payload,
            "duplicate cveID CVE-2099-0001",
        )

    def test_malformed_cve_is_rejected(self) -> None:
        payload = self.fresh_payload()
        payload["vulnerabilities"][0]["cveID"] = "2099-0001"

        self.assert_validation_error(
            payload,
            "cveID must match CVE-YYYY-NNNN",
        )

    def test_missing_required_text_is_rejected(self) -> None:
        payload = self.fresh_payload()
        payload["vulnerabilities"][0]["product"] = "   "

        self.assert_validation_error(
            payload,
            "product must be a non-empty string",
        )

    def test_invalid_date_is_rejected(self) -> None:
        payload = self.fresh_payload()
        payload["vulnerabilities"][0]["dateAdded"] = "09/01/2026"

        self.assert_validation_error(
            payload,
            "dateAdded must use YYYY-MM-DD format",
        )

    def test_due_date_before_date_added_is_rejected(self) -> None:
        payload = self.fresh_payload()
        payload["vulnerabilities"][0]["dueDate"] = "2026-08-31"

        self.assert_validation_error(
            payload,
            "dueDate cannot precede dateAdded",
        )

    def test_invalid_ransomware_value_is_rejected(self) -> None:
        payload = self.fresh_payload()

        payload["vulnerabilities"][0][
            "knownRansomwareCampaignUse"
        ] = "No"

        self.assert_validation_error(
            payload,
            "must be Known or Unknown",
        )

    def test_invalid_forensic_value_is_rejected(self) -> None:
        payload = self.fresh_payload()
        payload["vulnerabilities"][0]["forensicTriage"] = "Maybe"

        self.assert_validation_error(
            payload,
            "forensicTriage must be Yes or No",
        )

    def test_invalid_cwe_is_rejected(self) -> None:
        payload = self.fresh_payload()
        payload["vulnerabilities"][0]["cwes"] = ["not-a-cwe"]

        self.assert_validation_error(
            payload,
            "cwes[0] must match CWE-NNNN",
        )


if __name__ == "__main__":
    unittest.main()