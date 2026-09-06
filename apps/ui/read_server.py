"""Minimal HTTP server for clean /read pages (Safari Listen to Page).

Runs alongside Streamlit in the UI container on port 8502. Fetches blocks from
the API over the Docker network — never opens SQLite itself.
"""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

from apps.ui.read_html import ReadPage, build_read_article_html

DEFAULT_API = "http://api:8000"
DEFAULT_PORT = 8502


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


class ReadHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/health"}:
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not parsed.path.startswith("/read/"):
            self.send_error(404)
            return
        book_id = parsed.path[len("/read/") :].strip("/")
        if not book_id or "/" in book_id:
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
            self.send_error(exc.response.status_code, "block fetch failed")
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
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def main() -> None:
    port = int(os.environ.get("READ_PORT", str(DEFAULT_PORT)))
    # Container-internal bind; host LAN exposure is compose HOMELIB_UI_BIND.
    server = ThreadingHTTPServer(("0.0.0.0", port), ReadHandler)  # noqa: S104
    server.serve_forever()


if __name__ == "__main__":
    main()
