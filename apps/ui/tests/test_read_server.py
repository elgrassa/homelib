"""Clean /read helpers — Safari Listen to Page companion on :8502."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import httpx
import pytest
import respx

from apps.ui.read_html import ReadPage, build_read_article_html
from apps.ui.read_server import (
    DEFAULT_API,
    DEFAULT_PORT,
    ReadHandler,
    _api_base,
    _fetch_block,
    _fetch_book_title,
    main,
)
from apps.ui.view_model import OfficialPreviewBook

POTTERMORE_PDF_URL = (
    "https://www.pottermorepublishing.com/wp-content/uploads/9781789391725_HP1_Ukrainian_v5.pdf"
)


def test_api_base_prefers_read_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", "http://read-api:8000/")
    monkeypatch.delenv("API_URL", raising=False)
    assert _api_base() == "http://read-api:8000"


def test_api_base_falls_back_to_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("READ_API_URL", raising=False)
    monkeypatch.setenv("API_URL", "http://api:9000")
    assert _api_base() == "http://api:9000"


def test_read_html_includes_previous_when_ordinal_allows() -> None:
    doc = build_read_article_html(
        ReadPage(
            book_id="walden",
            title="Walden",
            authors="Thoreau",
            ordinal=2,
            text="page three",
            prev_ordinal=1,
            next_ordinal=None,
        )
    )
    assert 'href="/read/walden?ordinal=1"' in doc
    assert "Next" not in doc


@respx.mock
def test_fetch_block_returns_page_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books/walden/blocks").mock(
        return_value=httpx.Response(
            200,
            json={"block_id": "b0", "book_id": "walden", "ordinal": 0, "text": "woods"},
        )
    )
    assert _fetch_block("walden", 0)["text"] == "woods"


@respx.mock
def test_fetch_block_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books/missing/blocks").mock(
        return_value=httpx.Response(404, json={"detail": "missing@0"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        _fetch_block("missing", 0)


@respx.mock
def test_fetch_book_title_resolves_catalog_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books").mock(
        return_value=httpx.Response(
            200,
            json=[{"book_id": "walden", "title": "Walden", "authors": ["Thoreau"]}],
        )
    )
    assert _fetch_book_title("walden") == ("Walden", "Thoreau")


@respx.mock
def test_fetch_book_title_falls_back_when_catalog_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books").mock(return_value=httpx.Response(200, json=[]))
    assert _fetch_book_title("unknown") == ("unknown", "")


@respx.mock
def test_fetch_block_raises_valueerror_for_non_dict_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books/walden/blocks").mock(
        return_value=httpx.Response(200, json=["not", "a", "dict"])
    )
    with pytest.raises(ValueError, match="expected block object"):
        _fetch_block("walden", 0)


@respx.mock
def test_fetch_book_title_returns_early_for_non_list_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books").mock(
        return_value=httpx.Response(200, json={"not": "a list"})
    )
    assert _fetch_book_title("walden") == ("walden", "")


@respx.mock
def test_fetch_book_title_skips_non_matching_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books").mock(
        return_value=httpx.Response(
            200,
            json=[
                "not-a-dict-row",
                {"book_id": "other", "title": "Other", "authors": []},
                {"book_id": "walden", "title": "Walden", "authors": ["Thoreau"]},
            ],
        )
    )
    assert _fetch_book_title("walden") == ("Walden", "Thoreau")


# ---------------------------------------------------------------------------
# Handler-level (real ThreadingHTTPServer) hardening tests.
# ---------------------------------------------------------------------------

API_BASE = "http://api.test"

# Loopback handler calls under a contended host (PrepOS CI + local pre-push)
# otherwise hit httpx's 5s default and flake as ReadTimeout.
_LOOPBACK_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _loopback_get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=_LOOPBACK_TIMEOUT)


@pytest.fixture
def running_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """A real ReadHandler bound to an ephemeral port, torn down after the test."""
    monkeypatch.setenv("READ_API_URL", API_BASE)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ReadHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _allow_localhost() -> None:
    """respx mocks httpx globally in-process — including our own request to
    the locally running ReadHandler. Only the handler's *upstream* API calls
    are meant to be intercepted, so let anything addressed to 127.0.0.1 pass
    through to the real (loopback) network."""
    respx.route(host="127.0.0.1").pass_through()


def _mock_walden_blocks(ordinal_text: str = "I went to the woods.") -> None:
    respx.get(f"{API_BASE}/v1/books/walden/blocks").mock(
        return_value=httpx.Response(
            200,
            json={"block_id": "b0", "book_id": "walden", "ordinal": 0, "text": ordinal_text},
        )
    )
    respx.get(f"{API_BASE}/v1/books").mock(
        return_value=httpx.Response(
            200, json=[{"book_id": "walden", "title": "Walden", "authors": ["Thoreau"]}]
        )
    )


def test_read_server_pdf_route_404_without_flag(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HOMELIB_OFFICIAL_VIEWER", raising=False)
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/hp-uk-1")
    assert resp.status_code == 404


@respx.mock
def test_pdf_allowlist_rejects_lookalike_host(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    fake_book = OfficialPreviewBook(
        id="hp-uk-1",
        title="Fake",
        authors=("Author",),
        reader_url="https://www.pottermorepublishing.com/x.html",
        pdf_url="https://www.pottermorepublishing.com.evil.tld/x.pdf",
    )
    monkeypatch.setattr("apps.ui.read_server.official_book_by_id", lambda book_id: fake_book)
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/hp-uk-1")
    assert resp.status_code == 403


@respx.mock
def test_pdf_allowlist_rejects_query_string_spoof(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    fake_book = OfficialPreviewBook(
        id="hp-uk-1",
        title="Fake",
        authors=("Author",),
        reader_url="https://www.pottermorepublishing.com/x.html",
        pdf_url="https://evil.example/x.pdf?host=www.pottermorepublishing.com",
    )
    monkeypatch.setattr("apps.ui.read_server.official_book_by_id", lambda book_id: fake_book)
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/hp-uk-1")
    assert resp.status_code == 403


@respx.mock
def test_pdf_fetch_refuses_redirect(running_server: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    respx.get(POTTERMORE_PDF_URL).mock(
        return_value=httpx.Response(302, headers={"location": "https://evil.example/x.pdf"})
    )
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/hp-uk-1")
    assert resp.status_code == 502


@respx.mock
def test_pdf_over_cap_maps_to_502(running_server: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    monkeypatch.setattr("apps.ui.read_server.MAX_PDF_BYTES", 10)
    respx.get(POTTERMORE_PDF_URL).mock(
        return_value=httpx.Response(
            200, content=b"x" * 1000, headers={"content-type": "application/pdf"}
        )
    )
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/hp-uk-1")
    assert resp.status_code == 502


def test_read_rejects_percent_encoded_slash_book_id(running_server: int) -> None:
    # assert_all_called=False: this mock exists only to catch an accidental
    # call — the whole point of the test is that the *API* mock is never hit.
    with respx.mock(assert_all_called=False) as mocked:
        mocked.route(host="127.0.0.1").pass_through()
        route = mocked.get(url__startswith=f"{API_BASE}/v1/books/").mock(
            return_value=httpx.Response(200, json={"text": "should never be reached"})
        )
        resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/wal%2Fden")
        assert resp.status_code == 404
        assert route.call_count == 0


@respx.mock
def test_read_responses_have_no_cors_wildcard(running_server: int) -> None:
    _allow_localhost()
    _mock_walden_blocks()
    health = _loopback_get(f"http://127.0.0.1:{running_server}/health")
    assert "access-control-allow-origin" not in health.headers
    assert health.headers.get("cache-control") == "private, no-store"
    assert health.headers.get("x-content-type-options") == "nosniff"

    read_resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/walden?ordinal=0")
    assert read_resp.status_code == 200
    assert "access-control-allow-origin" not in read_resp.headers
    assert read_resp.headers.get("cache-control") == "private, no-store"
    assert read_resp.headers.get("x-content-type-options") == "nosniff"


@respx.mock
def test_handler_routes_health_read_pdf_book(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_localhost()
    _mock_walden_blocks()
    base = f"http://127.0.0.1:{running_server}"

    health = _loopback_get(f"{base}/health")
    assert health.status_code == 200
    assert health.text == "ok"

    read_resp = _loopback_get(f"{base}/read/walden?ordinal=0")
    assert read_resp.status_code == 200
    assert "I went to the woods." in read_resp.text

    monkeypatch.delenv("HOMELIB_OFFICIAL_VIEWER", raising=False)
    off_resp = _loopback_get(f"{base}/book/hp-uk-1")
    assert off_resp.status_code == 404

    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    on_resp = _loopback_get(f"{base}/book/hp-uk-1")
    assert on_resp.status_code == 200

    unknown = _loopback_get(f"{base}/nope")
    assert unknown.status_code == 404


@respx.mock
def test_upstream_500_maps_to_502(running_server: int) -> None:
    _allow_localhost()
    respx.get(f"{API_BASE}/v1/books/walden/blocks").mock(return_value=httpx.Response(500))
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/walden?ordinal=0")
    assert resp.status_code == 502


@respx.mock
def test_read_upstream_404_maps_to_404(running_server: int) -> None:
    _allow_localhost()
    respx.get(f"{API_BASE}/v1/books/walden/blocks").mock(return_value=httpx.Response(404))
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/walden?ordinal=0")
    assert resp.status_code == 404


@respx.mock
def test_read_bad_ordinal_maps_to_422(running_server: int) -> None:
    _allow_localhost()
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/walden?ordinal=not-a-number")
    assert resp.status_code == 422


@respx.mock
def test_read_negative_ordinal_maps_to_422(running_server: int) -> None:
    _allow_localhost()
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/walden?ordinal=-1")
    assert resp.status_code == 422


@respx.mock
def test_read_connect_error_maps_to_502(running_server: int) -> None:
    _allow_localhost()
    respx.get(f"{API_BASE}/v1/books/walden/blocks").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/walden?ordinal=0")
    assert resp.status_code == 502


@respx.mock
def test_read_next_ordinal_omitted_when_probe_fails(running_server: int) -> None:
    _allow_localhost()
    # More specific (ordinal=1) route registered first: respx tries routes in
    # registration order, so this wins for the "is there a next page?" probe
    # while the plain route below still answers the ordinal=0 fetch.
    respx.get(f"{API_BASE}/v1/books/walden/blocks", params={"ordinal": "1"}).mock(
        return_value=httpx.Response(404)
    )
    respx.get(f"{API_BASE}/v1/books/walden/blocks").mock(
        return_value=httpx.Response(
            200,
            json={"block_id": "b0", "book_id": "walden", "ordinal": 0, "text": "last page"},
        )
    )
    respx.get(f"{API_BASE}/v1/books").mock(
        return_value=httpx.Response(
            200, json=[{"book_id": "walden", "title": "Walden", "authors": ["Thoreau"]}]
        )
    )
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/walden?ordinal=0")
    assert resp.status_code == 200
    assert 'href="/read/walden?ordinal=1"' not in resp.text


@respx.mock
def test_read_rejects_invalid_book_id_characters(running_server: int) -> None:
    _allow_localhost()
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/read/wal%20den")
    assert resp.status_code == 404


@respx.mock
def test_pdf_rejects_invalid_book_id_characters(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/wal%20den")
    assert resp.status_code == 404


@respx.mock
def test_pdf_unknown_book_maps_to_404(running_server: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/no-such-book")
    assert resp.status_code == 404


@respx.mock
def test_pdf_connect_error_maps_to_502(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    respx.get(POTTERMORE_PDF_URL).mock(side_effect=httpx.ConnectError("down"))
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/hp-uk-1")
    assert resp.status_code == 502


@respx.mock
def test_pdf_success_streams_allowlisted_bytes(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    respx.get(POTTERMORE_PDF_URL).mock(
        return_value=httpx.Response(
            200, content=b"%PDF-1.4 fake", headers={"content-type": "application/pdf; charset=x"}
        )
    )
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/pdf/hp-uk-1")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 fake"
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == "inline"
    assert "access-control-allow-origin" not in resp.headers


@respx.mock
def test_book_rejects_invalid_book_id_characters(
    running_server: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/book/wal%20den")
    assert resp.status_code == 404


@respx.mock
def test_book_unknown_id_maps_to_404(running_server: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMELIB_OFFICIAL_VIEWER", "1")
    _allow_localhost()
    resp = _loopback_get(f"http://127.0.0.1:{running_server}/book/no-such-book")
    assert resp.status_code == 404


def test_main_exits_cleanly_when_port_already_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """A busy port must fail loudly and fast, not hang or print a traceback."""
    blocker = ThreadingHTTPServer(("127.0.0.1", 0), ReadHandler)
    busy_port = blocker.server_address[1]
    try:
        monkeypatch.setenv("READ_PORT", str(busy_port))
        monkeypatch.setattr(
            "apps.ui.read_server.ThreadingHTTPServer",
            lambda address, handler: (_ for _ in ()).throw(OSError("address in use")),
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
    finally:
        blocker.server_close()


def test_main_binds_and_serves_forever(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class _FakeServer:
        def __init__(self, address: tuple[str, int], handler: object) -> None:
            calls["address"] = address

        def serve_forever(self) -> None:
            calls["served"] = True

    monkeypatch.delenv("READ_PORT", raising=False)
    monkeypatch.setattr("apps.ui.read_server.ThreadingHTTPServer", _FakeServer)
    main()
    assert calls["address"] == ("0.0.0.0", DEFAULT_PORT)
    assert calls["served"] is True
