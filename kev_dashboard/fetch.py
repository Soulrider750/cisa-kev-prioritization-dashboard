"""Safe local and remote loading for CISA KEV JSON data."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import __version__


DEFAULT_FEED_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/"
    "known_exploited_vulnerabilities.json"
)

ALLOWED_FEED_HOSTS = frozenset(
    {
        "www.cisa.gov",
    }
)

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_FEED_BYTES = 25 * 1024 * 1024

USER_AGENT = (
    f"cisa-kev-prioritization-dashboard/{__version__}"
)


class CatalogLoadError(ValueError):
    """Raised when a KEV source cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class CatalogDocument:
    """Decoded JSON plus evidence describing its source."""

    payload: dict[str, Any]
    raw_bytes: bytes
    source: str
    retrieved_at: datetime
    sha256_digest: str


def _validate_feed_url(
    url: str,
    allowed_hosts: Collection[str],
) -> None:
    """Require an approved HTTPS destination."""

    if not isinstance(url, str) or not url.strip():
        raise CatalogLoadError(
            "feed URL must be a non-empty string"
        )

    parsed = urlparse(url)

    if parsed.scheme.casefold() != "https":
        raise CatalogLoadError(
            "feed URL must use HTTPS"
        )

    if parsed.username is not None or parsed.password is not None:
        raise CatalogLoadError(
            "feed URL must not contain credentials"
        )

    host = (parsed.hostname or "").casefold()

    normalized_hosts = {
        allowed_host.casefold()
        for allowed_host in allowed_hosts
    }

    if host not in normalized_hosts:
        raise CatalogLoadError(
            f"feed host is not approved: {host or 'missing host'}"
        )

    try:
        port = parsed.port
    except ValueError as error:
        raise CatalogLoadError(
            "feed URL contains an invalid port"
        ) from error

    if port not in (None, 443):
        raise CatalogLoadError(
            "feed URL must use the default HTTPS port"
        )


def _document_from_bytes(
    raw_bytes: bytes,
    *,
    source: str,
) -> CatalogDocument:
    """Decode JSON and preserve source evidence."""

    try:
        decoded_text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CatalogLoadError(
            f"{source}: response is not valid UTF-8"
        ) from error

    try:
        payload = json.loads(decoded_text)
    except json.JSONDecodeError as error:
        raise CatalogLoadError(
            f"{source}: response is not valid JSON"
        ) from error

    if not isinstance(payload, dict):
        raise CatalogLoadError(
            f"{source}: top-level JSON value must be an object"
        )

    return CatalogDocument(
        payload=payload,
        raw_bytes=raw_bytes,
        source=source,
        retrieved_at=datetime.now(timezone.utc),
        sha256_digest=sha256(raw_bytes).hexdigest(),
    )


def load_local_json(
    path: Path,
    *,
    max_bytes: int = MAX_FEED_BYTES,
) -> CatalogDocument:
    """Load a bounded local JSON document."""

    if max_bytes < 1:
        raise ValueError(
            "max_bytes must be greater than zero"
        )

    try:
        declared_size = path.stat().st_size
    except OSError as error:
        raise CatalogLoadError(
            f"could not inspect local file {path}: {error}"
        ) from error

    if declared_size > max_bytes:
        raise CatalogLoadError(
            f"local file exceeds the {max_bytes}-byte limit"
        )

    try:
        raw_bytes = path.read_bytes()
    except OSError as error:
        raise CatalogLoadError(
            f"could not read local file {path}: {error}"
        ) from error

    if len(raw_bytes) > max_bytes:
        raise CatalogLoadError(
            f"local file exceeds the {max_bytes}-byte limit"
        )

    return _document_from_bytes(
        raw_bytes,
        source=str(path),
    )


def fetch_live_json(
    url: str = DEFAULT_FEED_URL,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_FEED_BYTES,
    allowed_hosts: Collection[str] = ALLOWED_FEED_HOSTS,
) -> CatalogDocument:
    """Retrieve a bounded JSON document from an approved HTTPS host."""

    if timeout <= 0:
        raise ValueError(
            "timeout must be greater than zero"
        )

    if max_bytes < 1:
        raise ValueError(
            "max_bytes must be greater than zero"
        )

    _validate_feed_url(url, allowed_hosts)

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            final_url = response.geturl()

            # urllib follows redirects automatically. Validate the final
            # destination so an approved URL cannot redirect elsewhere.
            _validate_feed_url(
                final_url,
                allowed_hosts,
            )

            content_length = response.headers.get(
                "Content-Length"
            )

            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except (TypeError, ValueError) as error:
                    raise CatalogLoadError(
                        "server returned an invalid "
                        "Content-Length header"
                    ) from error

                if declared_size < 0:
                    raise CatalogLoadError(
                        "server returned a negative "
                        "Content-Length header"
                    )

                if declared_size > max_bytes:
                    raise CatalogLoadError(
                        "remote response exceeds the "
                        f"{max_bytes}-byte limit"
                    )

            raw_bytes = response.read(max_bytes + 1)

    except CatalogLoadError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise CatalogLoadError(
            f"could not retrieve {url}: {error}"
        ) from error

    if len(raw_bytes) > max_bytes:
        raise CatalogLoadError(
            "remote response exceeds the "
            f"{max_bytes}-byte limit"
        )

    return _document_from_bytes(
        raw_bytes,
        source=final_url,
    )