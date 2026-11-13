"""Exercise worker publication against an isolated scratch volume."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
from unittest.mock import patch

from kev_dashboard.fetch import (
    CatalogLoadError,
    DEFAULT_FEED_URL,
    load_local_json,
)
from kev_dashboard.live_refresh import refresh_live_dashboard


FIXTURE = Path(__file__).parent / "fixtures" / "kev_sample.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(deployment_root: Path) -> None:
    require(
        not os.path.lexists(deployment_root / "current"),
        "scratch deployment already has a current release",
    )

    deployment_root.mkdir(mode=0o750, parents=True, exist_ok=True)
    (deployment_root / "candidates").mkdir(mode=0o700, exist_ok=True)
    (deployment_root / "releases").mkdir(mode=0o750, exist_ok=True)

    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    document = replace(
        load_local_json(FIXTURE),
        source=DEFAULT_FEED_URL,
        retrieved_at=now - timedelta(minutes=5),
    )

    with patch(
        "kev_dashboard.live_refresh.fetch_live_json",
        return_value=document,
    ):
        first = refresh_live_dashboard(deployment_root, now=now)

    current = deployment_root / "current"
    require(current.is_symlink(), "initial refresh did not activate a release")
    require(
        current.resolve(strict=True) == first.release_path,
        "active release does not match the published release",
    )

    snapshot = current / "data" / "kev_snapshot.json"
    original_snapshot = snapshot.read_bytes()
    original_target = current.readlink()
    original_releases = tuple(sorted(
        path.name for path in (deployment_root / "releases").iterdir()
    ))
    require((current / "search.html").is_file(), "search page is missing")
    require((current / "search.js").is_file(), "search script is missing")

    with patch(
        "kev_dashboard.live_refresh.fetch_live_json",
        side_effect=CatalogLoadError("redirect rejected in acceptance test"),
    ):
        try:
            refresh_live_dashboard(
                deployment_root,
                now=now + timedelta(minutes=1),
            )
        except CatalogLoadError:
            pass
        else:
            raise AssertionError("failed fetch unexpectedly published a release")

    require(current.readlink() == original_target, "active release changed")
    require(snapshot.read_bytes() == original_snapshot, "snapshot changed")
    require(
        tuple(sorted(
            path.name for path in (deployment_root / "releases").iterdir()
        )) == original_releases,
        "failed refresh created a release",
    )
    require(
        not any((deployment_root / "candidates").iterdir()),
        "failed refresh left a candidate",
    )
    print("PASS: worker preserved the active scratch release")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: worker_image_acceptance.py DEPLOYMENT_ROOT")
    main(Path(sys.argv[1]))
