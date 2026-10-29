"""Tests for safe local and remote KEV loading."""

from email.message import Message
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.request import (
    HTTPHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)
from urllib.response import addinfourl

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


class FakeOpener:
    """Return one prepared response while recording the open call."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[Request, float]] = []

    def open(self, request: Request, *, timeout: float) -> FakeResponse:
        self.calls.append((request, timeout))
        return self.response


class RecordingTransport:
    """Model HTTP responses without making network requests."""

    def __init__(
        self,
        body: bytes,
        *,
        redirect_status: int | None = None,
        redirect_location: str | None = None,
    ) -> None:
        self.body = body
        self.redirect_status = redirect_status
        self.redirect_location = redirect_location
        self.requests: list[Request] = []

    def respond(self, request: Request):
        self.requests.append(request)
        headers = Message()

        if self.redirect_status is not None and len(self.requests) == 1:
            headers["Location"] = self.redirect_location or ""
            response = addinfourl(
                BytesIO(b""),
                headers,
                request.full_url,
                self.redirect_status,
            )
            response.msg = "Redirect"
            return response

        headers["Content-Length"] = str(len(self.body))
        response = addinfourl(
            BytesIO(self.body),
            headers,
            request.full_url,
            200,
        )
        response.msg = "OK"
        return response


class RecordingHTTPSHandler(HTTPSHandler):
    def __init__(self, transport: RecordingTransport) -> None:
        super().__init__()
        self.transport = transport

    def https_open(self, request: Request):
        return self.transport.respond(request)


class RecordingHTTPHandler(HTTPHandler):
    def __init__(self, transport: RecordingTransport) -> None:
        super().__init__()
        self.transport = transport

    def http_open(self, request: Request):
        return self.transport.respond(request)


def _recording_opener_factory(transport: RecordingTransport):
    def factory(*handlers):
        return build_opener(
            ProxyHandler({}),
            RecordingHTTPSHandler(transport),
            RecordingHTTPHandler(transport),
            *handlers,
        )

    return factory


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
        fake_opener = FakeOpener(fake_response)

        with patch(
            "kev_dashboard.fetch.build_opener",
            return_value=fake_opener,
        ):
            document = fetch_live_json(timeout=5.0)

        self.assertEqual(document.raw_bytes, fixture_bytes)
        self.assertEqual(document.payload["count"], 6)
        self.assertEqual(document.source, DEFAULT_FEED_URL)
        self.assertEqual(
            document.sha256_digest,
            sha256(fixture_bytes).hexdigest(),
        )

        self.assertEqual(len(fake_opener.calls), 1)
        request, timeout = fake_opener.calls[0]

        self.assertEqual(request.full_url, DEFAULT_FEED_URL)
        self.assertEqual(
            request.get_header("Accept"),
            "application/json",
        )
        self.assertEqual(timeout, 5.0)

    def test_unapproved_response_url_is_rejected(self) -> None:
        fixture_bytes = FIXTURE_PATH.read_bytes()

        fake_response = FakeResponse(
            fixture_bytes,
            final_url="https://example.com/catalog.json",
        )

        with patch(
            "kev_dashboard.fetch.build_opener",
            return_value=FakeOpener(fake_response),
        ):
            with self.assertRaisesRegex(
                CatalogLoadError,
                "feed host is not approved",
            ):
                fetch_live_json()

    def test_direct_response_through_redirect_guard(self) -> None:
        fixture_bytes = FIXTURE_PATH.read_bytes()
        transport = RecordingTransport(fixture_bytes)

        with patch(
            "kev_dashboard.fetch.build_opener",
            side_effect=_recording_opener_factory(transport),
        ):
            document = fetch_live_json()

        self.assertEqual(document.raw_bytes, fixture_bytes)
        self.assertEqual(document.source, DEFAULT_FEED_URL)
        self.assertEqual(
            [request.full_url for request in transport.requests],
            [DEFAULT_FEED_URL],
        )

    def test_direct_approved_alternate_url_still_works(self) -> None:
        alternate_url = "https://www.cisa.gov/other.json"
        transport = RecordingTransport(FIXTURE_PATH.read_bytes())

        with patch(
            "kev_dashboard.fetch.build_opener",
            side_effect=_recording_opener_factory(transport),
        ):
            document = fetch_live_json(alternate_url)

        self.assertEqual(document.source, alternate_url)
        self.assertEqual(
            [request.full_url for request in transport.requests],
            [alternate_url],
        )

    def test_redirects_are_rejected_before_follow_up_request(self) -> None:
        redirect_cases = (
            (301, "https://example.com/other.json"),
            (302, "http://www.cisa.gov/other.json"),
            (303, "//example.com/other.json"),
            (307, "https://www.cisa.gov/other.json"),
            (308, "/other.json"),
        )

        for status, location in redirect_cases:
            with self.subTest(status=status, location=location):
                transport = RecordingTransport(
                    b"{}",
                    redirect_status=status,
                    redirect_location=location,
                )

                with patch(
                    "kev_dashboard.fetch.build_opener",
                    side_effect=_recording_opener_factory(transport),
                ):
                    with self.assertRaisesRegex(
                        CatalogLoadError,
                        "feed redirects are not permitted",
                    ):
                        fetch_live_json()

                self.assertEqual(
                    [request.full_url for request in transport.requests],
                    [DEFAULT_FEED_URL],
                )

    def test_oversized_content_length_is_rejected(self) -> None:
        fake_response = FakeResponse(
            b"{}",
            content_length=1_000,
        )

        with patch(
            "kev_dashboard.fetch.build_opener",
            return_value=FakeOpener(fake_response),
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
            "kev_dashboard.fetch.build_opener",
            return_value=FakeOpener(fake_response),
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
            "kev_dashboard.fetch.build_opener",
            return_value=FakeOpener(fake_response),
        ):
            with self.assertRaisesRegex(
                CatalogLoadError,
                "response is not valid JSON",
            ):
                fetch_live_json()


if __name__ == "__main__":
    unittest.main()
