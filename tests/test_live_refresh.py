"""Tests for one-shot live dashboard refreshes."""

import errno
import fcntl
import inspect
import json
import os
from dataclasses import replace
from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID

from kev_dashboard import live_refresh
from kev_dashboard import pipeline
from kev_dashboard import publication
from kev_dashboard.build_validation import (
    validate_build,
)
from kev_dashboard.fetch import (
    CatalogDocument,
    CatalogLoadError,
    DEFAULT_FEED_URL,
    DEFAULT_TIMEOUT_SECONDS,
    load_local_json,
)
from kev_dashboard.live_refresh import (
    LiveRefreshBusyError,
    LiveRefreshError,
    refresh_live_dashboard,
)
from kev_dashboard.pipeline import BuildResult
from kev_dashboard.publication import (
    PublicationBusyError,
    PublicationError,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "kev_sample.json"
)

FIXED_UUID = UUID(
    "01234567-89ab-cdef-0123-456789abcdef"
)

EXPECTED_CANDIDATE_ID = (
    "candidate-"
    "0123456789abcdef0123456789abcdef"
)


class LiveRefreshTests(unittest.TestCase):
    """Verify official fetch-to-publication orchestration."""

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

        self.deployment_root.mkdir(
            mode=0o700,
        )

        self.candidates_path.mkdir(
            mode=0o700,
        )

        self.releases_path.mkdir(
            mode=0o700,
)

        self.now = datetime(
            2026,
            9,
            5,
            4,
            5,
            tzinfo=timezone.utc,
        )

        self.document = replace(
            load_local_json(FIXTURE_PATH),
            source=DEFAULT_FEED_URL,
            retrieved_at=datetime(
                2026,
                9,
                5,
                3,
                55,
                tzinfo=timezone.utc,
            ),
        )

    def capture_preflight_failure(
        self,
        expected_message: str,
        *,
        now: datetime | None = None,
        expected_uuid_calls: int = 0,
    ) -> BaseException:
        """Run refresh and require failure before fetching."""

        caught_error: BaseException | None = None

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ) as mocked_uuid,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ) as mocked_fetch,
        ):
            try:
                refresh_live_dashboard(
                    self.deployment_root,
                    now=(
                        self.now
                        if now is None
                        else now
                    ),
                )
            except (
                OSError,
                ValueError,
            ) as error:
                caught_error = error
            else:
                self.fail(
                    "refresh did not reject unsafe "
                    "deployment state"
                )

        self.assertEqual(
            mocked_uuid.call_count,
            expected_uuid_calls,
        )
        mocked_fetch.assert_not_called()

        self.assertIsInstance(
            caught_error,
            LiveRefreshError,
        )

        self.assertRegex(
            str(caught_error),
            expected_message,
        )

        return caught_error

    def publish_initial_release(
        self,
    ) -> publication.PublicationResult:
        """Create one deterministic last-known-good release."""

        initial_document = replace(
            self.document,
            retrieved_at=datetime(
                2026,
                9,
                5,
                3,
                45,
                tzinfo=timezone.utc,
            ),
        )

        candidate_id = "candidate-initial"

        candidate_path = (
            self.candidates_path
            / candidate_id
        )

        candidate_path.mkdir(
            mode=0o700
        )

        pipeline.build_dashboard(
            initial_document,
            candidate_path,
            as_of=date(2026, 9, 4),
            top_vendors=2,
            queue_limit=3,
        )

        return publication.publish_candidate(
            self.deployment_root,
            candidate_id,
            now=self.now,
            max_age=timedelta(hours=1),
        )

    def temporary_activation_paths(
        self,
    ) -> list[Path]:
        """Return temporary current-link paths."""

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

    def assert_last_known_good(
        self,
        initial_result: publication.PublicationResult,
    ) -> None:
        """Assert that the initial release remains selected."""

        self.assertEqual(
            os.readlink(self.current_path),
            (
                "releases/"
                f"{initial_result.release_id}"
            ),
        )

        self.assertEqual(
            {
                path.name
                for path
                in self.releases_path.iterdir()
            },
            {
                initial_result.release_id,
            },
        )

        self.assertTrue(
            initial_result.release_path.is_dir()
        )

        self.assertIsNone(
            validate_build(
                initial_result.release_path
            )
        )

        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

    def observe_refresh_lock_held(
        self,
        lock_path: Path,
        stage: str,
        observations: list[str],
    ) -> None:
        """Record a stage only while the refresh lock is held."""

        with lock_path.open("a+b") as contender:
            try:
                fcntl.flock(
                    contender.fileno(),
                    (
                        fcntl.LOCK_EX
                        | fcntl.LOCK_NB
                    ),
                )
            except OSError as error:
                if error.errno in {
                    errno.EACCES,
                    errno.EAGAIN,
                    errno.EWOULDBLOCK,
                }:
                    observations.append(stage)
                    return

                raise

            fcntl.flock(
                contender.fileno(),
                fcntl.LOCK_UN,
            )

        self.fail(
            "live refresh lock was not held "
            f"during {stage}"
        )

    def test_public_api_excludes_nonlive_source_controls(
        self,
    ) -> None:
        parameters = inspect.signature(
            refresh_live_dashboard
        ).parameters

        self.assertEqual(
            tuple(parameters),
            (
                "deployment_root",
                "now",
                "timeout",
                "max_age",
                "top_vendors",
                "queue_limit",
            ),
        )

        for excluded_parameter in (
            "input",
            "source_url",
            "as_of",
            "candidate_id",
        ):
            with self.subTest(
                parameter=excluded_parameter
            ):
                self.assertNotIn(
                    excluded_parameter,
                    parameters,
                )

    def test_successful_refresh_fetches_and_publishes(
        self,
    ) -> None:
        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ) as mocked_fetch,
        ):
            result = refresh_live_dashboard(
                self.deployment_root,
                now=self.now,
                timeout=12.5,
                max_age=timedelta(hours=1),
                top_vendors=2,
                queue_limit=3,
            )

        self.assertEqual(
            result.candidate_id,
            EXPECTED_CANDIDATE_ID,
        )

        mocked_fetch.assert_called_once_with(
            DEFAULT_FEED_URL,
            timeout=12.5,
        )

        self.assertEqual(
            result.source,
            DEFAULT_FEED_URL,
        )
        self.assertEqual(
            result.record_count,
            6,
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
        self.assertEqual(
            result.current_path,
            (
                self.deployment_root
                / "current"
            ),
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
        self.assertFalse(
            os.path.lexists(
                self.candidates_path
                / EXPECTED_CANDIDATE_ID
            )
        )
        self.assertEqual(
            len(list(self.releases_path.iterdir())),
            1,
        )
        self.assertIsNone(
            validate_build(
                result.release_path
            )
        )

    def test_candidate_is_private_before_build(
        self,
    ) -> None:
        observations: list[
            tuple[Path, int]
        ] = []

        real_build_dashboard = (
            pipeline.build_dashboard
        )

        def observing_build(
            document: CatalogDocument,
            output_dir: Path,
            *,
            as_of: date | None,
            top_vendors: int,
            queue_limit: int,
        ) -> BuildResult:
            observations.append(
                (
                    output_dir.parent,
                    stat.S_IMODE(
                        output_dir.stat().st_mode
                    ),
                )
            )

            return real_build_dashboard(
                document,
                output_dir,
                as_of=as_of,
                top_vendors=top_vendors,
                queue_limit=queue_limit,
            )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                ),
                side_effect=observing_build,
            ),
        ):
            refresh_live_dashboard(
                self.deployment_root,
                now=self.now,
            )

        self.assertEqual(
            observations,
            [
                (
                    self.candidates_path,
                    0o700,
                ),
            ],
        )

    def test_analysis_date_uses_america_new_york(
        self,
    ) -> None:
        observed_dates: list[
            date | None
        ] = []

        real_build_dashboard = (
            pipeline.build_dashboard
        )

        def observing_build(
            document: CatalogDocument,
            output_dir: Path,
            *,
            as_of: date | None,
            top_vendors: int,
            queue_limit: int,
        ) -> BuildResult:
            observed_dates.append(as_of)

            return real_build_dashboard(
                document,
                output_dir,
                as_of=as_of,
                top_vendors=top_vendors,
                queue_limit=queue_limit,
            )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                ),
                side_effect=observing_build,
            ),
        ):
            result = refresh_live_dashboard(
                self.deployment_root,
                now=self.now,
            )

        self.assertEqual(
            observed_dates,
            [
                date(2026, 9, 4),
            ],
        )
        self.assertEqual(
            result.analysis_date,
            "2026-09-04",
        )

        metadata = json.loads(
            (
                result.release_path
                / "data"
                / "metadata.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            metadata["as_of"],
            "2026-09-04",
        )

    def test_symbolic_link_deployment_root_is_rejected_before_fetch(
        self,
    ) -> None:
        real_root = (
            self.deployment_root.parent
            / "real-deployment"
        )

        self.deployment_root.rename(
            real_root
        )

        marker_path = (
            real_root / "marker.txt"
        )

        marker_path.write_text(
            "unchanged\n",
            encoding="utf-8",
        )

        self.deployment_root.symlink_to(
            real_root,
            target_is_directory=True,
        )

        self.capture_preflight_failure(
            (
                "deployment root must not be "
                "a symbolic link"
            )
        )

        self.assertEqual(
            marker_path.read_text(
                encoding="utf-8"
            ),
            "unchanged\n",
        )

        self.assertEqual(
            list(
                (
                    real_root / "candidates"
                ).iterdir()
            ),
            [],
        )

        self.assertEqual(
            list(
                (
                    real_root / "releases"
                ).iterdir()
            ),
            [],
        )

    def test_symbolic_link_candidates_directory_is_rejected_before_fetch(
        self,
    ) -> None:
        self.candidates_path.rmdir()

        outside_candidates = (
            self.deployment_root.parent
            / "outside-candidates"
        )

        outside_candidates.mkdir()

        marker_path = (
            outside_candidates
            / "marker.txt"
        )

        marker_path.write_text(
            "unchanged\n",
            encoding="utf-8",
        )

        self.candidates_path.symlink_to(
            outside_candidates,
            target_is_directory=True,
        )

        self.capture_preflight_failure(
            (
                "candidates directory must not "
                "be a symbolic link"
            )
        )

        self.assertEqual(
            marker_path.read_text(
                encoding="utf-8"
            ),
            "unchanged\n",
        )

        self.assertEqual(
            {
                path.name
                for path
                in outside_candidates.iterdir()
            },
            {
                "marker.txt",
            },
        )

        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )

        self.assertFalse(
            os.path.lexists(
                self.deployment_root
                / "current"
            )
        )

    def test_symbolic_link_releases_directory_is_rejected_before_fetch(
        self,
    ) -> None:
        self.releases_path.rmdir()

        outside_releases = (
            self.deployment_root.parent
            / "outside-releases"
        )

        outside_releases.mkdir()

        marker_path = (
            outside_releases
            / "marker.txt"
        )

        marker_path.write_text(
            "unchanged\n",
            encoding="utf-8",
        )

        self.releases_path.symlink_to(
            outside_releases,
            target_is_directory=True,
        )

        self.capture_preflight_failure(
            (
                "releases directory must not "
                "be a symbolic link"
            )
        )

        self.assertEqual(
            marker_path.read_text(
                encoding="utf-8"
            ),
            "unchanged\n",
        )

        self.assertEqual(
            {
                path.name
                for path
                in outside_releases.iterdir()
            },
            {
                "marker.txt",
            },
        )

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

        self.assertFalse(
            os.path.lexists(
                self.deployment_root
                / "current"
            )
        )

    def test_candidate_collision_is_rejected_before_fetch(
        self,
    ) -> None:
        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        candidate_path.mkdir(
            mode=0o700
        )

        marker_path = (
            candidate_path
            / "marker.txt"
        )

        marker_path.write_text(
            "unchanged\n",
            encoding="utf-8",
        )

        self.capture_preflight_failure(
            "candidate path already exists",
            expected_uuid_calls=1,
        )

        self.assertEqual(
            marker_path.read_text(
                encoding="utf-8"
            ),
            "unchanged\n",
        )

        self.assertEqual(
            {
                path.name
                for path
                in self.candidates_path.iterdir()
            },
            {
                EXPECTED_CANDIDATE_ID,
            },
        )

        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )

        self.assertFalse(
            os.path.lexists(
                self.deployment_root
                / "current"
            )
        )

    def test_fetch_failure_creates_no_candidate_and_preserves_last_known_good(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                side_effect=CatalogLoadError(
                    "simulated upstream failure"
                ),
            ) as mocked_fetch,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                )
            ) as mocked_build,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                )
            ) as mocked_publication,
        ):
            with self.assertRaisesRegex(
                CatalogLoadError,
                "simulated upstream failure",
            ):
                refresh_live_dashboard(
                    self.deployment_root,
                    now=self.now,
                )

        mocked_fetch.assert_called_once_with(
            DEFAULT_FEED_URL,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        mocked_build.assert_not_called()
        mocked_publication.assert_not_called()

        self.assertFalse(
            os.path.lexists(candidate_path)
        )

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

        self.assert_last_known_good(
            initial_result
        )

    def test_build_failure_removes_candidate_and_preserves_last_known_good(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        def failing_build(
            document: CatalogDocument,
            output_dir: Path,
            *,
            as_of: date | None,
            top_vendors: int,
            queue_limit: int,
        ) -> BuildResult:
            (
                output_dir
                / "partial-output.txt"
            ).write_text(
                "incomplete\n",
                encoding="utf-8",
            )

            raise ValueError(
                "simulated build failure"
            )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                ),
                side_effect=failing_build,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                )
            ) as mocked_publication,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "simulated build failure",
            ):
                refresh_live_dashboard(
                    self.deployment_root,
                    now=self.now,
                )

        mocked_publication.assert_not_called()

        self.assertFalse(
            os.path.lexists(candidate_path)
        )

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

        self.assert_last_known_good(
            initial_result
        )

    def test_publication_failure_removes_candidate_and_preserves_last_known_good(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                ),
                side_effect=PublicationError(
                    "simulated publication failure"
                ),
            ) as mocked_publication,
        ):
            with self.assertRaisesRegex(
                PublicationError,
                "simulated publication failure",
            ):
                refresh_live_dashboard(
                    self.deployment_root,
                    now=self.now,
                )

        mocked_publication.assert_called_once()

        self.assertFalse(
            os.path.lexists(candidate_path)
        )

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

        self.assert_last_known_good(
            initial_result
        )

    def test_publication_busy_removes_candidate_and_stays_distinct(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                ),
                side_effect=PublicationBusyError(
                    "publication already in progress"
                ),
            ),
        ):
            with self.assertRaisesRegex(
                PublicationBusyError,
                "publication already in progress",
            ):
                refresh_live_dashboard(
                    self.deployment_root,
                    now=self.now,
                )

        self.assertFalse(
            os.path.lexists(candidate_path)
        )

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

        self.assert_last_known_good(
            initial_result
        )

    def test_naive_now_is_rejected_before_fetch(
        self,
    ) -> None:
        self.capture_preflight_failure(
            "now must be timezone-aware",
            now=datetime(
                2026,
                9,
                5,
                4,
                5,
            ),
        )

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )
        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )
        self.assertFalse(
            os.path.lexists(self.current_path)
        )

    def test_naive_retrieval_time_is_rejected_before_candidate_creation(
        self,
    ) -> None:
        naive_document = replace(
            self.document,
            retrieved_at=datetime(
                2026,
                9,
                5,
                3,
                55,
            ),
        )

        caught_error: BaseException | None = None

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=naive_document,
            ) as mocked_fetch,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                )
            ) as mocked_build,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                )
            ) as mocked_publication,
        ):
            try:
                refresh_live_dashboard(
                    self.deployment_root,
                    now=self.now,
                )
            except (
                OSError,
                ValueError,
            ) as error:
                caught_error = error
            else:
                self.fail(
                    "refresh accepted a naive "
                    "retrieval timestamp"
                )

        mocked_fetch.assert_called_once_with(
            DEFAULT_FEED_URL,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        self.assertIsInstance(
            caught_error,
            LiveRefreshError,
        )
        self.assertRegex(
            str(caught_error),
            "retrieved_at must be timezone-aware",
        )

        mocked_build.assert_not_called()
        mocked_publication.assert_not_called()

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

    def test_deployment_directories_must_share_filesystem(
        self,
    ) -> None:
        real_lstat = os.lstat

        def different_release_device(
            path: object,
            *args: object,
            **kwargs: object,
        ) -> os.stat_result:
            result = real_lstat(
                path,
                *args,
                **kwargs,
            )

            if (
                isinstance(
                    path,
                    (str, bytes, os.PathLike),
                )
                and Path(path)
                == self.releases_path
            ):
                values = list(result)
                values[2] = result.st_dev + 1

                return os.stat_result(values)

            return result

        with patch(
            "kev_dashboard.live_refresh.os.lstat",
            side_effect=different_release_device,
        ):
            self.capture_preflight_failure(
                (
                    "deployment directories must "
                    "be on the same filesystem"
                )
            )

    def test_deployment_root_must_be_owned_by_current_user(
        self,
    ) -> None:
        real_lstat = os.lstat

        def foreign_root_owner(
            path: object,
            *args: object,
            **kwargs: object,
        ) -> os.stat_result:
            result = real_lstat(
                path,
                *args,
                **kwargs,
            )

            if (
                isinstance(
                    path,
                    (str, bytes, os.PathLike),
                )
                and Path(path)
                == self.deployment_root
            ):
                values = list(result)
                values[4] = result.st_uid + 1

                return os.stat_result(values)

            return result

        with patch(
            "kev_dashboard.live_refresh.os.lstat",
            side_effect=foreign_root_owner,
        ):
            self.capture_preflight_failure(
                (
                    "deployment root must be owned "
                    "by the current user"
                )
            )

    def test_deployment_root_must_not_be_group_or_world_writable(
        self,
    ) -> None:
        self.deployment_root.chmod(
            0o775
        )

        self.capture_preflight_failure(
            (
                "deployment root must not be "
                "group- or world-writable"
            )
        )

    def test_candidates_directory_must_be_private(
        self,
    ) -> None:
        self.candidates_path.chmod(
            0o750
        )

        self.capture_preflight_failure(
            (
                "candidates directory permissions "
                "must be 0700"
            )
        )

    def test_releases_directory_must_not_be_group_or_world_writable(
        self,
    ) -> None:
        self.releases_path.chmod(
            0o775
        )

        self.capture_preflight_failure(
            (
                "releases directory must not be "
                "group- or world-writable"
            )
        )

    def test_nondirectory_deployment_root_is_rejected_before_fetch(
        self,
    ) -> None:
        self.candidates_path.rmdir()
        self.releases_path.rmdir()
        self.deployment_root.rmdir()

        self.deployment_root.write_text(
            "not a directory\n",
            encoding="utf-8",
        )

        self.capture_preflight_failure(
            "deployment root must be a directory"
        )

    def test_nondirectory_candidates_path_is_rejected_before_fetch(
        self,
    ) -> None:
        self.candidates_path.rmdir()

        self.candidates_path.write_text(
            "not a directory\n",
            encoding="utf-8",
        )

        self.capture_preflight_failure(
            "candidates directory must be a directory"
        )

        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )

    def test_nondirectory_releases_path_is_rejected_before_fetch(
        self,
    ) -> None:
        self.releases_path.rmdir()

        self.releases_path.write_text(
            "not a directory\n",
            encoding="utf-8",
        )

        self.capture_preflight_failure(
            "releases directory must be a directory"
        )

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

    def test_refresh_lock_contention_stops_before_fetch(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        lock_path.touch(mode=0o600)
        lock_path.chmod(0o600)

        with (
            lock_path.open("r+b") as lock_file,
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ) as mocked_uuid,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ) as mocked_fetch,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                )
            ) as mocked_build,
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                )
            ) as mocked_publication,
        ):
            fcntl.flock(
                lock_file.fileno(),
                (
                    fcntl.LOCK_EX
                    | fcntl.LOCK_NB
                ),
            )

            try:
                with self.assertRaisesRegex(
                    LiveRefreshBusyError,
                    (
                        "live refresh already "
                        "in progress"
                    ),
                ):
                    refresh_live_dashboard(
                        self.deployment_root,
                        now=self.now,
                    )
            finally:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_UN,
                )

        mocked_uuid.assert_not_called()
        mocked_fetch.assert_not_called()
        mocked_build.assert_not_called()
        mocked_publication.assert_not_called()

        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )

        self.assert_last_known_good(
            initial_result
        )

    def test_foreign_owned_refresh_lock_is_rejected_before_fetch(
        self,
    ) -> None:
        lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        lock_path.touch(mode=0o600)
        lock_path.chmod(0o600)

        real_lstat = os.lstat

        def foreign_lock_owner(
            path: object,
            *args: object,
            **kwargs: object,
        ) -> os.stat_result:
            result = real_lstat(
                path,
                *args,
                **kwargs,
            )

            if (
                isinstance(
                    path,
                    (str, bytes, os.PathLike),
                )
                and Path(path) == lock_path
            ):
                values = list(result)
                values[4] = result.st_uid + 1

                return os.stat_result(values)

            return result

        with patch(
            "kev_dashboard.live_refresh.os.lstat",
            side_effect=foreign_lock_owner,
        ):
            self.capture_preflight_failure(
                (
                    "live refresh lock must be owned "
                    "by the current user"
                )
            )

        self.assertTrue(
            lock_path.is_file()
        )
        self.assertFalse(
            lock_path.is_symlink()
        )
        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )
        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )
        self.assertFalse(
            os.path.lexists(self.current_path)
        )

    def test_hard_linked_refresh_lock_is_rejected_before_fetch(
        self,
    ) -> None:
        lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        linked_path = (
            self.deployment_root.parent
            / "linked-refresh-lock"
        )

        lock_path.write_text(
            "lock marker\n",
            encoding="utf-8",
        )
        lock_path.chmod(0o600)

        os.link(
            lock_path,
            linked_path,
        )

        self.capture_preflight_failure(
            (
                "live refresh lock must have "
                "exactly one link"
            )
        )

        self.assertTrue(
            lock_path.is_file()
        )
        self.assertTrue(
            linked_path.is_file()
        )
        self.assertEqual(
            os.lstat(lock_path).st_ino,
            os.lstat(linked_path).st_ino,
        )
        self.assertEqual(
            linked_path.read_text(
                encoding="utf-8"
            ),
            "lock marker\n",
        )
        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )
        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )
        self.assertFalse(
            os.path.lexists(self.current_path)
        )

    def test_failed_candidate_cleanup_reports_residual_after_nested_file_disappears(
        self,
    ) -> None:
        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        candidate_path.mkdir(
            mode=0o700
        )

        (
            candidate_path
            / "partial.txt"
        ).write_text(
            "partial\n",
            encoding="utf-8",
        )

        original_error = RuntimeError(
            "synthetic build failure"
        )

        with patch(
            (
                "kev_dashboard.live_refresh."
                "shutil.rmtree"
            ),
            side_effect=FileNotFoundError(
                "nested entry disappeared"
            ),
        ):
            with self.assertRaises(
                LiveRefreshError
            ) as caught:
                live_refresh._remove_failed_candidate(
                    candidate_path,
                    self.candidates_path,
                    original_error=original_error,
                )

        self.assertIn(
            "candidate cleanup failed",
            str(caught.exception),
        )
        self.assertIn(
            str(candidate_path),
            str(caught.exception),
        )
        self.assertIs(
            caught.exception.__cause__,
            original_error,
        )
        self.assertTrue(
            candidate_path.is_dir()
        )
        self.assertTrue(
            (
                candidate_path
                / "partial.txt"
            ).is_file()
        )

    def test_switch_and_rollback_failure_reports_residual_release(
        self,
    ) -> None:
        initial_result = (
            self.publish_initial_release()
        )

        initial_target = os.readlink(
            self.current_path
        )

        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        activation_error = OSError(
            "synthetic activation failure"
        )

        rollback_error = OSError(
            "synthetic rollback failure"
        )

        real_publish_candidate = (
            publication.publish_candidate
        )

        real_rename = Path.rename

        def selectively_fail_rollback(
            source: Path,
            target: Path,
        ) -> Path:
            target_path = Path(target)

            if (
                source.parent
                == self.releases_path
                and target_path
                == candidate_path
            ):
                raise rollback_error

            return real_rename(
                source,
                target_path,
            )

        def failing_publication(
            deployment_root: Path,
            candidate_id: str,
            *,
            now: datetime,
            max_age: timedelta,
        ) -> publication.PublicationResult:
            with (
                patch(
                    (
                        "kev_dashboard.publication."
                        "os.replace"
                    ),
                    side_effect=activation_error,
                ),
                patch.object(
                    Path,
                    "rename",
                    autospec=True,
                    side_effect=(
                        selectively_fail_rollback
                    ),
                ),
            ):
                return real_publish_candidate(
                    deployment_root,
                    candidate_id,
                    now=now,
                    max_age=max_age,
                )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                ),
                side_effect=failing_publication,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "shutil.rmtree"
                ),
            ) as mocked_candidate_cleanup,
        ):
            with self.assertRaises(
                PublicationError
            ) as caught:
                refresh_live_dashboard(
                    self.deployment_root,
                    now=self.now,
                )

        self.assertIs(
            caught.exception.__cause__,
            rollback_error,
        )

        self.assertFalse(
            os.path.lexists(candidate_path)
        )

        mocked_candidate_cleanup.assert_not_called()

        self.assertEqual(
            os.readlink(self.current_path),
            initial_target,
        )

        self.assertTrue(
            initial_result.release_path.is_dir()
        )

        orphan_paths = [
            path
            for path
            in self.releases_path.iterdir()
            if path != initial_result.release_path
        ]

        self.assertEqual(
            len(orphan_paths),
            1,
        )

        orphan_path = orphan_paths[0]

        self.assertTrue(
            orphan_path.is_dir()
        )

        self.assertIsNone(
            validate_build(orphan_path)
        )

        self.assertEqual(
            self.temporary_activation_paths(),
            [],
        )

        error_message = str(
            caught.exception
        )

        self.assertIn(
            str(orphan_path),
            error_message,
        )
        self.assertIn(
            str(candidate_path),
            error_message,
        )
        self.assertIn(
            "synthetic activation failure",
            error_message,
        )
        self.assertIn(
            "synthetic rollback failure",
            error_message,
        )

        refresh_lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        with refresh_lock_path.open(
            "r+b"
        ) as contender:
            fcntl.flock(
                contender.fileno(),
                (
                    fcntl.LOCK_EX
                    | fcntl.LOCK_NB
                ),
            )

            fcntl.flock(
                contender.fileno(),
                fcntl.LOCK_UN,
            )

    def test_symbolic_link_refresh_lock_is_rejected_before_fetch(
        self,
    ) -> None:
        marker_path = (
            self.deployment_root.parent
            / "refresh-lock-marker.txt"
        )

        marker_path.write_text(
            "unchanged\n",
            encoding="utf-8",
        )

        lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        lock_path.symlink_to(
            marker_path
        )

        self.capture_preflight_failure(
            (
                "live refresh lock must not be "
                "a symbolic link"
            )
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
        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )
        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )
        self.assertFalse(
            os.path.lexists(self.current_path)
        )

    def test_nonregular_refresh_lock_is_rejected_before_fetch(
        self,
    ) -> None:
        lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        lock_path.mkdir()

        self.capture_preflight_failure(
            (
                "live refresh lock must be "
                "a regular file"
            )
        )

        self.assertTrue(
            lock_path.is_dir()
        )
        self.assertEqual(
            list(self.candidates_path.iterdir()),
            [],
        )
        self.assertEqual(
            list(self.releases_path.iterdir()),
            [],
        )
        self.assertFalse(
            os.path.lexists(self.current_path)
        )

    def test_refresh_lock_is_held_during_fetch_build_and_publication(
        self,
    ) -> None:
        lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        observations: list[str] = []

        real_build_dashboard = (
            pipeline.build_dashboard
        )

        real_publish_candidate = (
            publication.publish_candidate
        )

        def observing_fetch(
            url: str,
            *,
            timeout: float,
        ) -> CatalogDocument:
            self.observe_refresh_lock_held(
                lock_path,
                "fetch",
                observations,
            )

            return self.document

        def observing_build(
            document: CatalogDocument,
            output_dir: Path,
            *,
            as_of: date | None,
            top_vendors: int,
            queue_limit: int,
        ) -> BuildResult:
            self.observe_refresh_lock_held(
                lock_path,
                "build",
                observations,
            )

            return real_build_dashboard(
                document,
                output_dir,
                as_of=as_of,
                top_vendors=top_vendors,
                queue_limit=queue_limit,
            )

        def observing_publication(
            deployment_root: Path,
            candidate_id: str,
            *,
            now: datetime,
            max_age: timedelta,
        ) -> publication.PublicationResult:
            self.observe_refresh_lock_held(
                lock_path,
                "publication",
                observations,
            )

            return real_publish_candidate(
                deployment_root,
                candidate_id,
                now=now,
                max_age=max_age,
            )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                side_effect=observing_fetch,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                ),
                side_effect=observing_build,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                ),
                side_effect=observing_publication,
            ),
        ):
            result = refresh_live_dashboard(
                self.deployment_root,
                now=self.now,
            )

        self.assertEqual(
            observations,
            [
                "fetch",
                "build",
                "publication",
            ],
        )

        self.assertTrue(
            result.release_path.is_dir()
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

        with lock_path.open("r+b") as contender:
            fcntl.flock(
                contender.fileno(),
                (
                    fcntl.LOCK_EX
                    | fcntl.LOCK_NB
                ),
            )

            fcntl.flock(
                contender.fileno(),
                fcntl.LOCK_UN,
            )

    def test_refresh_lock_is_held_during_failed_candidate_cleanup(
        self,
    ) -> None:
        lock_path = (
            self.deployment_root
            / ".refresh.lock"
        )

        candidate_path = (
            self.candidates_path
            / EXPECTED_CANDIDATE_ID
        )

        observations: list[str] = []

        real_cleanup = (
            live_refresh._remove_failed_candidate
        )

        def failing_build(
            document: CatalogDocument,
            output_dir: Path,
            *,
            as_of: date | None,
            top_vendors: int,
            queue_limit: int,
        ) -> BuildResult:
            raise RuntimeError(
                "synthetic build failure"
            )

        def observing_cleanup(
            failed_candidate_path: Path,
            candidates_path: Path,
            *,
            original_error: Exception,
        ) -> None:
            self.observe_refresh_lock_held(
                lock_path,
                "cleanup",
                observations,
            )

            real_cleanup(
                failed_candidate_path,
                candidates_path,
                original_error=original_error,
            )

        with (
            patch(
                "kev_dashboard.live_refresh.uuid4",
                return_value=FIXED_UUID,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "fetch_live_json"
                ),
                return_value=self.document,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "pipeline.build_dashboard"
                ),
                side_effect=failing_build,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "_remove_failed_candidate"
                ),
                side_effect=observing_cleanup,
            ),
            patch(
                (
                    "kev_dashboard.live_refresh."
                    "publication.publish_candidate"
                )
            ) as mocked_publication,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "synthetic build failure",
            ):
                refresh_live_dashboard(
                    self.deployment_root,
                    now=self.now,
                )

        self.assertEqual(
            observations,
            [
                "cleanup",
            ],
        )

        mocked_publication.assert_not_called()

        self.assertFalse(
            os.path.lexists(candidate_path)
        )

        self.assertTrue(
            lock_path.is_file()
        )

        with lock_path.open("r+b") as contender:
            fcntl.flock(
                contender.fileno(),
                (
                    fcntl.LOCK_EX
                    | fcntl.LOCK_NB
                ),
            )

            fcntl.flock(
                contender.fileno(),
                fcntl.LOCK_UN,
            )


if __name__ == "__main__":
    unittest.main()
