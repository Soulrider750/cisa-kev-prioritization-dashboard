"""Transactional publication of validated dashboard builds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from . import build_validation
from . import deployment_policy


_CANDIDATE_ID_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
)

_RELEASE_ID_PATTERN = re.compile(
    r"\d{8}T\d{12}Z-[0-9a-f]{16}"
)

_SHA256_PATTERN = re.compile(
    r"[0-9a-f]{64}"
)


class PublicationError(ValueError):
    """Raised when a candidate cannot be safely published."""


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Paths and identifiers from one successful publication."""

    release_id: str
    release_path: Path
    current_path: Path
    previous_release_id: str | None


def _require_real_directory(
    path: Path,
    description: str,
) -> None:
    """Require an existing directory that is not a symbolic link."""

    if path.is_symlink():
        raise PublicationError(
            f"{description} must not be a symbolic link"
        )

    if not path.is_dir():
        raise PublicationError(
            f"{description} must be a directory"
        )


def _read_previous_release_id(
    deployment_root: Path,
    current_path: Path,
) -> str | None:
    """Return the release selected by the current symbolic link."""

    if not os.path.lexists(current_path):
        return None

    if not current_path.is_symlink():
        raise PublicationError(
            "current must be a symbolic link"
        )

    try:
        target_text = os.readlink(current_path)
    except OSError as error:
        raise PublicationError(
            "could not read current symbolic link"
        ) from error

    target = Path(target_text)

    if (
        target.is_absolute()
        or len(target.parts) != 2
        or target.parts[0] != "releases"
    ):
        raise PublicationError(
            "current symbolic link target is invalid"
        )

    release_id = target.parts[1]

    expected_target = (
        Path("releases") / release_id
    ).as_posix()

    if (
        target_text != expected_target
        or _RELEASE_ID_PATTERN.fullmatch(
            release_id
        )
        is None
    ):
        raise PublicationError(
            "current symbolic link target is invalid"
        )

    previous_release_path = (
        deployment_root / target
    )

    if (
        previous_release_path.is_symlink()
        or not previous_release_path.is_dir()
    ):
        raise PublicationError(
            "current symbolic link target is invalid"
        )

    return release_id


def _read_candidate_metadata(
    candidate_path: Path,
) -> tuple[str, datetime, str]:
    """Read publication inputs from validated candidate metadata."""

    metadata_path = (
        candidate_path
        / "data"
        / "metadata.json"
    )

    try:
        metadata = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(metadata, dict):
            raise TypeError

        source = metadata["source"]
        retrieved_at_text = metadata[
            "retrieved_at"
        ]
        snapshot_sha256 = metadata[
            "snapshot_sha256"
        ]

        if (
            not isinstance(source, str)
            or not isinstance(
                retrieved_at_text,
                str,
            )
            or not isinstance(
                snapshot_sha256,
                str,
            )
        ):
            raise TypeError

        retrieved_at = datetime.fromisoformat(
            retrieved_at_text
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        raise PublicationError(
            "could not read validated candidate metadata"
        ) from None

    if (
        _SHA256_PATTERN.fullmatch(
            snapshot_sha256
        )
        is None
    ):
        raise PublicationError(
            "could not read validated candidate metadata"
        )

    return (
        source,
        retrieved_at,
        snapshot_sha256,
    )


def _discard_temporary_link(
    path: Path,
) -> None:
    """Best-effort removal of a temporary activation link."""

    try:
        path.unlink()
    except OSError:
        pass


def publish_candidate(
    deployment_root: Path,
    candidate_id: str,
    *,
    now: datetime,
    max_age: timedelta,
) -> PublicationResult:
    """Validate, authorize, and atomically publish one candidate."""

    if (
        not isinstance(candidate_id, str)
        or _CANDIDATE_ID_PATTERN.fullmatch(
            candidate_id
        )
        is None
    ):
        raise PublicationError(
            "invalid candidate identifier"
        )

    deployment_root = Path(
        deployment_root
    )

    candidates_path = (
        deployment_root / "candidates"
    )
    releases_path = (
        deployment_root / "releases"
    )
    candidate_path = (
        candidates_path / candidate_id
    )
    current_path = (
        deployment_root / "current"
    )

    _require_real_directory(
        deployment_root,
        "deployment root",
    )
    _require_real_directory(
        candidates_path,
        "candidates directory",
    )
    _require_real_directory(
        releases_path,
        "releases directory",
    )

    previous_release_id = (
        _read_previous_release_id(
            deployment_root,
            current_path,
        )
    )

    _require_real_directory(
        candidate_path,
        "candidate",
    )

    try:
        build_validation.validate_build(
            candidate_path
        )
    except (
        build_validation.BuildValidationError,
        OSError,
    ) as error:
        raise PublicationError(
            "candidate build validation failed: "
            f"{error}"
        ) from error

    (
        source,
        retrieved_at,
        snapshot_sha256,
    ) = _read_candidate_metadata(
        candidate_path
    )

    try:
        policy_result = (
            deployment_policy.evaluate_deployment_policy(
                source=source,
                retrieved_at=retrieved_at,
                now=now,
                max_age=max_age,
            )
        )
    except (
        deployment_policy.DeploymentPolicyError
    ) as error:
        raise PublicationError(
            "candidate failed deployment policy: "
            f"{error}"
        ) from error

    timestamp = (
        policy_result.retrieved_at.strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    release_id = (
        f"{timestamp}-"
        f"{snapshot_sha256[:16]}"
    )

    release_path = (
        releases_path / release_id
    )

    if os.path.lexists(release_path):
        raise PublicationError(
            "release already exists"
        )

    relative_target = (
        Path("releases") / release_id
    )

    temporary_current_path = (
        deployment_root
        / f".current-{uuid4().hex}.tmp"
    )

    try:
        temporary_current_path.symlink_to(
            relative_target,
            target_is_directory=True,
        )
    except OSError as error:
        raise PublicationError(
            "could not prepare current symbolic link"
        ) from error

    try:
        candidate_path.rename(
            release_path
        )
    except OSError as error:
        _discard_temporary_link(
            temporary_current_path
        )

        raise PublicationError(
            "could not create release"
        ) from error

    try:
        os.replace(
            temporary_current_path,
            current_path,
        )
    except OSError as switch_error:
        _discard_temporary_link(
            temporary_current_path
        )

        try:
            release_path.rename(
                candidate_path
            )
        except OSError as rollback_error:
            raise PublicationError(
                "could not activate release and "
                "could not restore candidate"
            ) from rollback_error

        raise PublicationError(
            "could not activate release"
        ) from switch_error

    return PublicationResult(
        release_id=release_id,
        release_path=release_path,
        current_path=current_path,
        previous_release_id=(
            previous_release_id
        ),
    )
