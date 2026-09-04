"""Tests for the self-contained HTML dashboard."""

from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kev_dashboard.analysis import analyze_catalog
from kev_dashboard.fetch import load_local_json
from kev_dashboard.models import parse_catalog
from kev_dashboard.report import (
    build_report_html,
    render_report,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kev_sample.json"


class ReportTests(unittest.TestCase):
    """Verify dashboard content, safety, and accessibility."""

    @classmethod
    def setUpClass(cls) -> None:
        document = load_local_json(FIXTURE_PATH)

        catalog = parse_catalog(
            document.payload,
            source=document.source,
        )

        cls.analysis = analyze_catalog(
            catalog,
            as_of=date(2026, 9, 3),
        )

    def test_render_report_writes_complete_document(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = (
                Path(temporary_directory)
                / "nested"
                / "index.html"
            )

            returned_path = render_report(
                self.analysis,
                output_path,
            )

            html = output_path.read_text(
                encoding="utf-8"
            )

        self.assertEqual(
            returned_path,
            output_path,
        )
        self.assertTrue(
            html.startswith("<!doctype html>")
        )
        self.assertTrue(
            html.endswith("</html>\n")
        )
        self.assertIn(
            "<title>CISA KEV Prioritization Dashboard</title>",
            html,
        )

    def test_headline_metrics_are_present(self) -> None:
        html = build_report_html(self.analysis)

        self.assertIn("Catalog entries", html)
        self.assertIn("Known ransomware", html)
        self.assertIn("Forensic triage", html)
        self.assertIn("Unique vendors", html)
        self.assertIn("Median window", html)
        self.assertIn("33.3% of the snapshot", html)
        self.assertIn("25.5 days", html)

    def test_expected_chart_titles_are_present(self) -> None:
        html = build_report_html(self.analysis)

        expected_titles = (
            "Top 4 vendors by catalog entries",
            "Catalog additions by year",
            "Known ransomware campaign use",
            "Forensic-triage indication",
            "Catalog remediation-window distribution",
            "Primary review signals",
        )

        for title in expected_titles:
            with self.subTest(title=title):
                self.assertIn(title, html)

    def test_charts_include_accessible_equivalents(
        self,
    ) -> None:
        html = build_report_html(self.analysis)

        self.assertEqual(
            html.count('role="img"'),
            6,
        )
        self.assertEqual(
            html.count("<desc id="),
            6,
        )
        self.assertEqual(
            html.count('<details class="chart-data">'),
            6,
        )
        self.assertIn(
            "View data for Catalog additions by year",
            html,
        )

    def test_queue_limit_and_order_are_respected(
        self,
    ) -> None:
        html = build_report_html(
            self.analysis,
            queue_limit=3,
        )

        first_position = html.index(
            "CVE-2099-0001"
        )
        second_position = html.index(
            "CVE-2099-0003"
        )
        third_position = html.index(
            "CVE-2099-0004"
        )

        self.assertLess(
            first_position,
            second_position,
        )
        self.assertLess(
            second_position,
            third_position,
        )
        self.assertNotIn(
            "CVE-2099-0006",
            html,
        )

    def test_untrusted_text_is_html_escaped(self) -> None:
        altered_analysis = deepcopy(self.analysis)

        altered_analysis["vulnerabilities"][0][
            "vendor"
        ] = '<script>alert("test")</script>'

        html = build_report_html(
            altered_analysis
        )

        self.assertNotIn(
            '<script>alert("test")</script>',
            html,
        )
        self.assertIn(
            (
                "&lt;script&gt;alert"
                "(&quot;test&quot;)&lt;/script&gt;"
            ),
            html,
        )

    def test_https_source_becomes_safe_link(self) -> None:
        altered_analysis = deepcopy(self.analysis)

        altered_analysis["metadata"]["source"] = (
            "https://www.cisa.gov/feed.json"
        )

        html = build_report_html(
            altered_analysis
        )

        self.assertIn(
            'href="https://www.cisa.gov/feed.json"',
            html,
        )
        self.assertIn(
            'rel="noreferrer noopener"',
            html,
        )

    def test_local_source_is_not_linked(self) -> None:
        html = build_report_html(self.analysis)

        self.assertIn(
            "local snapshot",
            html,
        )

    def test_report_has_no_external_assets(self) -> None:
        html = build_report_html(
            self.analysis
        ).casefold()

        self.assertNotIn("<script", html)
        self.assertNotIn("<link", html)
        self.assertNotIn(" src=", html)

    def test_invalid_display_limits_are_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "top_vendors must be at least 1",
        ):
            build_report_html(
                self.analysis,
                top_vendors=0,
            )

        with self.assertRaisesRegex(
            ValueError,
            "queue_limit must be at least 1",
        ):
            build_report_html(
                self.analysis,
                queue_limit=0,
            )


if __name__ == "__main__":
    unittest.main()