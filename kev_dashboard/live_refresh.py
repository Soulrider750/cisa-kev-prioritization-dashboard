"""One-shot orchestration for live dashboard refreshes."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import errno
import fcntl
import os
from pathlib import Path
import shutil
import stat
from uuid import uuid4
from zoneinfo import ZoneInfo

from . import pipeline
from . import publication
from .fetch import (
    DEFAULT_FEED_URL,
    DEFAULT_TIMEOUT_SECONDS,
    fetch_live_json,
)


DEFAULT_LIVE_MAX_AGE = timedelta(
    hours=1
)

LIVE_ANALYSIS_TIME_ZONE = ZoneInfo(
    "America/New_York"
)


class LiveRefreshError(ValueError):
    """Raised when live refresh orchestration cannot proceed."""


class LiveRefreshBusyError(LiveRefreshError):
    """Raised when another live refresh is already running."""


@dataclass(frozen=True, slots=True)
class LiveRefreshResult:
    """Evidence from one successful live refresh."""

    candidate_id: str
    source: str
    analysis_date: str
    record_count: int
    release_id: str
    release_path: Path
    current_path: Path
    previous_release_id: str | None


def _validate_refresh_lock_status(
    lock_status: os.stat_result,
) -> None:
    """Require a private, owned, single-link regular lock file."""

    if not stat.S_ISREG(
        lock_status.st_mode
    ):
        raise LiveRefreshError(
            "live refresh lock must be a regular file"
        )

    if lock_status.st_uid != os.geteuid():
        raise LiveRefreshError(
            "live refresh lock must be owned "
            "by the current user"
        )

    if lock_status.st_nlink != 1:
        raise LiveRefreshError(
            "live refresh lock must have "
            "exactly one link"
        )


@contextmanager
def _refresh_lock(
    deployment_root: Path,
) -> Iterator[None]:
    """Hold the exclusive whole-refresh lock."""

    lock_path = (
        deployment_root / ".refresh.lock"
    )

    try:
        existing_status = os.lstat(
            lock_path
        )
    except FileNotFoundError:
        pass
    except OSError as error:
        raise LiveRefreshError(
            "could not inspect live refresh lock"
        ) from error
    else:
        if stat.S_ISLNK(
            existing_status.st_mode
        ):
            raise LiveRefreshError(
                "live refresh lock must not be "
                "a symbolic link"
            )

        _validate_refresh_lock_status(
            existing_status
        )

    try:
        open_flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_CLOEXEC
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
        )
    except AttributeError:
        raise LiveRefreshError(
            "secure live refresh locking "
            "is not supported"
        ) from None

    try:
        lock_descriptor = os.open(
            lock_path,
            open_flags,
            0o600,
        )
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise LiveRefreshError(
                "live refresh lock must not be "
                "a symbolic link"
            ) from error

        try:
            failed_status = os.lstat(
                lock_path
            )
        except OSError:
            pass
        else:
            if stat.S_ISLNK(
                failed_status.st_mode
            ):
                raise LiveRefreshError(
                    "live refresh lock must not be "
                    "a symbolic link"
                ) from error

            if not stat.S_ISREG(
                failed_status.st_mode
            ):
                raise LiveRefreshError(
                    "live refresh lock must be "
                    "a regular file"
                ) from error

        raise LiveRefreshError(
            "could not open live refresh lock"
        ) from error

    try:
        try:
            opened_status = os.fstat(
                lock_descriptor
            )
        except OSError as error:
            raise LiveRefreshError(
                "could not inspect live refresh lock"
            ) from error

        _validate_refresh_lock_status(
            opened_status
        )

        try:
            fcntl.flock(
                lock_descriptor,
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
                raise LiveRefreshBusyError(
                    "live refresh already in progress"
                ) from error

            raise LiveRefreshError(
                "could not acquire live refresh lock"
            ) from error

        try:
            named_status = os.lstat(
                lock_path
            )
        except OSError as error:
            raise LiveRefreshError(
                "could not verify live refresh lock"
            ) from error

        if stat.S_ISLNK(
            named_status.st_mode
        ):
            raise LiveRefreshError(
                "live refresh lock must not be "
                "a symbolic link"
            )

        _validate_refresh_lock_status(
            named_status
        )

        if (
            named_status.st_dev
            != opened_status.st_dev
            or named_status.st_ino
            != opened_status.st_ino
        ):
            raise LiveRefreshError(
                "live refresh lock changed "
                "while opening"
            )

        try:
            os.fchmod(
                lock_descriptor,
                0o600,
            )

            secured_status = os.fstat(
                lock_descriptor
            )
        except OSError as error:
            raise LiveRefreshError(
                "could not secure live refresh lock"
            ) from error

        if (
            stat.S_IMODE(
                secured_status.st_mode
            )
            != 0o600
        ):
            raise LiveRefreshError(
                "could not secure live refresh lock"
            )

        yield None
    finally:
        try:
            os.close(
                lock_descriptor
            )
        except OSError:
            pass


def _require_aware_datetime(
    value: datetime,
    description: str,
) -> datetime:
    """Require one timezone-aware datetime."""

    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise LiveRefreshError(
            f"{description} must be timezone-aware"
        )

    return value


def _require_real_directory(
    path: Path,
    description: str,
    *,
    private: bool = False,
) -> os.stat_result:
    """Require a trusted, owned, real directory."""

    try:
        directory_status = os.lstat(path)
    except FileNotFoundError:
        raise LiveRefreshError(
            f"{description} must be a directory"
        ) from None
    except OSError as error:
        raise LiveRefreshError(
            f"could not inspect {description}"
        ) from error

    if stat.S_ISLNK(directory_status.st_mode):
        raise LiveRefreshError(
            f"{description} must not be a symbolic link"
        )

    if not stat.S_ISDIR(directory_status.st_mode):
        raise LiveRefreshError(
            f"{description} must be a directory"
        )

    if directory_status.st_uid != os.geteuid():
        raise LiveRefreshError(
            f"{description} must be owned by the current user"
        )

    mode = stat.S_IMODE(
        directory_status.st_mode
    )

    if private:
        if mode != 0o700:
            raise LiveRefreshError(
                f"{description} permissions must be 0700"
            )
    elif mode & 0o022:
        raise LiveRefreshError(
            f"{description} must not be "
            "group- or world-writable"
        )

    return directory_status


def _remove_failed_candidate(
    candidate_path: Path,
    candidates_path: Path,
    *,
    original_error: Exception,
) -> None:
    """Remove only the candidate created by the failed refresh."""

    if (
        candidate_path.parent != candidates_path
        or not candidate_path.name.startswith(
            "candidate-"
        )
    ):
        raise LiveRefreshError(
            "candidate cleanup path is invalid"
        ) from original_error

    try:
        candidate_status = os.lstat(
            candidate_path
        )
    except FileNotFoundError:
        return
    except OSError as cleanup_error:
        raise LiveRefreshError(
            "refresh failed and candidate cleanup "
            "failed; candidate remains at "
            f"{candidate_path}: {cleanup_error}"
        ) from original_error

    try:
        if stat.S_ISDIR(
            candidate_status.st_mode
        ):
            shutil.rmtree(
                candidate_path
            )
        else:
            candidate_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as cleanup_error:
        raise LiveRefreshError(
            "refresh failed and candidate cleanup "
            "failed; candidate remains at "
            f"{candidate_path}: {cleanup_error}"
        ) from original_error

    if os.path.lexists(candidate_path):
        raise LiveRefreshError(
            "refresh failed and candidate cleanup "
            "failed; candidate remains at "
            f"{candidate_path}"
        ) from original_error


def refresh_live_dashboard(
    deployment_root: Path,
    *,
    now: datetime,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_age: timedelta = DEFAULT_LIVE_MAX_AGE,
    top_vendors: int = 10,
    queue_limit: int = 20,
) -> LiveRefreshResult:
    """Fetch, build, validate, and publish one live dashboard."""

    deployment_root = Path(
        deployment_root
    )

    now = _require_aware_datetime(
        now,
        "now",
    )

    candidates_path = (
        deployment_root / "candidates"
    )

    releases_path = (
        deployment_root / "releases"
    )

    root_status = _require_real_directory(
        deployment_root,
        "deployment root",
    )

    candidates_status = _require_real_directory(
        candidates_path,
        "candidates directory",
        private=True,
    )

    releases_status = _require_real_directory(
        releases_path,
        "releases directory",
    )

    if (
        candidates_status.st_dev
        != root_status.st_dev
        or releases_status.st_dev
        != root_status.st_dev
    ):
        raise LiveRefreshError(
            "deployment directories must be "
            "on the same filesystem"
        )

    with _refresh_lock(
        deployment_root
    ):
        candidate_id = (
            f"candidate-{uuid4().hex}"
        )

        candidate_path = (
            candidates_path / candidate_id
        )

        if os.path.lexists(candidate_path):
            raise LiveRefreshError(
                "candidate path already exists"
            )

        document = fetch_live_json(
            DEFAULT_FEED_URL,
            timeout=timeout,
        )

        retrieved_at = _require_aware_datetime(
            document.retrieved_at,
            "retrieved_at",
        )

        try:
            candidate_path.mkdir(
                mode=0o700,
                parents=False,
                exist_ok=False,
            )
        except FileExistsError as error:
            raise LiveRefreshError(
                "candidate path already exists"
            ) from error

        try:
            analysis_date = (
                retrieved_at.astimezone(
                    LIVE_ANALYSIS_TIME_ZONE
                ).date()
            )

            build_result = pipeline.build_dashboard(
                document,
                candidate_path,
                as_of=analysis_date,
                top_vendors=top_vendors,
                queue_limit=queue_limit,
            )

            publication_result = (
                publication.publish_candidate(
                    deployment_root,
                    candidate_id,
                    now=now,
                    max_age=max_age,
                )
            )

        except Exception as error:
            _remove_failed_candidate(
                candidate_path,
                candidates_path,
                original_error=error,
            )

            raise

        return LiveRefreshResult(
            candidate_id=candidate_id,
            source=build_result.source,
            analysis_date=(
                build_result.analysis_date
            ),
            record_count=build_result.record_count,
            release_id=(
                publication_result.release_id
            ),
            release_path=(
                publication_result.release_path
            ),
            current_path=(
                publication_result.current_path
            ),
            previous_release_id=(
                publication_result.previous_release_id
            ),
        )
