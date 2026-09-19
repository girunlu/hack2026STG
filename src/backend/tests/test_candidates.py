"""Contract tests for the named buy / sell / switch candidates (`REVIEW.md` §11.1.1).

The brief lists *"Identifying securities to buy, sell or switch"* as a possible next best action and
`REVIEW.md` §9.4 measured it at **0/47 clients**. These tests hold the properties that make a named
instrument defensible rather than invented:

* every name comes from the bank's own data — an open (``Entwurf``) proposal's target weights, or a
  member of ``reference.RecommendationLists`` in an asset class below its SAA target;
* every exclusion, drop and undeterminable classification is reported, never silently applied.
"""

from __future__ import annotations

import pytest

from app.domain import candidates
from app.domain.ingest import listof, text

SOURCES = {"clients.json", "reference.json", "computed"}


def shipped_refs(dataset) -> list[str]:
    """The 47 case clients; uploads are isolated per session by ``conftest``."""
    return sorted(text(c, "ClientRef") for c in dataset.clients if text(c, "ClientRef").startswith("CASE-"))


def draft_proposals(dataset, client_ref: str) -> list[dict]:
    client = dataset.client(client_ref)
    return [p for p in listof(client, "Proposals")
            if text(p, "ProposalStatusName") == candidates.OPEN_PROPOSAL_STATUS]


# ----------------------------------------------------------------------------------------------------
# proposal moves
# ----------------------------------------------------------------------------------------------------

def test_open_proposal_names_the_instruments_it_moves(dataset):
    """CASE-045's draft exits two large lines and builds new ones — both legs are named."""
    rows = candidates.proposal_moves("CASE-045")
    assert rows, "the draft proposal produced no named instrument"

    exits = {row["isin"]: row for row in rows if row["reason_code"] == candidates.REASON_PROPOSAL_EXIT}
    novartis = exits.get("CH0012005267")
    assert novartis is not None, f"Novartis is not reported as exited: {sorted(exits)}"
    assert novartis["direction"] == candidates.SELL
    assert novartis["target_weight"] == 0.0
    assert novartis["delta"] == pytest.approx(-novartis["current_weight"])
    assert novartis["security_id"] == 264  # the held position's own id, never an ISIN guess

    buys = [row for row in rows if row["direction"] == candidates.BUY]
    assert buys and all(row["target_weight"] >= candidates.MIN_TARGET_WEIGHT for row in buys)
    # One proposal, both directions, one asset class: the brief's "switch", reported as two legs.
    assert {row["asset_class"] for row in exits.values()} & {row["asset_class"] for row in buys}
    assert all(row["proposal_status"] == "Entwurf" and row["proposal_id"] for row in rows)


def test_immaterial_draft_produces_no_moves(dataset):
    """CASE-034's draft re-weights nothing by a percentage point, so it names nothing.

    Without the materiality threshold this proposal yields 22 rows of rounding noise — an advisor
    cannot act on "increase 7.49% to 7.55%".
    """
    drafts = draft_proposals(dataset, "CASE-034")
    assert drafts and len(listof(drafts[0], "SecurityPositions")) > 10, "fixture changed: no real draft"
    assert candidates.proposal_moves("CASE-034") == []


def test_amounts_keep_their_own_currency(dataset):
    """No FX is invented: an amount is always reported with the currency it is stated in."""
    checked = 0
    for ref in shipped_refs(dataset):
        for row in candidates.proposal_moves(ref):
            if row["amount"] is None:
                continue
            checked += 1
            assert row["amount_currency"], f"{ref}: amount without a currency: {row['isin']}"
            expected = ("TotalAmountInPortfolioCurrency" if row["reason_code"] == candidates.REASON_PROPOSAL_EXIT
                        else "TotalAmountInProposalCurrency")
            assert any(item["label"] == expected for item in row["evidence"]), \
                f"{ref}: {row['isin']} cites no amount source"
    assert checked > 10, f"only {checked} amounts checked — the test is not covering the extractor"


# ----------------------------------------------------------------------------------------------------
# recommendation-list buys
# ----------------------------------------------------------------------------------------------------

def test_buy_candidates_are_list_members_and_not_already_held(dataset):
    """A named buy must be in the bank's universe and must not be a position the client has."""
    checked = 0
    for ref in shipped_refs(dataset):
        for row in candidates.candidates(ref)["buys"]:
            checked += 1
            assert dataset.in_recommendation_list(row["security_id"]), f"{ref}: {row['name']} is not a list member"
            assert row["recommendation_lists"], f"{ref}: {row['name']} names no list"
            _, portfolio = dataset.portfolio(ref, row["portfolio_nr"])
            held = {text(p, "Isin") for p in listof(portfolio, "SecurityPositions")}
            assert row["isin"] not in held, f"{ref}: {row['name']} is already held"
            assert row["asset_class"] == row["target_category"]
            assert row["difference"] <= -candidates.DRIFT_THRESHOLD, \
                f"{ref}: {row['target_category']} is not underweight"
    assert checked > 50, f"only {checked} candidates checked — the test is not covering the extractor"


def test_client_preference_rules_out_contradicting_names(dataset):
    """CASE-007 asks to avoid fossil-fuel energy: no Energy name is offered, and the drop is named."""
    bundle = candidates.candidates("CASE-007")
    assert bundle["buys"], "CASE-007 is 18.3 pp below its equity target and should get names"
    assert all(row["industry"] != "Energy" for row in bundle["buys"])

    assert any("Exxon" in str(row["name"]) for row in bundle["excluded"]), bundle["excluded"]
    assert all(row["keyword"] == "fossil" for row in bundle["excluded"])
    assert all(str(row["note_path"]).startswith("clients[CASE-007].ClientNotes[") for row in bundle["excluded"])
    pool = next(p for p in bundle["buy_pools"] if p["category"] == "Shares")
    assert pool["excluded_by_preference"] == len(bundle["excluded"])
    assert pool["pool_size"] > pool["offered"], "the disclosure must show that names were dropped"


def test_every_pool_discloses_what_it_dropped(dataset):
    """The cap is a choice, so each class reports its pool, its offer and its ranking rule."""
    for ref in shipped_refs(dataset):
        bundle = candidates.candidates(ref)
        for pool in bundle["buy_pools"]:
            offered = [row for row in bundle["buys"]
                       if row["portfolio_nr"] == pool["portfolio_nr"] and row["target_category"] == pool["category"]]
            assert len(offered) == pool["offered"] <= candidates.MAX_BUYS_PER_CLASS
            assert pool["offered"] <= pool["pool_size"]
            assert pool["ranked_by"] == list(candidates.RANKED_BY)
            assert [row["rank"] for row in offered] == list(range(1, len(offered) + 1))
        if not bundle["buy_pools"]:
            assert not bundle["buys"], f"{ref}: buys without a pool disclosure"


def test_missing_strategy_is_declared_not_guessed(dataset):
    """CASE-038-01 sits on SAA 96, which carries no usable target: a gap, and no invented candidate."""
    bundle = candidates.candidates("CASE-038")
    assert {"code": "saa_unavailable", "client_ref": "CASE-038", "portfolio_nr": "CASE-038-01"} in bundle["gaps"]
    assert all(row["portfolio_nr"] == "CASE-038-02" for row in bundle["buys"])


# ----------------------------------------------------------------------------------------------------
# honesty of the joins
# ----------------------------------------------------------------------------------------------------

def test_ambiguous_isin_never_borrows_a_sibling_classification(dataset):
    """One ISIN, two currency share classes that disagree on the list: no verdict is picked."""
    security_id, asset_class, industry, in_list, ambiguous = candidates._classification("IE00B5BMR087")
    rows = dataset.securities_by_isin("IE00B5BMR087")
    assert len(rows) > 1 and ambiguous is True
    assert asset_class == "Shares"  # both rows agree, so it is safe to report
    assert in_list is None  # the two rows disagree — reporting either would be a guess
    assert security_id is None

    unique = candidates._classification("CH0012005267")
    assert unique[0] == 264 and unique[4] is False and unique[3] is True

    unknown = candidates._classification("NOT-A-REAL-ISIN")
    assert unknown == (None, None, None, None, False)


def test_portfolio_scope_restricts_every_row(dataset):
    """``portfolio_nr`` narrows the bundle; CASE-036 only has candidates in its second portfolio."""
    assert {p["portfolio_nr"] for p in candidates.candidates("CASE-036")["buy_pools"]} == {"CASE-036-02"}
    scoped_out = candidates.candidates("CASE-036", "CASE-036-01")
    assert scoped_out["buys"] == [] and scoped_out["buy_pools"] == [] and scoped_out["moves"] == []
    scoped_in = candidates.candidates("CASE-036", "CASE-036-02")
    assert scoped_in["buys"] == candidates.candidates("CASE-036")["buys"]
    assert all(row["portfolio_nr"] == "CASE-036-02" for row in scoped_in["buys"])


def test_every_row_carries_evidence_in_the_contract_shape(dataset):
    """PROJECT.md §8: no row without evidence, and every entry in the §5.2 shape."""
    rows = 0
    for ref in shipped_refs(dataset):
        bundle = candidates.candidates(ref)
        for row in bundle["buys"] + bundle["moves"]:
            rows += 1
            assert row["evidence"], f"{ref}: a candidate without evidence"
            for item in row["evidence"]:
                assert set(item) == {"label", "value", "source", "path", "unit"}, item
                assert item["source"] in SOURCES, item
                assert str(item["label"]).strip() and str(item["path"]).strip(), item
                if item["source"] != "computed":
                    assert item["path"].startswith(f"clients[{ref}]."), item
    assert rows > 80, f"only {rows} rows checked — the test is not covering the extractor"


def test_unknown_client_returns_an_empty_bundle(dataset):
    bundle = candidates.candidates("CASE-NOPE")
    assert bundle == {"scope": {"client_ref": "CASE-NOPE", "portfolio_nr": None},
                      "moves": [], "buys": [], "buy_pools": [], "excluded": [], "gaps": []}
    assert candidates.proposal_moves("CASE-NOPE") == []


def test_the_brief_action_is_no_longer_empty(dataset):
    """0/47 -> a named instrument for a substantial part of the case data, deterministically."""
    with_moves, with_buys = set(), set()
    for ref in shipped_refs(dataset):
        bundle = candidates.candidates(ref)
        if bundle["moves"]:
            with_moves.add(ref)
        if bundle["buys"]:
            with_buys.add(ref)
    assert len(shipped_refs(dataset)) == 47
    assert with_moves == {"CASE-017", "CASE-037", "CASE-042", "CASE-045"}
    assert len(with_buys) >= 15, with_buys
    assert len(with_moves | with_buys) >= 18
    # The same input twice must give the same rows: no set or dict ordering may leak into a briefing.
    assert candidates.candidates("CASE-045") == candidates.candidates("CASE-045")
