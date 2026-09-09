"""Tests for version consistency across release artifacts."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from kev_dashboard import __version__ as DASHBOARD_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    """Keep package, documentation, and image versions aligned."""

    def read_required(self, relative_path: str) -> str:
        """Read one required UTF-8 release file."""

        path = PROJECT_ROOT / relative_path

        if not path.is_file():
            self.fail(
                "required release file is missing: "
                f"{relative_path}"
            )

        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            self.fail(
                f"{relative_path} is not valid UTF-8: "
                f"{error}"
            )

    def test_package_version_is_three_part(self) -> None:
        self.assertIsNotNone(
            re.fullmatch(
                r"\d+\.\d+\.\d+",
                DASHBOARD_VERSION,
            )
        )

    def test_release_documents_track_package_version(
        self,
    ) -> None:
        version = DASHBOARD_VERSION

        self.assertIn(
            f"Version {version}",
            self.read_required("README.md"),
        )

        publishing = self.read_required(
            "PUBLISHING_STATUS.md"
        )
        publishing_markers = (
            f"Current public release: v{version}",
            f"Release candidate: v{version}",
        )
        self.assertTrue(
            any(
                marker in publishing
                for marker in publishing_markers
            ),
            "publishing status does not track package version",
        )

        workflow = self.read_required(
            "RELEASE_WORKFLOW.md"
        )
        workflow_markers = (
            f"Current release review: v{version}",
            f"Latest published release: v{version}",
        )
        self.assertTrue(
            any(
                marker in workflow
                for marker in workflow_markers
            ),
            "release workflow does not track package version",
        )

        self.assertIn(
            f"v{version}",
            self.read_required("CHANGELOG.md"),
        )


if __name__ == "__main__":
    unittest.main()
