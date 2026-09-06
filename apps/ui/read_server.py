"""Minimal HTTP server for clean /read pages + Official Pottermore PDF preview.

Runs alongside Streamlit in the UI container on port 8502.

- ``/read/{book_id}`` — shelf article HTML for Safari Listen to Page (via API).
- ``/pdf/{book_id}`` — display-only stream of allowlisted Pottermore PDFs
  (publishers set X-Frame-Options; we never write bytes to SQLite / FTS).
- ``/book/{book_id}`` — two-page pdf.js open-book stage for the projector.
"""

from __future__ import annotations

import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

import httpx

from apps.ui.book_spread import build_book_spread_html, official_book_by_id
from apps.ui.read_html import ReadPage, build_read_article_html
from apps.ui.view_model import is_allowlisted_official_url, official_viewer_enabled

DEFAULT_API = "http://api:8000"
DEFAULT_PORT = 8502

# 64 MiB cap on a proxied PDF — bounds the buffer even though we stream the
# upstream response instead of trusting Content-Length.
MAX_PDF_BYTES = 64 * 1024 * 1024

# Percent-decoded path segment must match this before it is trusted in a
# routed URL (book id / block id). No "/", "?", "%" — safe to f-string.
_BOOK_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _api_base() -> str:
    return (os.environ.get("READ_API_URL") or os.environ.get("API_URL") or DEFAULT_API).rstrip("/")


def _fetch_block(book_id: str, ordinal: int) -> dict[str, object]:
    url = f"{_api_base()}/v1/books/{book_id}/blocks"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, params={"ordinal": ordinal})
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("expected block object")
    return data


def _fetch_book_title(book_id: str) -> tuple[str, str]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{_api_base()}/v1/books")
        resp.raise_for_status()
        books = resp.json()
    if not isinstance(books, list):
        return book_id, ""
    for book in books:
        if isinstance(book, dict) and str(book.get("book_id")) == book_id:
            authors = book.get("authors") or []
            author_s = ", ".join(str(a) for a in authors) if isinstance(authors, list) else ""
            return str(book.get("title") or book_id), author_s
    return book_id, ""


def _stream_official_pdf(book_id: str) -> tuple[bytes, str]:
    """Fetch allowlisted Pottermore PDF bytes for display only.

    Streamed (not buffered via ``client.get``) so ``MAX_PDF_BYTES`` bounds
    memory regardless of what the upstream ``Content-Length`` claims.
    """
    book = official_book_by_id(book_id)
    if book is None:
        raise LookupError(book_id)
    if not is_allowlisted_official_url(book.pdf_url):
        raise PermissionError("pdf host not allowlisted")
    with (
        httpx.Client(timeout=120.0, follow_redirects=False) as client,
        client.stream("GET", book.pdf_url) as resp,
    ):
        if 300 <= resp.status_code < 400:
            raise PermissionError("redirect refused")
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/pdf")
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > MAX_PDF_BYTES:
                raise ValueError("upstream pdf exceeds MAX_PDF_BYTES")
            chunks.append(chunk)
        return b"".join(chunks), content_type.split(";")[0].strip() or "application/pdf"


class ReadHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _write(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """Common response headers for every route: never cached, never
        MIME-sniffed, and never CORS-open (this server is not an API)."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        raw = urlparse(self.path)
        # Percent-decode BEFORE routing/validating so a path segment like
        # "wal%2Fden" cannot smuggle a "/" past the book-id allowlist below.
        parsed = raw._replace(path=unquote(raw.path))

        if parsed.path in {"/", "/health"}:
            self._write(200, b"ok", "text/plain; charset=utf-8")
            return

        if parsed.path.startswith("/pdf/"):
            self._serve_pdf(parsed.path[len("/pdf/") :].strip("/"))
            return
        if parsed.path.startswith("/book/"):
            self._serve_book(parsed.path[len("/book/") :].strip("/"))
            return
        if parsed.path.startswith("/read/"):
            self._serve_read(parsed)
            return
        self.send_error(404)

    def _serve_pdf(self, book_id: str) -> None:
        if not official_viewer_enabled():
            self.send_error(404, "official viewer disabled")
            return
        if not _BOOK_ID_RE.match(book_id):
            self.send_error(404)
            return
        try:
            data, content_type = _stream_official_pdf(book_id)
        except LookupError:
            self.send_error(404, "unknown official preview book")
            return
        except PermissionError as exc:
            # Allowlist violation is a client-facing 403; a refused upstream
            # redirect is treated as an upstream failure (502) — never trust
            # or forward a redirect target.
            status = 502 if str(exc) == "redirect refused" else 403
            self.send_error(status, str(exc) or "pdf host not allowlisted")
            return
        except ValueError:
            self.send_error(502, "upstream pdf too large")
            return
        except httpx.HTTPError:
            self.send_error(502, "upstream pdf unreachable")
            return
        # No X-Frame-Options: Streamlit :8501 embeds /book/ in an iframe; PDF
        # fetch is same-origin to that viewer document on :8502.
        self._write(200, data, content_type, extra_headers={"Content-Disposition": "inline"})

    def _serve_book(self, book_id: str) -> None:
        if not official_viewer_enabled():
            self.send_error(404, "official viewer disabled")
            return
        if not _BOOK_ID_RE.match(book_id):
            self.send_error(404)
            return
        book = official_book_by_id(book_id)
        if book is None:
            self.send_error(404, "unknown official preview book")
            return
        html = build_book_spread_html(book).encode("utf-8")
        self._write(200, html, "text/html; charset=utf-8")

    def _serve_read(self, parsed: ParseResult) -> None:
        book_id = parsed.path[len("/read/") :].strip("/")
        if not _BOOK_ID_RE.match(book_id):
            self.send_error(404)
            return
        qs = parse_qs(parsed.query)
        try:
            ordinal = int((qs.get("ordinal") or ["0"])[0])
        except ValueError:
            self.send_error(422, "bad ordinal")
            return
        if ordinal < 0:
            self.send_error(422, "ordinal must be >= 0")
            return
        try:
            block = _fetch_block(book_id, ordinal)
            title, authors = _fetch_book_title(book_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                self.send_error(404, "block not found")
            else:
                # Never reflect the upstream status verbatim.
                self.send_error(502, "upstream error")
            return
        except Exception:
            self.send_error(502, "api unreachable")
            return
        prev_o = ordinal - 1 if ordinal > 0 else None
        next_o: int | None
        try:
            _fetch_block(book_id, ordinal + 1)
            next_o = ordinal + 1
        except Exception:
            next_o = None
        page = ReadPage(
            book_id=book_id,
            title=title,
            authors=authors,
            ordinal=ordinal,
            text=str(block.get("text") or ""),
            prev_ordinal=prev_o,
            next_ordinal=next_o,
        )
        html = build_read_article_html(page).encode("utf-8")
        self._write(200, html, "text/html; charset=utf-8")


def main() -> None:
    port = int(os.environ.get("READ_PORT", str(DEFAULT_PORT)))
    try:
        # Container-internal bind; host LAN exposure is compose HOMELIB_UI_BIND.
        server = ThreadingHTTPServer(("0.0.0.0", port), ReadHandler)  # noqa: S104
    except OSError as exc:
        print(f"read_server: cannot bind 0.0.0.0:{port}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
