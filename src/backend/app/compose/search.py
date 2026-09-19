"""Market search — the advisor's ad-hoc "what is going on with X?" surface.

Assembles four sources and keeps them visibly apart, because the advisor has to be able to say
where every line came from:

* the **security master** — what the instrument is (type, currency, asset class, industry, price,
  volatility, the bank's own instrument rating);
* **live headlines** — what is being written about it right now (X1, keyless RSS);
* the **bank's view** — the CIO stances whose category matches the instrument, labelled as the
  mock they are, plus ``SecurityInvestRatingName`` from the master, labelled as the bank's rating
  rather than ours;
* **who holds it** — every client and portfolio in the book with a position, largest first.

No verdict is computed anywhere in this module. The brief's question is "is this worth investing
for my client?", and the honest answer is the union of those four facts; inventing a score would
make this the one component that produces a number nobody can trace back to a source.
"""

from __future__ import annotations

from typing import Any

from ..domain import index
from ..domain.instrument_search import resolve
from ..domain.ingest import listof, num, text
from ..external import house_view as house_view_module
from ..external import llm as llm_module
from ..external import news
from ..i18n import DEFAULT_LANG, t

# CIO stance dimension -> the master field carrying the category that dimension is keyed by.
# The same vocabulary the SAA mappings use, so matching is exact-string and needs no translation.
_BANK_VIEW_DIMENSIONS = {
    "AssetClass": "SAA_AssetClassName",
    "CurrencyGroup": "SAA_CurrencyGroupName",
    "CountryGroup": "SAA_CountryGroupName",
    "Industry": "SAA_IndustryName",
}


def _client_name(client: dict, ref: str) -> str:
    """Display name, following the same rule as the briefing facts (``compose/facts.py``)."""
    company = text(client, "Company")
    if company:
        return company
    joined = " ".join(part for part in (text(client, "FirstName"), text(client, "LastName")) if part)
    return joined.strip() or ref


def _instrument_block(match: dict) -> dict:
    """What the master says about the matched row, plus what else the query could have meant.

    The key set is identical whether or not the master carried the query. An advisor-facing panel
    renders one field grid, and the unmatched case — the common one, because the master was trimmed
    to the holdings the case clients carry — must fill it with the declared gaps it already carries,
    not with an absent key that a UI then reads as ``undefined``.
    """
    block: dict[str, Any] = {
        "matched": False,
        "raw_query": match.get("raw_query"),
        "matched_on": None,
        "security_id": None,
        "name": None,
        "display_name": None,
        "isin": None,
        "valor": None,
        "security_type": None,
        "currency": None,
        "asset_class": None,
        "asset_class_detailed": None,
        "industry": None,
        "country": None,
        "country_group": None,
        "price": None,
        "price_date": None,
        "volatility": None,
        "sustainability_score": None,
        "prc": None,
        "bank_rating": None,
        "in_recommendation_list": False,
        "recommendation_lists": [],
        "share_class_count": 0,
        "alternatives": match.get("alternatives") or [],
    }
    row = match.get("security")
    if not row:
        return block

    name = str(row.get("Name") or "")
    price_date = str(row.get("PriceDateUtc") or "")
    security_id = row.get("Id")
    block.update({
        "matched": True,
        "matched_on": match.get("matched_on"),
        "security_id": security_id,
        "name": name,
        # The cleaned form is what a news index expects and what the advisor recognises; the raw
        # master name travels beside it instead of being thrown away.
        "display_name": news.clean_query_name(name) or name,
        "isin": row.get("Isin"),
        "valor": row.get("Valor"),
        "security_type": row.get("SecurityTypeName"),
        "currency": row.get("Currency"),
        "asset_class": row.get("SAA_AssetClassName"),
        "asset_class_detailed": row.get("AssetClassName"),
        "industry": row.get("IndustryName"),
        "country": row.get("CountryName"),
        "country_group": row.get("SAA_CountryGroupName") or row.get("CountryGroupName"),
        "price": row.get("EndOfDayPrice"),
        "price_date": price_date[:10] or None,
        "volatility": row.get("Volatility"),
        "sustainability_score": row.get("SustainabilityScore"),
        "prc": row.get("PRC"),
        "bank_rating": row.get("SecurityInvestRatingName"),
        "in_recommendation_list": bool(row.get("InRecommendationList")),
        "recommendation_lists": index.get().recommendation_lists(int(security_id or -1)),
        "share_class_count": match.get("share_class_count") or 1,
    })
    return block


def _bank_view_block(security: dict | None) -> dict:
    """The bank's stances on this instrument's categories, verbatim and labelled mock.

    Only the stance itself is read — never a portfolio relation. There is no portfolio in a search,
    and ``house_view.match`` classifies a relation against a weight this call does not have.
    """
    view = house_view_module.house_view()
    stances: list[dict] = []
    if security:
        for stance in view.get("stances") or []:
            dimension = str(stance.get("dimension") or "")
            field = _BANK_VIEW_DIMENSIONS.get(dimension)
            if not field or not security.get(field):
                continue
            if security.get(field) == stance.get("category"):
                stances.append({
                    "dimension": dimension,
                    "category": stance.get("category"),
                    "stance": stance.get("stance"),
                    "note": stance.get("note"),
                })
    return {
        "source": view.get("source"),
        "source_url": view.get("source_url"),
        "as_of": view.get("as_of"),
        "mock": bool(view.get("mock")),
        "disclaimer": view.get("disclaimer"),
        "stances": stances,
    }


def _held_by(security_ids: set[int], isin: str | None) -> list[dict]:
    """Every position in the book on this instrument, largest weight first.

    Positions join on ``SecurityId`` (``PROJECT.md`` §7.1), and the ids of *all* master rows
    sharing the instrument's ISIN count — an advisor asking who holds a fund means the fund, and
    two share classes of it are one instrument to them. Each entry keeps its own ``security_id``,
    value and currency, so nothing is ever summed across share classes.

    An ex-custody position whose ISIN is not in the trimmed master has no ``SecurityId`` at all, so
    the ISIN is the fallback — but only when the id is absent, never as a second, competing key.
    """
    dataset = index.get()
    holders: list[dict] = []
    for client in dataset.clients:
        ref = text(client, "ClientRef")
        for portfolio in listof(client, "Portfolios"):
            for position in listof(portfolio, "SecurityPositions"):
                position_id = position.get("SecurityId")
                if isinstance(position_id, (int, float)) and not isinstance(position_id, bool):
                    if int(position_id) not in security_ids:
                        continue
                elif not (isin and text(position, "Isin") == isin):
                    continue
                holders.append({
                    "client_ref": ref,
                    "client_name": _client_name(client, ref),
                    "portfolio_nr": text(portfolio, "PortfolioNr"),
                    "security_id": int(position_id) if isinstance(position_id, (int, float)) else None,
                    "weight": num(position, "PortfolioValuePercentage", 0.0),
                    "value": num(position, "TotalAmountInPortfolioCurrency", 0.0),
                    "currency": text(portfolio, "PortfolioCurrency") or text(portfolio, "ReferenceCurrency"),
                })
    holders.sort(key=lambda holder: (-(holder.get("weight") or 0.0), str(holder.get("client_ref") or "")))
    return holders


def _refusal(query: str, instrument: dict, lang: str, reason: str, query_kind: str | None) -> dict:
    """The payload for a query this prototype does not answer, carrying the reason it does not.

    Same key set as a successful search: the panel renders one layout, and an empty news list beside
    a stated reason is a first-class state, not an error.
    """
    return {
        "query": query,
        "query_kind": query_kind,
        "as_of": None,
        "instrument": instrument,
        "news": {
            "query_used": None,
            "providers_used": [],
            "items": [],
            "unavailable": [{
                "name": instrument.get("raw_query") or query,
                "isin": instrument.get("isin"),
                "reason": reason,
            }],
            "notes": [],
        },
        "signals": {"applied": False, "reason": None, "model": None, "items": []},
        "bank_view": _bank_view_block(None),
        "held_by": [],
        "held_by_total": 0,
        "portfolio_weight": None,
        "unavailable": [reason],
    }


def search(query: str, lang: str = DEFAULT_LANG, limit: int = 8) -> dict:
    """Answer one advisor search: instrument, coverage, bank view, holders, declared gaps.

    Only instruments the security master carries are answered. The brief ties market coverage to the
    client's actual holdings and exposures (L189–191) and defers every other data connection to
    production (L203), so an unknown company is refused with a stated reason — a general web summary
    about a company the bank has no position in, no rating for and no classification of is exactly
    the "general market summary without a clear connection to the portfolio" the brief rules out.

    Args:
        query: What the advisor typed (instrument name, valor or ISIN).
        lang: Language for every declared reason in the payload.
        limit: Max headlines to return.

    Returns:
        The assembled payload. Top-level ``unavailable`` collects the human-readable gaps of the
        whole search; ``news.unavailable`` keeps the provider-level detail with its reasons.
    """
    match = resolve(query)
    instrument = _instrument_block(match)
    security = match.get("security")

    if not security:
        return _refusal(
            query,
            instrument,
            lang,
            t("search.not_in_master", lang, query=match.get("raw_query") or query),
            None,
        )

    # A private company has no public coverage to report, and the briefing path refuses it for the
    # same reason — the two must not disagree about the same instrument.
    if news.is_private_instrument(instrument.get("isin")):
        return _refusal(
            query,
            instrument,
            lang,
            t("news.private_instrument", lang),
            match.get("matched_on"),
        )

    # Query the provider with the cleaned instrument name — the master spells names the way a bank
    # does ("Na. u. Inh. Ti.-Aktie ASML Holding NV"), which is not what a news index expects.
    market = news.fetch_for_query(
        instrument.get("display_name") or match.get("raw_query") or query,
        limit=limit,
        lang=lang,
    )

    # Positions join on ``SecurityId`` (``PROJECT.md`` §7.1) and the ids of every master row sharing
    # the instrument's ISIN count: an advisor asking who holds a fund means the fund, and its share
    # classes are one instrument to them.
    security_ids: set[int] = set()
    security_isin = str(security.get("Isin") or "") or None
    if security_isin:
        for row in index.get().securities_by_isin(security_isin):
            raw_id = row.get("Id")
            if isinstance(raw_id, (int, float)) and not isinstance(raw_id, bool):
                security_ids.add(int(raw_id))

    # Signals are the one interpretation in this payload, so they are generated from exactly the
    # headlines shown and declared separately: a reader must be able to tell a model's reading of a
    # headline from the headline itself.
    signal_result = llm_module.signals(
        [str(item.get("headline") or "") for item in (market.get("items") or [])],
        lang,
    )

    holders = _held_by(security_ids, security_isin)
    weights = [holder["weight"] for holder in holders if holder.get("weight") is not None]

    unavailable = [
        str(entry["reason"])
        for entry in (market.get("unavailable") or [])
        if entry.get("reason")
    ]

    return {
        "query": query,
        # How the query found its row: the advisor typed an ISIN, a valor or a name.
        "query_kind": match.get("matched_on"),
        "as_of": market.get("fetched_at"),
        "instrument": instrument,
        "news": {
            "query_used": market.get("query_used"),
            "providers_used": market.get("providers_used") or [],
            "items": market.get("items") or [],
            "unavailable": market.get("unavailable") or [],
            "notes": market.get("notes") or [],
        },
        "signals": {
            "applied": bool(signal_result.get("applied")),
            "reason": signal_result.get("reason"),
            "model": llm_module.model() if signal_result.get("applied") else None,
            "items": signal_result.get("signals") or [],
        },
        "bank_view": _bank_view_block(security),
        "held_by": holders,
        "held_by_total": len(holders),
        "portfolio_weight": max(weights) if weights else None,
        "unavailable": unavailable,
    }
