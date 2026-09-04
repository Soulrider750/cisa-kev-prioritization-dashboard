"""Tests for safe local and remote KEV loading."""

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from kev_dashboard.fetch import (
    CatalogLoadError,
    DEFAULT_FEED_URL,
    fetch_live_json,
    load_local_json,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kev_sample.json"


class FakeResponse:
    """Small context-manager replacement for an HTTP response."""

    def __init__(
        self,
        body: bytes,
        *,
        final_url: str = DEFAULT_FEED_URL,
        content_length: int | str | None = None,
    ) -> None:
        self._body = body
        self._final_url = final_url
        self.headers: dict[str, str] = {}

        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(
        self,
        exception_type,
        exception,
        traceback,
    ) -> bool:
        return False

    def geturl(self) -> str:
        return self._final_url

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self._body

        return self._body[:size]


class FetchTests(unittest.TestCase):
    """Verify local loading and bounded HTTPS retrieval."""

    def test_local_loader_preserves_bytes_and_metadata(self) -> None:
        expected_bytes = FIXTURE_PATH.read_bytes()

        document = load_local_json(FIXTURE_PATH)

        self.assertEqual(document.raw_bytes, expected_bytes)
        self.assertEqual(document.payload["count"], 6)
        self.assertEqual(document.source, str(FIXTURE_PATH))
        self.assertEqual(
            document.sha256_digest,
            sha256(expected_bytes).hexdigest(),
        )
        self.assertIsNotNone(document.retrieved_at.tzinfo)

    def test_local_top_level_array_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "array.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(
                CatalogLoadError,
                "top-level JSON value must be an object",
            ):
                load_local_json(path)

    def test_invalid_local_json_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "invalid.json"
            path.write_text("{not valid json", encoding="utf-8")

            with self.assertRaisesRegex(
                CatalogLoadError,
                "response is not valid JSON",
            ):
                load_local_json(path)

    def test_oversized_local_file_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            CatalogLoadError,
            "local file exceeds",
        ):
            load_local_json(
                FIXTURE_PATH,
                max_bytes=10,
            )

    def test_http_url_is_rejected(self) -> None:
        unsafe_url = (
            "http://www.cisa.gov/example.json"
        )

        with self.assertRaisesRegex(
            CatalogLoadError,
            "must use HTTPS",
        ):
            fetch_live_json(unsafe_url)

    def test_unapproved_host_is_rejected(self) -> None:
        unapproved_url = (
            "https://example.com/catalog.json"
        )

        with self.assertRaisesRegex(
            CatalogLoadError,
            "feed host is not approved",
        ):
            fetch_live_json(unapproved_url)

    def test_live_fetch_returns_document(self) -> None:
        fixture_bytes = FIXTURE_PATH.read_bytes()

        fake_response = FakeResponse(
            fixture_bytes,
            content_length=len(fixture_bytes),
        )

        with patch(
            "kev_dashboard.fetch.urlopen",
            return_value=fake_response,
        ) as mocked_urlopen:
            document = fetch_live_json(timeout=5.0)

        self.assertEqual(document.raw_bytes, fixture_bytes)
        self.assertEqual(document.payload["count"], 6)
        self.assertEqual(document.source, DEFAULT_FEED_URL)
        self.assertEqual(
            document.sha256_digest,
            sha256(fixture_bytes).hexdigest(),
        )

        request = mocked_urlopen.call_args.args[0]
        timeout = mocked_urlopen.call_args.kwargs["timeout"]

        self.assertEqual(request.full_url, DEFAULT_FEED_URL)
        self.assertEqual(
            request.get_header("Accept"),
            "application/json",
        )
        self.assertEqual(timeout, 5.0)

    def test_redirect_to_unapproved_host_is_rejected(self) -> None:
        fixture_bytes = FIXTURE_PATH.read_bytes()

        fake_response = FakeResponse(
            fixture_bytes,
            final_url="https://example.com/catalog.json",
        )

        with patch(
            "kev_dashboard.fetch.urlopen",
            return_value=fake_response,
        ):
            with self.assertRaisesRegex(
                CatalogLoadError,
                "feed host is not approved",
            ):
                fetch_live_json()

    def test_oversized_content_length_is_rejected(self) -> None:
        fake_response = FakeResponse(
            b"{}",
            content_length=1_000,
        )

        with patch(
            "kev_dashboard.fetch.urlopen",
            return_value=fake_response,
        ):
            with self.assertRaisesRegex(
                CatalogLoadError,
                "remote response exceeds",
            ):
                fetch_live_json(max_bytes=100)

    def test_oversized_body_is_rejected(self) -> None:
        fake_response = FakeResponse(
            b"x" * 101,
        )

        with patch(
            "kev_dashboard.fetch.urlopen",
            return_value=fake_response,
        ):
            with self.assertRaisesRegex(
                CatalogLoadError,
                "remote response exceeds",
            ):
                fetch_live_json(max_bytes=100)

    def test_invalid_remote_json_is_rejected(self) -> None:
        fake_response = FakeResponse(
            b"{not valid json",
        )

        with patch(
            "kev_dashboard.fetch.urlopen",
            return_value=fake_response,
        ):
            with self.assertRaisesRegex(
                CatalogLoadError,
                "response is not valid JSON",
            ):
                fetch_live_json()


if __name__ == "__main__":
    unittest.main()