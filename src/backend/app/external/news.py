"""X1 — Market news service.

Fetches real headlines for securities actually held in a portfolio, filtered by relevance.

Provider chain, in order: **Bing News RSS** (keyless, and the only one that returned relevant
German coverage for Swiss mid-caps when this was written), Google News RSS, then Yahoo Finance RSS.
Measured on the demo network: Google News answered with an empty body for every query, and Yahoo's
per-symbol feed returned nothing for `VZN.SW` while `s=UP` worked — so a single-provider design would
have looked "verified" while returning no market context at all.

Only direct equities are queried. A fund or ETF has no single-security coverage, and searching its
wrapper name produces generic articles about ETF investing; those positions are reported as
unavailable with that reason instead of polluting the briefing.

Caches responses under ``external/cache/news/`` keyed by query slug.

Public API:
- ``fetch_market_context(securities, limit)`` — batch fetch for multiple holdings
- ``fetch_for_security(security, limit)`` — single security fetch

Both return structured dicts with ``items``, ``unavailable``, ``fetched_at``,
``providers_used``, ``notes``. Never raise; network failures produce empty lists
with reasons.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from ..i18n import DEFAULT_LANG, t


def offline() -> bool:
    """Whether market news is disabled for this process (``URO_NEWS_OFFLINE=1``).

    The T1 harness must be deterministic and must not touch the network; a briefing that reaches Bing
    inside a test is a flaky test. In offline mode every lookup declares itself unavailable — exactly
    what a dead network produces — so the declaration path is exercised rather than bypassed.
    """
    return os.environ.get("URO_NEWS_OFFLINE", "").strip().lower() not in ("", "0", "false", "no")


def _cache_dir() -> Path:
    """Cache directory, overridable via URO_NEWS_CACHE_DIR for tests."""
    override = os.environ.get("URO_NEWS_CACHE_DIR")
    path = Path(override) if override else Path(__file__).parent / "cache" / "news"
    path.mkdir(parents=True, exist_ok=True)
    return path


# Provider timeouts and politeness
_TIMEOUT = 6.0
_DELAY_BETWEEN_REQUESTS = 0.4  # seconds between requests to same host
_USER_AGENT = "UNRISKOMEGA-Prototype/1.0 (hackathon demo; contact@example.com)"

# Known private/unverifiable instruments — these have no live market coverage
# and should be reported as unavailable rather than returning company news.
# ISIN US84615Q1031 is SpaceX, a private company with no public listing.
_PRIVATE_INSTRUMENTS = {
    "US84615Q1031",  # SpaceX Aktie — private company, no public market
}


# German instrument-type prefixes and share-class noise that wreck a news query
# ("Namen-Aktie VZ Holding AG" -> "VZ Holding AG").
_QUERY_NOISE_PREFIXES = {
    "namen-aktie", "namen-aktien", "namensaktie", "inhaber-aktie", "inhaber-aktien",
    "na. u. inh. ti.-aktie", "partizipationsschein", "partizipationsscheine", "anteile",
    "accum", "shs", "aktie", "aktien", "registered", "bearer", "inhaber",
}
_QUERY_NOISE_TOKENS = {
    "-a-", "-b-", "-c-", "-1c-", "-chf-", "-eur-", "-usd-", "-gbp-", "acc", "dist", "chf", "eur", "usd",
}


def _norm_token(token: str) -> str:
    """Comparison form of one name token: lowercase, no surrounding dots."""
    return token.lower().strip(".")


# A noise prefix can be several tokens long ("na. u. inh. ti.-aktie" is the German share-class
# preamble for ASML and 12 other master rows), so prefixes are matched as *phrases* against the
# leading tokens — longest first — and not token by token.
_NOISE_PREFIX_PHRASES = frozenset(
    tuple(_norm_token(part) for part in phrase.split()) for phrase in _QUERY_NOISE_PREFIXES
)
_MAX_PREFIX_TOKENS = max((len(phrase) for phrase in _NOISE_PREFIX_PHRASES), default=1)

# Markers that identify a fund/ETF wrapper rather than a single company.
_FUND_MARKERS = (
    "etf", " fund", "fonds", "ucits", "sicav", "icav", "index fds", "index fund", "passive leader",
    "inv.series", "investment fund", "multi units", "xtrackers", "ishares",
)


# RSS namespaces
_RSS_NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def _slugify(query: str) -> str:
    """Stable slug for cache keying."""
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower().strip())
    slug = slug.strip("-")
    if len(slug) > 80:
        slug = slug[:80] + "-" + hashlib.sha1(query.encode()).hexdigest()[:6]
    return slug


def _cache_path(query: str, provider: str) -> Path:
    """Cache file path for a query + provider."""
    return _cache_dir() / f"{provider}__{_slugify(query)}.json"


# Bumped when the cached item shape changes. Entries written by an older build are ignored rather
# than served, because a cache hit is cache-primary and would otherwise keep the old fields for the
# full 6 h TTL. v2: the publisher is read from the feed's Source element, so entries written before
# that fix hold ``bing.com`` as the source of every headline.
_CACHE_SCHEMA = 2


def _read_cache(path: Path) -> dict | None:
    """Read cached response if present, parseable and written by the current schema."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "items" in data and data.get("schema") == _CACHE_SCHEMA:
            return data
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return None


def _write_cache(path: Path, data: dict) -> None:
    """Write response to cache."""
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # cache write failure is non-fatal


def _parse_rss_date(date_str: str | None) -> str | None:
    """Parse RSS pubDate to ISO 8601."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _child_text(item, local_name: str) -> str:
    """Text of a direct child matched by *local* name, ignoring any namespace.

    Bing wraps its publisher element in a namespace whose URI is the query URL itself
    (``{https://www.bing.com/news/search?q=ASML%20Holding%20NV&format=RSS}Source``), so no single
    namespaced XPath can be written once for both feeds. Matching the local name covers Bing's
    ``<News:Source>`` and Google's unprefixed ``<source>`` alike; without it every Bing headline
    reported its publisher as ``bing.com`` because the code fell through to the link-domain branch.
    """
    wanted = local_name.lower()
    for child in item:
        if child.tag.rpartition("}")[2].lower() == wanted:
            return (child.text or "").strip()
    return ""


def _extract_rss_items(xml_text: str, limit: int) -> list[dict]:
    """Extract items from RSS XML."""
    items = []
    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return items
        for item in channel.findall("item")[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            source = _child_text(item, "source")
            if not source:
                # Extract source from link domain
                if link.startswith("http"):
                    try:
                        from urllib.parse import urlparse
                        source = urlparse(link).netloc.replace("www.", "")
                    except Exception:
                        source = "Unknown"
                else:
                    source = "Unknown"
            if title and link:
                items.append({
                    "headline": title,
                    "source": source,
                    "url": link,
                    "published": _parse_rss_date(pub_date),
                })
    except ET.ParseError:
        pass
    return items


def _normalise_headline(title: str) -> str:
    """Collapse a headline to a comparison key: no publisher suffix, no language marker, lowercase."""
    text = title.split(" - ")[0] if " - " in title else title
    text = re.sub(r"\((deutsch|english|französisch)\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[^a-z0-9äöü ]+", " ", text.lower())
    return " ".join(text.split())


def _clean_query_name(name: str) -> str:
    """Strip instrument-type prefixes and share-class noise from a security name.

    The case data names instruments the way a bank does ("Namen-Aktie VZ Holding AG"), which is not
    what a news search expects. Returns "" when nothing meaningful survives.
    """
    flattened = name.replace("(", " ").replace(")", " ")
    tokens = [token for token in re.split(r"[\s,]+", flattened) if token]
    normalized = [_norm_token(token) for token in tokens]
    while normalized:
        for size in range(min(_MAX_PREFIX_TOKENS, len(normalized)), 0, -1):
            if tuple(normalized[:size]) in _NOISE_PREFIX_PHRASES:
                del tokens[:size]
                del normalized[:size]
                break
        else:
            break
    kept = [token for token in tokens if _norm_token(token) not in _QUERY_NOISE_TOKENS]
    cleaned = " ".join(kept).strip(" -,.")
    return cleaned if len(cleaned) >= 4 else ""


def clean_query_name(name: str) -> str:
    """Public form of the name cleaner, for callers outside this module (market search)."""
    return _clean_query_name(name)


def _is_direct_equity(security: dict) -> bool:
    """Whether a single security can have its own news coverage."""
    name = str(security.get("Name") or "").lower()
    if any(marker in name for marker in _FUND_MARKERS):
        return False
    return str(security.get("SecurityTypeName") or "").startswith("Shares")


def is_private_instrument(isin: str | None) -> bool:
    """Whether an ISIN is known to have no public market coverage (``_PRIVATE_INSTRUMENTS``)."""
    return bool(isin) and str(isin).strip().upper() in _PRIVATE_INSTRUMENTS


def _fetch_bing_news(query: str, limit: int) -> list[dict]:
    """Fetch from Bing News RSS (primary provider)."""
    url = f"https://www.bing.com/news/search?q={urllib.parse.quote(query)}&format=RSS"
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _USER_AGENT})
            if resp.status_code == 429 or resp.status_code >= 500:
                return []
            resp.raise_for_status()
            return _extract_rss_items(resp.text, limit)
    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        return []


def _fetch_google_news(query: str, limit: int) -> list[dict]:
    """Fetch from Google News RSS search."""
    # Quoted like Bing's: an advisor-typed search can contain spaces, "&" or "+", which an
    # unencoded query would turn into extra feed parameters or a 400.
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en&gl=US&ceid=US:en"
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _USER_AGENT})
            if resp.status_code == 429 or resp.status_code >= 500:
                return []
            resp.raise_for_status()
            return _extract_rss_items(resp.text, limit)
    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        return []


def _fetch_yahoo_news(query: str, limit: int) -> list[dict]:
    """Fetch from Yahoo Finance RSS (fallback)."""
    # Yahoo Finance RSS search
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={query}&region=US&lang=en-US"
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _USER_AGENT})
            if resp.status_code == 429 or resp.status_code >= 500:
                return []
            resp.raise_for_status()
            return _extract_rss_items(resp.text, limit)
    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        return []


def _fetch_with_cache(query: str, provider: str, fetcher, limit: int) -> tuple[list[dict], bool]:
    """Fetch with cache-primary TTL policy. Returns (items, is_fresh).

    If a cache file exists and its ``fetched_at`` is younger than 6 hours, serve it without
    touching the network (briefings become deterministic across repeated calls). Otherwise
    call the provider; on success overwrite the cache, on failure fall back to the stale
    cache so a dead network still yields something.
    """
    cache_path = _cache_path(query, provider)
    cached = _read_cache(cache_path)

    # Cache-primary: serve fresh cache without network.
    if cached:
        fetched_at_str = cached.get("fetched_at")
        if fetched_at_str:
            try:
                fetched_at = datetime.fromisoformat(fetched_at_str)
                if fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
                if age_hours < 6:
                    return cached.get("items", []), True
            except (ValueError, TypeError):
                pass

    # Stale or missing cache: try the network.
    items = fetcher(query, limit)
    if items:
        data = {
            "schema": _CACHE_SCHEMA,
            "items": items,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "query": query,
            "stale": False,
        }
        _write_cache(cache_path, data)
        return items, True

    # Fall back to stale cache if available.
    if cached:
        return cached.get("items", []), False

    return [], False



def _build_relevant_because(security: dict, weight: float | None, lang: str = DEFAULT_LANG) -> str:
    """Why this headline matters for this client, in the requested language."""
    name = security.get("Name") or t("news.unknown", lang)
    if weight is not None:
        return t("news.relevant_weight", lang, pct=f"{weight * 100:.2f}", name=name)
    return t("news.relevant_position", lang, name=name)


def fetch_for_security(
    security: dict,
    limit: int = 5,
    weight: float | None = None,
    lang: str = DEFAULT_LANG,
) -> dict:
    """Fetch news for a single security.

    Args:
        security: Security dict with ``Id``, ``Name``, ``Isin``.
        limit: Max headlines to return.
        weight: Portfolio weight (0–1) for relevance sentence.

    Returns:
        Dict with ``items``, ``unavailable``, ``fetched_at``, ``providers_used``, ``notes``.
    """
    sec_id = security.get("Id")
    name = security.get("Name", "")
    isin = security.get("Isin", "")

    result: dict[str, Any] = {
        "security_id": sec_id,
        "items": [],
        "unavailable": [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "providers_used": [],
        "notes": [],
    }

    if offline():
        result["unavailable"].append({
            "security_id": sec_id,
            "name": name or t("news.unknown", lang),
            "isin": isin or None,
            "reason": t("news.offline", lang),
        })
        result["notes"].append(t("news.offline_note", lang))
        return result

    if not name and not isin:
        result["unavailable"].append({
            "security_id": sec_id,
            "reason": t("news.no_name_isin", lang),
        })
        return result

    # Check for known private/unverifiable instruments
    if isin in _PRIVATE_INSTRUMENTS:
        result["unavailable"].append({
            "security_id": sec_id,
            "name": name,
            "isin": isin,
            "reason": t("news.private_instrument", lang),
        })
        return result

    if not _is_direct_equity(security):
        result["unavailable"].append({
            "security_id": sec_id,
            "name": name,
            "isin": isin,
            "reason": t("news.fund_no_single", lang),
        })
        return result

    query = _clean_query_name(name) or (isin if len(isin) == 12 else "")
    if not query:
        result["unavailable"].append({
            "security_id": sec_id,
            "name": name,
            "isin": isin,
            "reason": t("news.no_query", lang),
        })
        return result

    all_items: list[dict] = []
    providers_used: list[str] = []

    for provider, fetcher in (("bing", _fetch_bing_news), ("google", _fetch_google_news), ("yahoo", _fetch_yahoo_news)):
        time.sleep(_DELAY_BETWEEN_REQUESTS)
        items, is_fresh = _fetch_with_cache(query, provider, fetcher, limit)
        if items:
            all_items.extend(items)
            providers_used.append(provider)
            if not is_fresh:
                result["notes"].append(t("news.cached", lang, query=query))
            break

    if not all_items:
        result["unavailable"].append({
            "security_id": sec_id,
            "name": name,
            "isin": isin,
            "reason": t("news.no_results", lang, count=len(providers_used) or 0, query=query),
        })
    else:
        # Link each item to this security
        relevant_because = _build_relevant_because(security, weight, lang)
        for item in all_items[:limit]:
            item["linked_security_ids"] = [sec_id] if sec_id else []
            item["linked_sectors"] = []
            item["relevant_because"] = relevant_because
        result["items"] = all_items[:limit]

    result["providers_used"] = list(set(providers_used))
    return result


def fetch_for_query(
    query: str,
    limit: int = 8,
    lang: str = DEFAULT_LANG,
) -> dict:
    """Fetch headlines for one instrument name — the advisor's search over the bank's own data.

    Scoped deliberately: the brief ties market coverage to the client's actual holdings and portfolio
    exposures, and ties everything else to a production data connection, so this is only ever called
    with a name the security master already resolved. An unknown company is refused upstream rather
    than answered with a general web summary.

    Args:
        query: The instrument name to search for (raw master names are cleaned first).
        limit: Max headlines to return.
        lang: Language for the declared reasons and notes.

    Returns:
        Dict with ``query``, ``query_used``, ``items``, ``unavailable``, ``providers_used``,
        ``fetched_at``, ``notes``.
    """
    cleaned = query.strip()
    result: dict[str, Any] = {
        "query": cleaned,
        "query_used": cleaned,
        "items": [],
        "unavailable": [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "providers_used": [],
        "notes": [],
    }

    if offline():
        result["unavailable"].append({"name": cleaned or None, "isin": None, "reason": t("news.offline", lang)})
        result["notes"].append(t("news.offline_note", lang))
        return result

    search_text = _clean_query_name(cleaned) or cleaned
    if not search_text:
        result["unavailable"].append({"name": cleaned or None, "isin": None, "reason": t("news.no_query", lang)})
        return result
    result["query_used"] = search_text

    all_items: list[dict] = []
    providers_used: list[str] = []
    for provider, fetcher in (("bing", _fetch_bing_news), ("google", _fetch_google_news), ("yahoo", _fetch_yahoo_news)):
        time.sleep(_DELAY_BETWEEN_REQUESTS)
        items, is_fresh = _fetch_with_cache(search_text, provider, fetcher, limit)
        if items:
            all_items.extend(items)
            providers_used.append(provider)
            if not is_fresh:
                result["notes"].append(t("news.cached", lang, query=search_text))
            break

    result["providers_used"] = sorted(set(providers_used))

    if not all_items:
        result["unavailable"].append({
            "name": cleaned,
            "isin": None,
            "reason": t("news.no_results", lang, count=0, query=search_text),
        })
        return result

    # The same age filter and dedupe the briefing path applies: a search must not present a
    # two-year-old story as today's, nor the same story twice under two publisher suffixes.
    now = datetime.now(timezone.utc)
    kept: list[dict] = []
    for item in all_items:
        published = item.get("published")
        if published:
            try:
                dt = datetime.fromisoformat(published)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if (now - dt).total_seconds() > 365 * 86400:
                    continue
            except (ValueError, TypeError):
                pass
        kept.append(item)

    if not kept:
        result["unavailable"].append({
            "name": cleaned,
            "isin": None,
            "reason": t("news.no_recent_coverage", lang),
        })
        return result

    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for item in kept:
        url = item.get("url")
        title_key = _normalise_headline(str(item.get("headline") or ""))
        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        item["linked_security_ids"] = []
        item["linked_sectors"] = []
        deduped.append(item)

    deduped.sort(key=lambda item: str(item.get("published") or ""), reverse=True)
    result["items"] = deduped[:limit]
    return result


def _item_weight(item: dict, weights: dict[int, float]) -> float:
    """Portfolio weight of the holding a headline is about (``0.0`` when it is linked to none)."""
    linked = item.get("linked_security_ids") or []
    return max((float(weights.get(security_id) or 0.0) for security_id in linked), default=0.0)


def fetch_market_context(
    securities: list[dict] | None = None,
    limit: int = 8,
    weights: dict[int, float] | None = None,
    lang: str = DEFAULT_LANG,
    deadline_seconds: float = 12.0,
) -> dict:
    """Fetch market context for multiple securities.

    Args:
        securities: List of security dicts (with ``Id``, ``Name``, ``Isin``).
                    If None, returns empty context.
        limit: Total headlines to return across all securities.
        weights: Optional mapping of security_id -> portfolio weight.
        deadline_seconds: Wall-clock budget for the whole batch. Fetching a large portfolio
            sequentially would otherwise take minutes; once the budget is spent the remaining
            holdings are reported as unavailable instead of stalling the briefing.

    Returns:
        Dict with ``items``, ``unavailable``, ``fetched_at``, ``providers_used``, ``notes``.
    """
    if not securities:
        return {
            "items": [],
            "unavailable": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "providers_used": [],
            "notes": [t("news.no_securities", lang)],
        }

    weights = weights or {}
    if offline():
        return {
            "items": [],
            "unavailable": [
                {
                    "security_id": security.get("Id"),
                    "name": security.get("Name") or t("news.unknown", lang),
                    "isin": security.get("Isin"),
                    "reason": t("news.offline", lang),
                }
                for security in securities
            ],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "providers_used": [],
            "notes": [t("news.offline_note", lang)],
        }

    all_items = []
    all_unavailable = []
    all_providers = set()
    all_notes = []
    started = time.monotonic()

    for security in securities:
        elapsed = time.monotonic() - started
        if elapsed >= deadline_seconds:
            all_unavailable.append({
                "security_id": security.get("Id"),
                "name": security.get("Name") or t("news.unknown", lang),
                "isin": security.get("Isin"),
                "reason": t("news.time_budget", lang, seconds=f"{deadline_seconds:.0f}"),
            })
            continue
        sec_id = security.get("Id")
        weight = weights.get(sec_id) if sec_id is not None else None
        result = fetch_for_security(security, limit=limit, weight=weight, lang=lang)

        # Age filter: drop items older than 365 days. Items with missing/unparseable
        # published dates are kept (sorted last downstream). If a security had raw
        # items but all were dropped, declare it unavailable for the briefing window.
        now = datetime.now(timezone.utc)
        raw_items = result.get("items") or []
        kept_items = []
        for item in raw_items:
            pub = item.get("published")
            if pub:
                try:
                    dt = datetime.fromisoformat(pub)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if (now - dt).total_seconds() > 365 * 86400:
                        continue
                except (ValueError, TypeError):
                    pass
            kept_items.append(item)
        if raw_items and not kept_items:
            all_unavailable.append({
                "security_id": sec_id,
                "name": security.get("Name") or t("news.unknown", lang),
                "isin": security.get("Isin"),
                "reason": "no coverage in the last 12 months",
            })
        else:
            result["items"] = kept_items
            all_items.extend(kept_items)
        all_unavailable.extend(result["unavailable"])
        all_providers.update(result["providers_used"])
        all_notes.extend(result["notes"])


    # Deduplicate by URL *and* by normalised headline: one company release reaches Bing several
    # times (with/without "(deutsch)", with different publisher suffixes), and showing two variants of
    # the same story would waste the briefing's two available market lines.
    seen_urls = set()
    seen_titles = set()
    deduped_items = []
    for item in all_items:
        url = item.get("url")
        title_key = _normalise_headline(str(item.get("headline") or ""))
        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        deduped_items.append(item)

    # Order: the biggest holding first, newest within it. ``compose.facts`` already ranks the
    # securities it queries by weight and R4 renders the first items, so a date-only sort let an 18%
    # position take the lead market line from a 62% one whose coverage was a day older (SCEN-001,
    # REVIEW.md §12.1). Both passes are stable, so equal weights keep date order and the result stays
    # deterministic for the harness.
    deduped_items.sort(key=lambda item: str(item.get("published") or ""), reverse=True)
    deduped_items.sort(key=lambda item: -_item_weight(item, weights))

    return {
        "items": deduped_items[:limit],
        "unavailable": all_unavailable,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "providers_used": sorted(all_providers),
        "notes": all_notes,
    }
