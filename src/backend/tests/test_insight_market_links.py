"""A company insight must lead to that company's market results.

The brief asks the briefing to connect the portfolio to the market (L139–144, L189–191). A sentence
that names an instrument but cannot reach its coverage leaves the advisor to retype the name, so a
block that is about one instrument carries its id and ISIN and the UI turns that into a control. These
assert the payload side of that contract, including the cases that must *not* be tagged.
"""

from __future__ import annotations

import pytest

from app.compose import facts as facts_module
from app.compose import render as render_module
from app.domain import index


def _briefing(client_ref: str, portfolio_nr: str | None = None, lang: str = "en") -> dict:
    bundle = facts_module.assemble(client_ref, portfolio_nr, None, lang)
    return {"facts": bundle, "briefing": render_module.render(bundle, render_module.TEMPLATE, lang)}


def test_concentration_insight_carries_the_instrument_it_is_about():
    """CASE-028 is 95.85% in one holding: the concentration block must name it, not just its weight."""
    data = _briefing("CASE-028", "CASE-028-01")
    blocks = [
        block
        for section in data["briefing"]["sections"]
        for block in section["blocks"]
        if "Concentration risk" in block["text"]
    ]
    assert blocks, "this client is concentrated enough to produce the finding"
    block = blocks[0]
    assert block["isin"] == "CH0528751586"
    assert block["security_id"] is not None

    # The ISIN must be the one the market search accepts, and it must be the holding in question.
    security = index.get().security_by_isin(block["isin"])
    assert security and int(security["Id"]) == block["security_id"]
    assert "VZ Holding" in str(security["Name"])


def test_market_block_carries_the_instrument_it_quotes(monkeypatch):
    """End to end through R2 → R4 with a stubbed provider, so no network and no client upload."""
    from app.external import news as news_module

    holding_id = 18477  # CASE-028-01's VZ Holding, the position the headline is about
    monkeypatch.setattr(
        news_module,
        "fetch_market_context",
        lambda securities=None, **kwargs: {
            "items": [{
                "headline": "VZ Gruppe steigert Gewinn",
                "source": "Test",
                "url": "https://example.test/vz",
                "published": None,
                "linked_security_ids": [holding_id],
                "linked_sectors": [],
                "relevant_because": "Client holds 95.85% in Namen-Aktie VZ Holding AG.",
            }],
            "unavailable": [],
            "providers_used": ["bing"],
            "fetched_at": None,
            "notes": [],
        },
    )

    data = _briefing("CASE-028", "CASE-028-01")
    market_blocks = [
        block
        for section in data["briefing"]["sections"]
        for block in section["blocks"]
        if block["text"].startswith("**Market:**")
    ]
    assert market_blocks, "the stubbed headline must reach the briefing"
    block = market_blocks[0]
    assert block["isin"] == "CH0528751586"
    assert block["security_id"] == holding_id
    assert index.get().security_by_isin(block["isin"])


def test_a_block_about_the_portfolio_is_never_tagged():
    """A currency, a rule or an allocation has no market results — the control must not appear."""
    data = _briefing("CASE-007", None)
    for section in data["briefing"]["sections"]:
        for block in section["blocks"]:
            if "Currency risk" in block["text"] or "Strategy deviation" in block["text"]:
                assert not block.get("isin")


def test_instrument_tag_matches_the_finding_behind_the_block():
    """The tag is copied from the block's own finding, so the sentence and the link cannot diverge."""
    data = _briefing("CASE-028", "CASE-028-01")
    findings = {str(finding["id"]): finding for finding in data["facts"]["findings"]}

    tagged = [
        block
        for section in data["briefing"]["sections"]
        for block in section["blocks"]
        if block.get("isin")
    ]
    assert tagged

    for block in tagged:
        finding_refs = [ref for ref in block["evidence_refs"] if str(ref).startswith("finding:")]
        if not finding_refs:
            continue  # a market block: its ref is a news item, tagged where it is built
        finding = findings[str(finding_refs[0]).split(":", 1)[1].split("#", 1)[0]]
        assert block["isin"] == finding["isin"]


def test_blocks_about_the_portfolio_are_not_tagged():
    """A currency, a rule or an allocation has no market results — the control must not appear."""
    data = _briefing("CASE-007", None)
    for section in data["briefing"]["sections"]:
        for block in section["blocks"]:
            if "Currency risk" in block["text"] or "Strategy deviation" in block["text"]:
                assert not block.get("isin")


def test_the_localized_briefing_carries_the_same_instruments():
    """A German reader gets the same links: the tag is locale-independent."""
    english = _briefing("CASE-028", "CASE-028-01", "en")
    german = _briefing("CASE-028", "CASE-028-01", "de")

    def tags(data: dict) -> list[str | None]:
        return [
            block.get("isin")
            for section in data["briefing"]["sections"]
            for block in section["blocks"]
        ]

    assert tags(english) == tags(german)
