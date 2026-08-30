"""Shared retrieval hit model — see specs/indexing.md.

`Hit` is defined once, here, because `homelib_rag.index` (WP-10) and
`homelib_rag.hybrid` (WP-11) do not exist yet at the time `rerank.py` and
`rewrite.py` are written (WP-13), but both of those modules and their eventual
callers need the same type rather than each redefining it. `specs/hybrid.md`,
`specs/rerank.md`, and `specs/rewrite.md` all reference `Hit` by name and do
not redefine its fields.
"""

from pydantic import BaseModel, ConfigDict

__all__ = ["Hit"]


class Hit(BaseModel):
    """A single ranked retrieval result from one search arm or rerank pass."""

    model_config = ConfigDict(extra="allow")

    chunk_id: str
    book_id: str
    score: float
    rank: int  # 1-based position in this ranking
    text: str
    section_path: list[str]
    page: int | None
