"""Market search API — the advisor's ad-hoc instrument lookup.

One endpoint answering "what is this, what is being written about it, what does the bank say, and
who already holds it" — the 60-second preparation for a call about an instrument nobody planned to
discuss. It reads live news, so nothing here is cached beyond the provider cache in X1, and every
gap the search hits is declared in the payload rather than smoothed over.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..compose import search as search_module
from ..i18n import DEFAULT_LANG, LANGS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["X1"])


class MarketSearchResponse(BaseModel):
    """One advisor search, four sources kept apart.

    ``instrument`` is the security master row (``matched: false`` when the master does not carry
    the query — the normal case for a company the book does not hold). ``news`` is live coverage
    from the keyless X1 providers. ``bank_view`` is the mock CIO stance set filtered to this
    instrument's categories. ``held_by`` is every position in the book on it.
    """

    query: str = Field(description="What the advisor typed", examples=["ASML Holding"])
    query_kind: str | None = Field(
        default=None,
        description="How the query found its row: isin | valor | name; null when nothing matched",
        examples=["name"],
    )
    as_of: str | None = Field(default=None, description="When the market data was fetched")
    instrument: dict[str, Any] = Field(description="Security master row plus alternatives")
    news: dict[str, Any] = Field(description="Live headlines, providers used, provider-level gaps")
    signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Model-generated reading of those headlines (sentiment, materiality, why) — "
                    "labelled as interpretation, never as a bank fact",
    )
    bank_view: dict[str, Any] = Field(description="Mock CIO stances for this instrument's categories")
    held_by: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Positions in the book on this instrument, largest weight first",
    )
    held_by_total: int = Field(default=0, description="Number of positions holding it")
    portfolio_weight: float | None = Field(
        default=None,
        description="Largest position weight in the book (fraction 0-1), null when not held",
    )
    unavailable: list[str] = Field(
        default_factory=list,
        description="Declared gaps of the whole search — never filled with an invented value",
    )


@router.get("/search", response_model=MarketSearchResponse)
def market_search(
    q: str = Query(
        ...,
        min_length=1,
        max_length=120,
        description="Company name, ticker or ISIN",
        examples=["ASML Holding"],
    ),
    lang: str = Query(default=DEFAULT_LANG, description="Response language"),
    limit: int = Query(default=8, ge=1, le=25, description="Max headlines to return"),
) -> MarketSearchResponse:
    """Search the market for one instrument and return everything the advisor needs to answer."""
    if lang not in LANGS:
        lang = DEFAULT_LANG
    try:
        return MarketSearchResponse(**search_module.search(q, lang=lang, limit=limit))
    except Exception as exc:  # a search must report its failure, never return a half-built answer
        logger.exception("market search failed for query %r", q)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Market search failed: {exc}",
        ) from exc
