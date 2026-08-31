"""Shared retrieval hit model — see specs/indexing.md.

`Hit` is defined once, here, because `homelib_rag.index` (WP-10) and
`homelib_rag.hybrid` (WP-11) do not exist yet at the time `rerank.py` and
`rewrite.py` are written (WP-13), but both of those modules and their eventual
callers need the same type rather than each redefining it. `specs/hybrid.md`,
`specs/rerank.md`, and `specs/rewrite.md` all reference `Hit` by name and do
not redefine its fields.
"""

from pydantic import BaseModel, ConfigDict, Field

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

    #: The blocks this chunk was built from, in the chunk's own block order.
    #: The index query already selected these to derive `page`; carrying them
    #: on the Hit is what lets a Citation name a block a reader can actually
    #: open. Defaulted so existing constructions stay valid, but a Hit from a
    #: real index always has at least one.
    block_ids: list[str] = Field(default_factory=list)
