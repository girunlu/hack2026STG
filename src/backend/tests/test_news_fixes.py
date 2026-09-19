"""Regression tests for news.py fixes (dedupe, age filter, cache-primary TTL).

All tests are offline/deterministic — no network. The session-scoped conftest sets
URO_NEWS_OFFLINE=1; these tests temporarily clear it where they need the live code path.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.external import news as news_mod


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Route the news cache to a per-test temp dir."""
    monkeypatch.setenv("URO_NEWS_CACHE_DIR", str(tmp_path / "news_cache"))
    # Ensure the module picks up the env override on each call (it re-reads via _cache_dir()).
    yield


@pytest.fixture
def _online(monkeypatch):
    """Temporarily disable offline mode so the live code path runs."""
    monkeypatch.setenv("URO_NEWS_OFFLINE", "0")


def _seed_cache(query: str, provider: str, items: list[dict], fetched_at: str, cache_dir: Path) -> None:
    """Write a cache file directly, bypassing the network."""
    slug = news_mod._slugify(query)
    path = cache_dir / f"{provider}__{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": news_mod._CACHE_SCHEMA,
        "items": items,
        "fetched_at": fetched_at,
        "provider": provider,
        "query": query,
        "stale": False,
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _cache_dir() -> Path:
    return news_mod._cache_dir()


# ---------------------------------------------------------------------------
# Bug 1: title dedupe reads "headline", not "title"
# ---------------------------------------------------------------------------

def test_dedupe_by_normalised_headline(_online):
    """Two items with the same normalised headline but different URLs → one survives."""
    now_iso = datetime.now(timezone.utc).isoformat()
    items = [
        {"headline": "Nestlé Reports Strong Q1 - Reuters", "url": "https://example.com/a", "published": now_iso},
        {"headline": "Nestlé reports strong Q1 (english) - Bloomberg", "url": "https://example.com/b", "published": now_iso},
    ]
    # Both normalise to the same key via _normalise_headline.
    assert news_mod._normalise_headline(items[0]["headline"]) == news_mod._normalise_headline(items[1]["headline"])

    securities = [{"Id": 1, "Name": "Namen-Aktie Nestlé SA", "Isin": "CH0038863350", "SecurityTypeName": "Shares"}]

    def fake_fetcher(query, limit):
        return items

    # Monkeypatch the provider chain so only bing runs, returning our items.
    monkeypatch_bing = pytest.MonkeyPatch()
    monkeypatch_bing.setattr(news_mod, "_fetch_bing_news", fake_fetcher)
    monkeypatch_bing.setattr(news_mod, "_fetch_google_news", lambda q, l: [])
    monkeypatch_bing.setattr(news_mod, "_fetch_yahoo_news", lambda q, l: [])
    monkeypatch_bing.setattr(news_mod, "_DELAY_BETWEEN_REQUESTS", 0)
    try:
        result = news_mod.fetch_market_context(securities, limit=8)
    finally:
        monkeypatch_bing.undo()

    headlines = [it.get("headline") for it in result["items"]]
    assert len(headlines) == 1, f"expected 1 after dedupe, got {len(headlines)}: {headlines}"


# ---------------------------------------------------------------------------
# Bug 2: age filter drops stale items; declares unavailable when all dropped
# ---------------------------------------------------------------------------

def test_age_filter_drops_old_items(_online):
    """An item from 2017 is dropped; if it was the only item, unavailable is declared."""
    old_iso = "2017-07-07T12:00:00+00:00"
    items = [{"headline": "Old news", "url": "https://example.com/old", "published": old_iso}]

    securities = [{"Id": 2, "Name": "Namen-Aktie Acme AG", "Isin": "CH0000000001", "SecurityTypeName": "Shares"}]

    monkeypatch_age = pytest.MonkeyPatch()
    monkeypatch_age.setattr(news_mod, "_fetch_bing_news", lambda q, l: items)
    monkeypatch_age.setattr(news_mod, "_fetch_google_news", lambda q, l: [])
    monkeypatch_age.setattr(news_mod, "_fetch_yahoo_news", lambda q, l: [])
    monkeypatch_age.setattr(news_mod, "_DELAY_BETWEEN_REQUESTS", 0)
    try:
        result = news_mod.fetch_market_context(securities, limit=8)
    finally:
        monkeypatch_age.undo()

    assert result["items"] == []
    reasons = [u.get("reason") for u in result["unavailable"]]
    assert any("no coverage in the last 12 months" in r for r in reasons), f"unavailable: {result['unavailable']}"


def test_age_filter_keeps_recent_items(_online):
    """A recent item survives the age filter."""
    recent_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    items = [{"headline": "Recent news", "url": "https://example.com/new", "published": recent_iso}]

    securities = [{"Id": 3, "Name": "Namen-Aktie Acme AG", "Isin": "CH0000000002", "SecurityTypeName": "Shares"}]

    monkeypatch_recent = pytest.MonkeyPatch()
    monkeypatch_recent.setattr(news_mod, "_fetch_bing_news", lambda q, l: items)
    monkeypatch_recent.setattr(news_mod, "_fetch_google_news", lambda q, l: [])
    monkeypatch_recent.setattr(news_mod, "_fetch_yahoo_news", lambda q, l: [])
    monkeypatch_recent.setattr(news_mod, "_DELAY_BETWEEN_REQUESTS", 0)
    try:
        result = news_mod.fetch_market_context(securities, limit=8)
    finally:
        monkeypatch_recent.undo()

    assert len(result["items"]) == 1
    assert result["items"][0]["headline"] == "Recent news"


# ---------------------------------------------------------------------------
# Bug 3: cache is primary within TTL
# ---------------------------------------------------------------------------

def test_cache_primary_within_ttl(_online, tmp_path):
    """A cache entry younger than 6h is served without calling the provider."""
    query = "nestle"
    provider = "bing"
    cached_items = [{"headline": "Cached headline", "url": "https://example.com/cached", "published": datetime.now(timezone.utc).isoformat()}]
    _seed_cache(query, provider, cached_items, datetime.now(timezone.utc).isoformat(), _cache_dir())

    def raising_fetcher(q, l):
        raise AssertionError("provider must not be called when cache is fresh")

    monkeypatch_cache = pytest.MonkeyPatch()
    monkeypatch_cache.setattr(news_mod, "_fetch_bing_news", raising_fetcher)
    monkeypatch_cache.setattr(news_mod, "_fetch_google_news", raising_fetcher)
    monkeypatch_cache.setattr(news_mod, "_fetch_yahoo_news", raising_fetcher)
    monkeypatch_cache.setattr(news_mod, "_DELAY_BETWEEN_REQUESTS", 0)
    try:
        items, is_fresh = news_mod._fetch_with_cache(query, provider, raising_fetcher, limit=5)
    finally:
        monkeypatch_cache.undo()

    assert items == cached_items
    assert is_fresh is True


def test_cache_stale_triggers_network(_online, tmp_path):
    """A cache entry older than 6h is bypassed; the provider is called."""
    query = "nestle"
    provider = "bing"
    old_fetched_at = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    _seed_cache(query, provider, [{"headline": "Stale"}], old_fetched_at, _cache_dir())

    fresh_items = [{"headline": "Fresh from network", "url": "https://example.com/fresh", "published": datetime.now(timezone.utc).isoformat()}]
    called = {"count": 0}

    def network_fetcher(q, l):
        called["count"] += 1
        return fresh_items

    items, is_fresh = news_mod._fetch_with_cache(query, provider, network_fetcher, limit=5)

    assert called["count"] == 1
    assert items == fresh_items
    assert is_fresh is True


# ---------------------------------------------------------------------------
# Offline behavior unchanged
# ---------------------------------------------------------------------------

def test_offline_declares_unavailable_no_provider_call(monkeypatch):
    """URO_NEWS_OFFLINE=1 must short-circuit with no provider call."""
    monkeypatch.setenv("URO_NEWS_OFFLINE", "1")

    def raising_fetcher(q, l):
        raise AssertionError("provider must not be called in offline mode")

    monkeypatch.setattr(news_mod, "_fetch_bing_news", raising_fetcher)
    monkeypatch.setattr(news_mod, "_fetch_google_news", raising_fetcher)
    monkeypatch.setattr(news_mod, "_fetch_yahoo_news", raising_fetcher)

    securities = [{"Id": 4, "Name": "Namen-Aktie Acme AG", "Isin": "CH0000000003", "SecurityTypeName": "Shares"}]
    result = news_mod.fetch_market_context(securities, limit=8)

    assert result["items"] == []
    assert len(result["unavailable"]) == 1
    assert result["unavailable"][0]["security_id"] == 4


# ---------------------------------------------------------------------------
# Bug: a multi-word noise prefix was never stripped (REVIEW.md §4.13)
# ---------------------------------------------------------------------------

def test_multi_word_noise_prefix_is_stripped():
    """The German share-class preamble is four tokens long, so a single-token match never saw it.

    Measured effect before the fix: ASML was searched as "Na. u. Inh. Ti.-Aktie ASML Holding NV" and
    returned one generic headline, while Qualcomm — cleaned to "Qualcomm Inc" — returned seven
    on-point headlines in the same briefing.
    """
    assert news_mod._clean_query_name("Na. u. Inh. Ti.-Aktie ASML Holding NV") == "ASML Holding NV"
    cleaned = news_mod._clean_query_name("Na. u. Inh. Ti.-Aktie -B Novo Nordisk A/S")
    assert cleaned.endswith("Novo Nordisk A/S")
    assert "aktie" not in cleaned.lower()


def test_single_token_prefix_still_stripped():
    """The phrase matcher must not regress the one-token prefixes that already worked."""
    assert news_mod._clean_query_name("Namen-Aktie VZ Holding AG") == "VZ Holding AG"
    assert news_mod._clean_query_name("Anteile iShares Swiss Dividend ETF") == "iShares Swiss Dividend ETF"


def test_repeated_prefixes_are_all_stripped():
    assert news_mod._clean_query_name("Aktien Namen-Aktie Roche Holding AG") == "Roche Holding AG"


def test_noise_only_name_yields_no_query():
    """Nothing meaningful survives, so the caller falls back to the ISIN instead of searching noise."""
    assert news_mod._clean_query_name("Namen-Aktie") == ""


def test_a_company_name_is_never_eaten():
    """Only a *leading* preamble is stripped: "Aktiengesellschaft" is part of the company name."""
    cleaned = news_mod._clean_query_name("Namen-Aktie Stanserhorn-Bahn-Aktiengesellschaft")
    assert cleaned == "Stanserhorn-Bahn-Aktiengesellschaft"


def test_every_master_name_loses_its_preamble(dataset):
    """Dataset-wide invariant: no cleaned query still starts with an instrument-type preamble."""
    offenders = []
    for security in dataset.securities:
        name = str(security.get("Name") or "")
        cleaned = news_mod._clean_query_name(name)
        if not cleaned:
            continue
        first = cleaned.split()[0].lower().strip(".")
        if first in news_mod._QUERY_NOISE_PREFIXES:
            offenders.append((name, cleaned))
    assert not offenders, f"{len(offenders)} queries still carry a preamble: {offenders[:5]}"


# ---------------------------------------------------------------------------
# Ordering: the largest holding leads the market block
# ---------------------------------------------------------------------------

def test_market_context_leads_with_the_largest_holding(_online):
    """A newer headline about a small position must not take the lead from the dominant holding.

    R4 renders ``market_context[0]``. SCEN-001 holds 62% ASML and 18% Qualcomm, and a date-only sort
    handed the briefing's market line to Qualcomm (REVIEW.md §12.1). Within one holding the newest
    item still leads.
    """
    day = timedelta(days=1)
    now = datetime.now(timezone.utc)
    by_query = {
        "ASML Holding NV": [
            {"headline": "ASML last week", "url": "https://example.com/asml-old", "published": (now - 7 * day).isoformat()},
            {"headline": "ASML this week", "url": "https://example.com/asml-new", "published": (now - 4 * day).isoformat()},
        ],
        "Qualcomm Inc": [
            {"headline": "Qualcomm yesterday", "url": "https://example.com/qcom", "published": (now - day).isoformat()},
        ],
    }
    securities = [
        {"Id": 11, "Name": "Na. u. Inh. Ti.-Aktie ASML Holding NV", "Isin": "NL0010273215", "SecurityTypeName": "Shares"},
        {"Id": 12, "Name": "Namen-Aktie Qualcomm Inc", "Isin": "US7475251036", "SecurityTypeName": "Shares"},
    ]

    patch = pytest.MonkeyPatch()
    patch.setattr(news_mod, "_fetch_bing_news", lambda query, limit: by_query.get(query, []))
    patch.setattr(news_mod, "_fetch_google_news", lambda q, l: [])
    patch.setattr(news_mod, "_fetch_yahoo_news", lambda q, l: [])
    patch.setattr(news_mod, "_DELAY_BETWEEN_REQUESTS", 0)
    try:
        result = news_mod.fetch_market_context(securities, limit=8, weights={11: 0.62, 12: 0.18})
    finally:
        patch.undo()

    assert [item["headline"] for item in result["items"]] == [
        "ASML this week", "ASML last week", "Qualcomm yesterday",
    ]
    assert "62.00%" in result["items"][0]["relevant_because"]
