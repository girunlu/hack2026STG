"""Market search — the advisor's ad-hoc instrument lookup.

The endpoint exists to answer a question nobody planned for ("the client just asked about NVIDIA"),
so what these assert is the *honesty of a miss* as much as the happy path: an instrument the master
does not carry must still produce market coverage plus a declared gap, never a fabricated fact and
never an empty screen. Provider ordering is asserted with stubbed fetchers, so no test here touches
the network.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.compose import search as search_module
from app.domain import index
from app.domain.instrument_search import resolve
from app.external import news as news_mod

BING_ITEM = """<?xml version="1.0"?>
<rss version="2.0" xmlns:News="https://www.bing.com/news/search?q=ASML&amp;format=RSS">
  <channel>
    <item>
      <title>ASML Holding Aktie: Quartalszahlen am 14. Oktober</title>
      <link>https://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;aid=&amp;tid=1</link>
      <pubDate>Mon, 15 Sep 2026 08:15:00 GMT</pubDate>
      <News:Source>finanzen.net</News:Source>
    </item>
  </channel>
</rss>
"""

GOOGLE_ITEM = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Nvidia-Backed Data Center Firm Nscale Files Publicly for IPO</title>
      <link>https://news.google.com/rss/articles/abc</link>
      <pubDate>Fri, 18 Sep 2026 06:30:00 GMT</pubDate>
      <source url="https://www.bloomberg.com">Bloomberg.com</source>
    </item>
  </channel>
</rss>
"""


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def offline(monkeypatch):
    """Deterministic mode: no provider call, every gap declared."""
    monkeypatch.setenv("URO_NEWS_OFFLINE", "1")


# ---------------------------------------------------------------------------
# Publisher — the field the advisor reads to judge a headline
# ---------------------------------------------------------------------------

def test_publisher_is_read_from_the_feed_source_element():
    """Bing namespaces ``Source`` by the query URL; the publisher must survive that."""
    items = news_mod._extract_rss_items(BING_ITEM, 5)
    assert [item["source"] for item in items] == ["finanzen.net"]


def test_publisher_is_read_from_an_unprefixed_source_element():
    items = news_mod._extract_rss_items(GOOGLE_ITEM, 5)
    assert [item["source"] for item in items] == ["Bloomberg.com"]


def test_missing_source_falls_back_to_the_link_domain():
    xml = GOOGLE_ITEM.replace('<source url="https://www.bloomberg.com">Bloomberg.com</source>', "")
    items = news_mod._extract_rss_items(xml, 5)
    assert [item["source"] for item in items] == ["news.google.com"]


# ---------------------------------------------------------------------------
# Cache — a stale entry must not outlive a field change
# ---------------------------------------------------------------------------

def test_cache_entry_from_an_older_schema_is_ignored(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("URO_NEWS_CACHE_DIR", str(tmp_path))
    path = news_mod._cache_path("nestle", "bing")
    path.write_text(
        json.dumps({
            "items": [{"headline": "Old shape", "url": "https://example.com/old", "source": "bing.com"}],
            "fetched_at": news_mod.datetime.now(news_mod.timezone.utc).isoformat(),
            "provider": "bing",
            "query": "nestle",
            "stale": False,
        }),
        encoding="utf-8",
    )
    assert news_mod._read_cache(path) is None

    called = {"count": 0}

    def fetcher(query: str, limit: int) -> list[dict]:
        called["count"] += 1
        return [{"headline": "Fresh", "url": "https://example.com/new", "source": "Reuters"}]

    items, is_fresh = news_mod._fetch_with_cache("nestle", "bing", fetcher, limit=5)
    assert called["count"] == 1
    assert [item["headline"] for item in items] == ["Fresh"]
    assert is_fresh is True


# ---------------------------------------------------------------------------
# Provider order — measured, not assumed
# ---------------------------------------------------------------------------

def _stub_providers(monkeypatch, tmp_path: Path, seen: list[str]):
    monkeypatch.setenv("URO_NEWS_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("URO_NEWS_OFFLINE", "0")
    monkeypatch.setattr(news_mod, "_DELAY_BETWEEN_REQUESTS", 0)

    def make(name: str):
        def fetcher(query: str, limit: int) -> list[dict]:
            seen.append(name)
            return [{"headline": f"{name} says", "url": f"https://example.com/{name}", "published": None}]
        return fetcher

    monkeypatch.setattr(news_mod, "_fetch_bing_news", make("bing"))
    monkeypatch.setattr(news_mod, "_fetch_google_news", make("google"))
    monkeypatch.setattr(news_mod, "_fetch_yahoo_news", make("yahoo"))


def test_name_query_asks_bing_first(monkeypatch, tmp_path: Path):
    seen: list[str] = []
    _stub_providers(monkeypatch, tmp_path, seen)

    result = news_mod.fetch_for_query("ASML Holding", limit=3)

    assert seen == ["bing"]
    assert result["providers_used"] == ["bing"]


def test_the_chain_falls_through_to_the_next_provider(monkeypatch, tmp_path: Path):
    """A provider that returns nothing must not end the lookup."""
    monkeypatch.setenv("URO_NEWS_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("URO_NEWS_OFFLINE", "0")
    monkeypatch.setattr(news_mod, "_DELAY_BETWEEN_REQUESTS", 0)
    seen: list[str] = []

    def empty(name: str):
        def fetcher(query: str, limit: int) -> list[dict]:
            seen.append(name)
            return []
        return fetcher

    def hit(query: str, limit: int) -> list[dict]:
        seen.append("google")
        return [{"headline": "Google says", "url": "https://example.com/g", "published": None}]

    monkeypatch.setattr(news_mod, "_fetch_bing_news", empty("bing"))
    monkeypatch.setattr(news_mod, "_fetch_google_news", hit)
    monkeypatch.setattr(news_mod, "_fetch_yahoo_news", empty("yahoo"))

    result = news_mod.fetch_for_query("ASML Holding", limit=3)

    assert seen == ["bing", "google"]
    assert result["providers_used"] == ["google"]


# ---------------------------------------------------------------------------
# Resolution — ISIN, Valor, name
# ---------------------------------------------------------------------------

def test_resolve_matches_isin_valor_and_name():
    isin_hit = resolve("NL0010273215")
    assert isin_hit["matched"] is True
    assert isin_hit["matched_on"] == "isin"
    assert isin_hit["security"]["Isin"] == "NL0010273215"

    security = isin_hit["security"]
    valor_hit = resolve(str(security.get("Valor")))
    assert valor_hit["matched"] is True
    assert valor_hit["matched_on"] == "valor"
    assert valor_hit["security"]["Id"] == security["Id"]

    name_hit = resolve("ASML Holding")
    assert name_hit["matched"] is True
    assert name_hit["matched_on"] == "name"
    assert name_hit["security"]["Id"] == security["Id"]


def test_resolve_reports_unknown_and_too_short_queries_as_a_miss():
    assert resolve("")["matched"] is False
    assert resolve("Zz")["matched"] is False
    assert resolve("Some Company That Does Not Exist")["matched"] is False


# ---------------------------------------------------------------------------
# Composition — the miss is declared, coverage still stands
# ---------------------------------------------------------------------------

def test_unmatched_instrument_is_refused_without_a_market_search(monkeypatch, tmp_path: Path):
    """Out of scope by design: coverage is tied to the bank's own instruments, not the open web."""
    seen: list[str] = []
    _stub_providers(monkeypatch, tmp_path, seen)

    query = "Some Company That Does Not Exist"
    result = search_module.search(query, lang="en", limit=3)

    assert seen == [], "no provider may be asked for a company the bank's data does not contain"
    assert result["instrument"]["matched"] is False
    assert result["news"]["items"] == []
    assert result["news"]["providers_used"] == []
    assert result["held_by"] == []
    assert result["held_by_total"] == 0
    assert result["portfolio_weight"] is None
    assert result["query_kind"] is None
    assert any(query in gap for gap in result["unavailable"])
    assert any("not an instrument in the bank's data" in gap for gap in result["unavailable"])


def test_unmatched_instrument_keeps_the_same_key_set(monkeypatch, tmp_path: Path):
    """The panel renders one field grid, so the shape may not vary between a hit and a miss.

    The miss branch used to omit ``recommendation_lists`` (and every other detail field), which the
    UI read as ``undefined`` and crashed the whole screen on a query the master does not carry — the
    normal case for a company outside the trimmed master.
    """
    seen: list[str] = []
    _stub_providers(monkeypatch, tmp_path, seen)

    matched = search_module.search("ASML Holding", lang="en", limit=1)["instrument"]
    unmatched = search_module.search("Some Company That Does Not Exist", lang="en", limit=1)["instrument"]

    assert set(matched) == set(unmatched)
    assert unmatched["matched"] is False
    assert matched["matched"] is True
    assert unmatched["recommendation_lists"] == []
    assert unmatched["alternatives"] == []
    assert unmatched["share_class_count"] == 0
    assert all(
        unmatched[key] is None
        for key in ("name", "display_name", "isin", "valor", "currency", "bank_rating", "price")
    )


def test_query_kind_reports_how_the_row_was_found(monkeypatch, tmp_path: Path):
    """The chip the advisor sees says whether their ISIN, valor or name matched."""
    seen: list[str] = []
    _stub_providers(monkeypatch, tmp_path, seen)

    by_isin = search_module.search("NL0010273215", lang="en", limit=1)
    by_valor = search_module.search("19531091", lang="en", limit=1)
    by_name = search_module.search("ASML Holding", lang="en", limit=1)

    assert (by_isin["query_kind"], by_valor["query_kind"], by_name["query_kind"]) == ("isin", "valor", "name")
    for result in (by_isin, by_valor, by_name):
        assert result["instrument"]["security_id"] == by_isin["instrument"]["security_id"]


def test_a_private_instrument_is_refused_like_the_briefing_path_does(monkeypatch, tmp_path: Path):
    """SpaceX is in the master but has no public coverage; the two paths must agree."""
    dataset = index.get()
    private = [
        security for security in dataset.securities
        if news_mod.is_private_instrument(security.get("Isin"))
    ]
    assert private, "the private instrument is expected to be part of the dataset"

    seen: list[str] = []
    _stub_providers(monkeypatch, tmp_path, seen)
    result = search_module.search(str(private[0].get("Isin")), lang="en", limit=3)

    assert seen == []
    assert result["instrument"]["matched"] is True, "the instrument is known, its coverage is not"
    assert result["news"]["items"] == []
    assert result["unavailable"] == [news_mod.t("news.private_instrument", "en")]


def test_offline_search_declares_the_gap_instead_of_returning_nothing(offline):
    result = search_module.search("ASML Holding", lang="en", limit=3)

    assert result["news"]["items"] == []
    assert result["unavailable"], "an offline search must say why it has nothing"
    assert result["instrument"]["matched"] is True, "resolution is local and works offline"


# ---------------------------------------------------------------------------
# Holders — completeness, and never summed across share classes
# ---------------------------------------------------------------------------

def test_holders_match_the_positions_that_actually_hold_the_instrument(offline):
    dataset = index.get()

    # Every held ISIN, with the set of master ids positions reference under it.
    expected: dict[str, set[tuple[str, str]]] = defaultdict(set)
    identifiers: dict[str, set[int]] = defaultdict(set)
    for client in dataset.clients:
        ref = client.get("ClientRef")
        for portfolio in client.get("Portfolios") or []:
            nr = portfolio.get("PortfolioNr")
            for position in portfolio.get("SecurityPositions") or []:
                isin = position.get("Isin")
                if isin and position.get("SecurityId") is not None:
                    expected[isin].add((ref, nr))
                    identifiers[isin].add(int(position["SecurityId"]))

    assert expected, "the case data holds positions; this test is meaningless without them"

    for isin in list(expected)[:5]:
        result = search_module.search(isin, lang="en", limit=1)
        returned = {(holder["client_ref"], holder["portfolio_nr"]) for holder in result["held_by"]}
        assert returned == expected[isin], f"holder set wrong for {isin}"


def test_holder_weight_is_the_position_weight_from_the_data(offline):
    dataset = index.get()
    for client in dataset.clients:
        for portfolio in client.get("Portfolios") or []:
            for position in portfolio.get("SecurityPositions") or []:
                isin = position.get("Isin")
                if not isin or position.get("SecurityId") is None:
                    continue
                result = search_module.search(isin, lang="en", limit=1)
                for holder in result["held_by"]:
                    if holder["portfolio_nr"] == portfolio.get("PortfolioNr"):
                        assert holder["weight"] == pytest.approx(position["PortfolioValuePercentage"])
                        return
    pytest.fail("no position found to check the holder weight against")


# ---------------------------------------------------------------------------
# Endpoint contract
# ---------------------------------------------------------------------------

def test_endpoint_returns_the_documented_shape(client: TestClient, offline):
    response = client.get("/api/market/search", params={"q": "ASML Holding", "lang": "en"})
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["query"] == "ASML Holding"
    assert body["query_kind"] == "name"
    assert set(body) == {
        "query", "query_kind", "as_of", "instrument", "news", "signals", "bank_view",
        "held_by", "held_by_total", "portfolio_weight", "unavailable",
    }
    assert set(body["signals"]) == {"applied", "reason", "model", "items"}
    assert body["instrument"]["matched"] is True
    assert set(body["instrument"]) >= {
        "security_id", "name", "display_name", "isin", "currency", "asset_class",
        "bank_rating", "share_class_count", "alternatives",
    }
    assert body["bank_view"]["mock"] is True
    assert body["bank_view"]["stances"], "a resolved instrument with categories has CIO stances"


def test_endpoint_rejects_an_empty_query(client: TestClient):
    assert client.get("/api/market/search", params={"q": ""}).status_code == 422


def test_endpoint_falls_back_to_english_for_an_unsupported_language(client: TestClient, offline):
    """An unknown language must serve the default, never a half-translated payload."""
    english = client.get("/api/market/search", params={"q": "Unknown Company Zz", "lang": "en"}).json()
    unsupported = client.get("/api/market/search", params={"q": "Unknown Company Zz", "lang": "fr"}).json()

    assert unsupported["unavailable"] == english["unavailable"]
    assert unsupported["unavailable"], "an unmatched query declares itself in both cases"
