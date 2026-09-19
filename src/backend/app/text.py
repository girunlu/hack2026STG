"""Text helpers shared by the composer and the relevance engine.

``compact`` exists because the briefing has a word budget and instrument names, note texts and rule
descriptions are long. It cuts on a word boundary — a sentence that ends in ``…nee…`` reads like a
rendering bug, not like a deliberate abbreviation — and it never returns an empty string: a single
token longer than the limit is cut hard, because there is no boundary to cut at.
"""

from __future__ import annotations

from typing import Any

ELLIPSIS = "…"


def compact(value: Any, limit: int) -> str:
    """One line of text, truncated on a word boundary to at most ``limit`` characters."""
    if value is None:
        return "—"
    flat = " ".join(str(value).split())
    if len(flat) <= limit:
        return flat
    head = flat[: max(limit - 1, 1)]
    cut = head.rfind(" ")
    if cut > 0:
        head = head[:cut]
    return head.rstrip() + ELLIPSIS
