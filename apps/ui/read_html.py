"""Clean article HTML for Safari Listen to Page (not Streamlit chrome)."""

from __future__ import annotations

import html
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadPage:
    book_id: str
    title: str
    authors: str
    ordinal: int
    text: str
    prev_ordinal: int | None
    next_ordinal: int | None


def build_read_article_html(page: ReadPage) -> str:
    """Top-level HTML document Safari Reader / Listen to Page can detect."""
    title = html.escape(page.title)
    authors = html.escape(page.authors)
    body = html.escape(page.text).replace("\n", "<br>\n")
    nav_parts: list[str] = []
    if page.prev_ordinal is not None:
        nav_parts.append(
            f'<a href="/read/{html.escape(page.book_id)}?ordinal={page.prev_ordinal}">Previous</a>'
        )
    if page.next_ordinal is not None:
        nav_parts.append(
            f'<a href="/read/{html.escape(page.book_id)}?ordinal={page.next_ordinal}">Next</a>'
        )
    nav = " · ".join(nav_parts) if nav_parts else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — MagicLib</title>
  <style>
    :root {{
      --hl-shell: #f7f0e3; --hl-ink: #241c16; --hl-muted: #756758; --hl-gold: #8a5b13;
    }}
    body {{
      margin: 0; padding: 1.25rem; background: var(--hl-shell); color: var(--hl-ink);
      font-family: Georgia, "Times New Roman", serif; line-height: 1.65;
      max-width: 42rem; margin-inline: auto;
    }}
    h1 {{ font-weight: 500; font-size: clamp(1.4rem, 4vw, 2rem); margin: 0 0 0.25rem; }}
    .by {{ color: var(--hl-muted); font-size: 0.95rem; margin: 0 0 1.25rem; }}
    article {{ font-size: 1.15rem; }}
    nav {{ margin-top: 2rem; font-family: system-ui, sans-serif; }}
    nav a {{
      color: var(--hl-gold); font-size: 1.1rem; min-height: 44px;
      display: inline-block; padding: 0.5rem 0;
    }}
    .mark {{ color: var(--hl-muted); font: 0.8rem system-ui, sans-serif; margin-top: 2rem; }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p class="by">{authors} · page {page.ordinal + 1}</p>
  </header>
  <article>
    <p>{body}</p>
  </article>
  <nav aria-label="Pages">{nav}</nav>
  <p class="mark">MagicLib — HomeLib · use Safari Listen to Page (aA) or Speak Screen</p>
</body>
</html>
"""
