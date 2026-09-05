"""Tests for transactional dashboard publication."""

import fcntl
import os
import stat
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
from unittest.mock import patch

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
    PublicationBusyError,
    PublicationError,
    PublicationResult,
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

    def retrieval_time(
        self,
        minute: int,
    ) -> datetime:
        """Return one deterministic retrieval time."""

        return datetime(
            2026,
            9,
            5,
            3,
            minute,
            25,
            tzinfo=timezone.utc,
        )

    def publish_initial_release(
        self,
    ) -> PublicationResult:
        """Publish one deterministic last-known-good release."""

        self.build_candidate(
            "candidate-initial",
            retrieved_at=self.retrieval_time(30),
        )

        return publish_candidate(
            self.deployment_root,
            "candidate-initial",
            now=self.now,
            max_age=self.max_age,
        )

    def temporary_activation_paths(
        self,
    ) -> list[Path]:
        """Return temporary current-link paths, including broken links."""

        return sorted(
            (
                path
                for path
                in self.deployment_root.iterdir()
                if path.name.startswith(
                    ".current-"
                )
                and path.name.endswith(".tmp")
            ),
            key=lambda path: path.name,
        )

    def assert_release_ids(
        self,
        *expected_release_ids: str,
    ) -> None:
        """Assert the exact immutable-release set."""

        self.assertEqual(
            {
                path.name
                for path
                in self.releases_path.iterdir()
            },
            set(expected_release_ids),
        )

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

    def test_validation_failure_preserves_last_known_good(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        initial_target = os.readlink(
            self.current_path
        )

        candidate_path = self.build_candidate(
            "candidate-invalid",
            retrieved_at=self.retrieval_time(40),
        )

        (
            candidate_path
            / "data"
            / "metadata.json"
        ).unlink()

        with self.assertRaisesRegex(
            PublicationError,
            "candidate build validation failed",
        ):
            publish_candidate(
                self.deployment_root,
                "candidate-invalid",
                now=self.now,
                max_age=self.max_age,
            )

        self.assertEqual(
            os.readlink(self.current_path),
            initial_target,
        )
        self.assertTrue(
            candidate_path.is_dir()
        )
        self.assert_release_ids(
            initial_result.release_id
        )
        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

    def test_policy_failure_preserves_last_known_good(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        initial_target = os.readlink(
            self.current_path
        )

        candidate_path = self.build_candidate(
            "candidate-unapproved",
            retrieved_at=self.retrieval_time(40),
            source="fixture://not-approved",
        )

        with self.assertRaisesRegex(
            PublicationError,
            "candidate failed deployment policy",
        ):
            publish_candidate(
                self.deployment_root,
                "candidate-unapproved",
                now=self.now,
                max_age=self.max_age,
            )

        self.assertEqual(
            os.readlink(self.current_path),
            initial_target,
        )
        self.assertTrue(
            candidate_path.is_dir()
        )
        self.assert_release_ids(
            initial_result.release_id
        )
        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

    def test_switch_failure_restores_candidate_and_current(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        initial_target = os.readlink(
            self.current_path
        )

        candidate_path = self.build_candidate(
            "candidate-switch-failure",
            retrieved_at=self.retrieval_time(40),
        )

        with patch(
            "kev_dashboard.publication.os.replace",
            side_effect=OSError(
                "simulated switch failure"
            ),
        ):
            with self.assertRaisesRegex(
                PublicationError,
                "could not activate release",
            ):
                publish_candidate(
                    self.deployment_root,
                    "candidate-switch-failure",
                    now=self.now,
                    max_age=self.max_age,
                )

        self.assertEqual(
            os.readlink(self.current_path),
            initial_target,
        )
        self.assertTrue(
            candidate_path.is_dir()
        )
        self.assert_release_ids(
            initial_result.release_id
        )
        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

    def test_lock_contention_preserves_candidate_and_current(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        initial_target = os.readlink(
            self.current_path
        )

        candidate_path = self.build_candidate(
            "candidate-contended",
            retrieved_at=self.retrieval_time(40),
        )

        lock_path = (
            self.deployment_root
            / ".publish.lock"
        )

        with lock_path.open("a+b") as lock_file:
            fcntl.flock(
                lock_file.fileno(),
                (
                    fcntl.LOCK_EX
                    | fcntl.LOCK_NB
                ),
            )

            try:
                with self.assertRaisesRegex(
                    PublicationBusyError,
                    "publication already in progress",
                ):
                    publish_candidate(
                        self.deployment_root,
                        "candidate-contended",
                        now=self.now,
                        max_age=self.max_age,
                    )
            finally:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_UN,
                )

        self.assertEqual(
            os.readlink(self.current_path),
            initial_target,
        )
        self.assertTrue(
            candidate_path.is_dir()
        )
        self.assert_release_ids(
            initial_result.release_id
        )
        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

    def test_symbolic_link_lock_file_is_rejected(
        self,
    ) -> None:
        candidate_path = self.build_candidate(
            "candidate-lock-link",
            retrieved_at=self.retrieval_time(40),
        )

        marker_path = (
            self.deployment_root.parent
            / "lock-marker.txt"
        )

        marker_path.write_text(
            "unchanged\n",
            encoding="utf-8",
        )

        lock_path = (
            self.deployment_root
            / ".publish.lock"
        )

        lock_path.symlink_to(
            marker_path
        )

        with self.assertRaisesRegex(
            PublicationError,
            (
                "publication lock must not be "
                "a symbolic link"
            ),
        ):
            publish_candidate(
                self.deployment_root,
                "candidate-lock-link",
                now=self.now,
                max_age=self.max_age,
            )

        self.assertEqual(
            marker_path.read_text(
                encoding="utf-8"
            ),
            "unchanged\n",
        )
        self.assertTrue(
            lock_path.is_symlink()
        )
        self.assertTrue(
            candidate_path.is_dir()
        )
        self.assertFalse(
            os.path.lexists(self.current_path)
        )
        self.assert_release_ids()
        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

    def test_nonregular_lock_file_is_rejected(
        self,
    ) -> None:
        candidate_path = self.build_candidate(
            "candidate-lock-directory",
            retrieved_at=self.retrieval_time(40),
        )

        lock_path = (
            self.deployment_root
            / ".publish.lock"
        )

        lock_path.mkdir()

        with self.assertRaisesRegex(
            PublicationError,
            (
                "publication lock must be "
                "a regular file"
            ),
        ):
            publish_candidate(
                self.deployment_root,
                "candidate-lock-directory",
                now=self.now,
                max_age=self.max_age,
            )

        self.assertTrue(
            lock_path.is_dir()
        )
        self.assertTrue(
            candidate_path.is_dir()
        )
        self.assertFalse(
            os.path.lexists(self.current_path)
        )
        self.assert_release_ids()
        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

    def test_lock_is_held_during_validation_and_activation(
        self,
    ) -> None:
        candidate_path = self.build_candidate(
            "candidate-lock-scope",
            retrieved_at=self.retrieval_time(40),
        )

        lock_path = (
            self.deployment_root
            / ".publish.lock"
        )

        observations: list[str] = []

        real_validate_build = (
            validate_build
        )
        real_replace = os.replace

        def assert_lock_held(
            stage: str,
        ) -> None:
            with lock_path.open(
                "a+b"
            ) as contender:
                try:
                    fcntl.flock(
                        contender.fileno(),
                        (
                            fcntl.LOCK_EX
                            | fcntl.LOCK_NB
                        ),
                    )
                except BlockingIOError:
                    observations.append(stage)
                    return

                fcntl.flock(
                    contender.fileno(),
                    fcntl.LOCK_UN,
                )

            self.fail(
                "publication lock was not held "
                f"during {stage}"
            )

        def validating(
            path: Path,
        ) -> None:
            assert_lock_held("validation")
            real_validate_build(path)

        def activating(
            source: Path,
            destination: Path,
        ) -> None:
            assert_lock_held("activation")
            real_replace(
                source,
                destination,
            )

        with patch(
            (
                "kev_dashboard.publication."
                "build_validation.validate_build"
            ),
            side_effect=validating,
        ):
            with patch(
                "kev_dashboard.publication.os.replace",
                side_effect=activating,
            ):
                result = publish_candidate(
                    self.deployment_root,
                    "candidate-lock-scope",
                    now=self.now,
                    max_age=self.max_age,
                )

        self.assertEqual(
            observations,
            [
                "validation",
                "activation",
            ],
        )
        self.assertFalse(
            os.path.lexists(candidate_path)
        )
        self.assertTrue(
            result.release_path.is_dir()
        )
        self.assertTrue(
            result.current_path.is_symlink()
        )
        self.assertTrue(
            lock_path.is_file()
        )
        self.assertFalse(
            lock_path.is_symlink()
        )
        self.assertEqual(
            stat.S_IMODE(
                lock_path.stat().st_mode
            ),
            0o600,
        )


if __name__ == "__main__":
    unittest.main()
