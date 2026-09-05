"""Tests for transactional dashboard publication."""

import os
from dataclasses import replace
from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kev_dashboard.analysis import analyze_catalog
from kev_dashboard.build_validation import (
    validate_build,
)
from kev_dashboard.export import export_build
from kev_dashboard.fetch import (
    DEFAULT_FEED_URL,
    load_local_json,
)
from kev_dashboard.models import parse_catalog
from kev_dashboard.publication import (
    PublicationError,
    publish_candidate,
)
from kev_dashboard.report import render_report


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "kev_sample.json"
)


class PublicationTests(unittest.TestCase):
    """Verify candidate-to-release publication behavior."""

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()

        self.addCleanup(
            self.temporary_directory.cleanup
        )

        self.deployment_root = (
            Path(self.temporary_directory.name)
            / "deployment"
        )

        self.candidates_path = (
            self.deployment_root
            / "candidates"
        )

        self.releases_path = (
            self.deployment_root
            / "releases"
        )

        self.current_path = (
            self.deployment_root
            / "current"
        )

        self.candidates_path.mkdir(
            parents=True
        )

        self.releases_path.mkdir()

        self.now = datetime(
            2026,
            9,
            5,
            4,
            0,
            tzinfo=timezone.utc,
        )

        self.max_age = timedelta(
            hours=1
        )

    def build_candidate(
        self,
        candidate_id: str,
        *,
        retrieved_at: datetime,
        source: str = DEFAULT_FEED_URL,
    ) -> Path:
        """Build one deterministic private candidate."""

        candidate_path = (
            self.candidates_path
            / candidate_id
        )

        loaded_document = load_local_json(
            FIXTURE_PATH
        )

        document = replace(
            loaded_document,
            source=source,
            retrieved_at=retrieved_at,
        )

        catalog = parse_catalog(
            document.payload,
            source=document.source,
        )

        analysis = analyze_catalog(
            catalog,
            as_of=date(2026, 9, 3),
        )

        export_build(
            document,
            analysis,
            candidate_path,
        )

        render_report(
            analysis,
            candidate_path / "index.html",
            retrieved_at=document.retrieved_at,
        )

        return candidate_path

    def test_valid_candidate_becomes_current_release(
        self,
    ) -> None:
        candidate_path = self.build_candidate(
            "candidate-one",
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

        result = publish_candidate(
            self.deployment_root,
            "candidate-one",
            now=self.now,
            max_age=self.max_age,
        )

        self.assertFalse(
            os.path.lexists(candidate_path)
        )

        self.assertEqual(
            result.release_path,
            (
                self.releases_path
                / result.release_id
            ),
        )

        self.assertTrue(
            result.release_path.is_dir()
        )

        self.assertRegex(
            result.release_id,
            (
                r"^20260905T033625000000Z-"
                r"[0-9a-f]{16}$"
            ),
        )

        self.assertEqual(
            result.current_path,
            self.current_path,
        )

        self.assertTrue(
            result.current_path.is_symlink()
        )

        self.assertEqual(
            os.readlink(result.current_path),
            (
                "releases/"
                f"{result.release_id}"
            ),
        )

        self.assertIsNone(
            result.previous_release_id
        )

        self.assertIsNone(
            validate_build(
                result.release_path
            )
        )

    def test_second_publication_keeps_previous_release(
        self,
    ) -> None:
        self.build_candidate(
            "candidate-one",
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

        first_result = publish_candidate(
            self.deployment_root,
            "candidate-one",
            now=self.now,
            max_age=self.max_age,
        )

        self.assertTrue(
            first_result.release_path.is_dir()
        )

        first_report_path = (
            first_result.release_path
            / "index.html"
        )

        self.assertTrue(
            first_report_path.is_file()
        )

        first_report_bytes = (
            first_report_path.read_bytes()
        )

        self.build_candidate(
            "candidate-two",
            retrieved_at=datetime(
                2026,
                9,
                5,
                3,
                37,
                25,
                tzinfo=timezone.utc,
            ),
        )

        second_result = publish_candidate(
            self.deployment_root,
            "candidate-two",
            now=self.now,
            max_age=self.max_age,
        )

        self.assertNotEqual(
            first_result.release_id,
            second_result.release_id,
        )

        self.assertTrue(
            first_result.release_path.is_dir()
        )

        self.assertTrue(
            second_result.release_path.is_dir()
        )

        self.assertEqual(
            first_report_path.read_bytes(),
            first_report_bytes,
        )

        self.assertEqual(
            os.readlink(self.current_path),
            (
                "releases/"
                f"{second_result.release_id}"
            ),
        )

        self.assertEqual(
            second_result.previous_release_id,
            first_result.release_id,
        )

    def test_release_collision_preserves_candidate(
        self,
    ) -> None:
        retrieved_at = datetime(
            2026,
            9,
            5,
            3,
            36,
            25,
            tzinfo=timezone.utc,
        )

        self.build_candidate(
            "candidate-one",
            retrieved_at=retrieved_at,
        )

        first_result = publish_candidate(
            self.deployment_root,
            "candidate-one",
            now=self.now,
            max_age=self.max_age,
        )

        self.assertTrue(
            first_result.release_id
        )

        self.assertTrue(
            first_result.release_path.is_dir()
        )

        first_report_bytes = (
            first_result.release_path
            / "index.html"
        ).read_bytes()

        second_candidate = self.build_candidate(
            "candidate-two",
            retrieved_at=retrieved_at,
        )

        current_target = os.readlink(
            self.current_path
        )

        with self.assertRaisesRegex(
            PublicationError,
            "release already exists",
        ):
            publish_candidate(
                self.deployment_root,
                "candidate-two",
                now=self.now,
                max_age=self.max_age,
            )

        self.assertTrue(
            second_candidate.is_dir()
        )

        self.assertEqual(
            os.readlink(self.current_path),
            current_target,
        )

        self.assertEqual(
            (
                first_result.release_path
                / "index.html"
            ).read_bytes(),
            first_report_bytes,
        )

        self.assertEqual(
            len(list(self.releases_path.iterdir())),
            1,
        )

    def test_existing_current_file_is_not_replaced(
        self,
    ) -> None:
        candidate_path = self.build_candidate(
            "candidate-one",
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

        self.current_path.write_text(
            "do not replace\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            PublicationError,
            "current must be a symbolic link",
        ):
            publish_candidate(
                self.deployment_root,
                "candidate-one",
                now=self.now,
                max_age=self.max_age,
            )

        self.assertEqual(
            self.current_path.read_text(
                encoding="utf-8"
            ),
            "do not replace\n",
        )

        self.assertTrue(
            candidate_path.is_dir()
        )

        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )

    def test_candidate_identifier_cannot_escape_root(
        self,
    ) -> None:
        outside_path = (
            self.deployment_root
            / "escape"
        )

        outside_path.mkdir()

        marker_path = (
            outside_path
            / "marker.txt"
        )

        marker_path.write_text(
            "unchanged\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            PublicationError,
            "invalid candidate identifier",
        ):
            publish_candidate(
                self.deployment_root,
                "../escape",
                now=self.now,
                max_age=self.max_age,
            )

        self.assertEqual(
            marker_path.read_text(
                encoding="utf-8"
            ),
            "unchanged\n",
        )

        self.assertFalse(
            os.path.lexists(self.current_path)
        )

        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )


if __name__ == "__main__":
    unittest.main()
