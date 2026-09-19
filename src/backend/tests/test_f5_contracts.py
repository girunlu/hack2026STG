"""F5 contract tests — the invariants the whole product rests on.

These are not unit tests of implementation details; they pin the behavioural promises that
``app.domain.ingest``, ``app.domain.index`` and ``app.domain.metrics`` make to every downstream
consumer (F2/F3/F4, the briefing pipeline, the UI). If any of these regress, the demo breaks.

Run with::

    python -m pytest tests/test_f5_contracts.py -q
"""

from __future__ import annotations

import json

import pytest

from app.domain import index, ingest, metrics


# --------------------------------------------------------------------------- loading


def test_dataset_loads_47_clients_and_57_portfolios(dataset):
    """The case data ships exactly 47 clients and 57 portfolios; anything else is a load failure."""
    assert len(dataset.clients) == 47
    assert len(dataset.portfolios) == 57


def test_eight_portfolios_have_absent_securitypositions_treated_as_empty(dataset):
    """Eight portfolios have the ``SecurityPositions`` *key* missing entirely. ``listof`` must
    treat that the same as an empty list — no KeyError, no None, no invented positions."""
    absent = [
        nr for nr, (_, p) in dataset.portfolios.items()
        if "SecurityPositions" not in p
    ]
    assert len(absent) == 8
    for nr in absent:
        _, portfolio = dataset.portfolios[nr]
        # listof on an absent key returns []; portfolio_value sums to the cash accounts only.
        assert ingest.listof(portfolio, "SecurityPositions") == []
        # The portfolio screen must still render: value is the sum of cash accounts.
        assert metrics.portfolio_value(portfolio) >= 0.0


def test_fortyfour_null_individual_rule_overrides_behave_as_empty(dataset):
    """44 clients carry an explicit ``null`` for ``IndividualRuleOverrides``; ``listof`` must
    behave identically to an absent key — returning ``[]``."""
    nulls = [
        ingest.text(c, "ClientRef")
        for c in dataset.clients
        if ingest.opt(c, "IndividualRuleOverrides") is None
    ]
    assert len(nulls) == 44
    for ref in nulls:
        client = dataset.client(ref)
        assert ingest.listof(client, "IndividualRuleOverrides") == []


# --------------------------------------------------------------------------- integrity


def test_integrity_report_lists_dangling_refs_as_data(dataset):
    """Dangling portfolio references are DATA, not exceptions. The report must enumerate all 28
    (CASE-008: 13, CASE-038: 15 — a mix of violations and one proposal) without raising."""
    report = dataset.integrity_report()
    dangling = report["dangling_portfolio_refs"]
    assert len(dangling) == 28
    by_client = {}
    for row in dangling:
        by_client.setdefault(row["client_ref"], 0)
        by_client[row["client_ref"]] += 1
    assert by_client == {"CASE-008": 13, "CASE-038": 15}
    # Every entry names a real client and a portfolio id that exists on no client.
    for row in dangling:
        assert dataset.client(row["client_ref"]) is not None
        assert row["portfolio_id"] not in dataset.portfolio_ids_of(row["client_ref"])


def test_integrity_report_lists_four_null_risk_profiles(dataset):
    """CASE-029 through CASE-032 have no ``RiskProfileId``; the report must name them."""
    report = dataset.integrity_report()
    assert sorted(report["clients_without_risk_profile"]) == [
        "CASE-029", "CASE-030", "CASE-031", "CASE-032",
    ]


def test_integrity_report_never_raises(dataset):
    """Even on dirty data, ``integrity_report`` must return a dict — never raise."""
    report = dataset.integrity_report()
    assert isinstance(report, dict)
    for key in ("dangling_portfolio_refs", "clients_without_risk_profile",
                "portfolios_without_positions", "counts"):
        assert key in report


# --------------------------------------------------------------------------- returns


def test_returns_case007_matches_hand_calculation(dataset):
    """CASE-007-01: +15.15% over 12m and +7.67% over 3m, computed from ``PerformanceHistory``
    (monthly points). These are the numbers the UI shows; any drift is a regression."""
    client = dataset.client("CASE-007")
    portfolio = next(
        p for p in ingest.listof(client, "Portfolios")
        if ingest.text(p, "PortfolioNr") == "CASE-007-01"
    )
    result = metrics.returns(portfolio)
    assert result["return_12m_pct"] == pytest.approx(15.15, abs=0.01)
    assert result["return_3m_pct"] == pytest.approx(7.67, abs=0.01)
    assert result["source"] == "PerformanceHistory"


def test_performance_ytd_is_never_read_from_data(dataset):
    """``PerformanceYTD`` is absent on every portfolio in the case data. The backend must not
    read it — returns come from ``PerformanceHistory`` only."""
    for _, portfolio in dataset.portfolios.values():
        assert "PerformanceYTD" not in portfolio
    # And the returns function must still produce a ytd value by computing it from history.
    client = dataset.client("CASE-007")
    portfolio = next(
        p for p in ingest.listof(client, "Portfolios")
        if ingest.text(p, "PortfolioNr") == "CASE-007-01"
    )
    result = metrics.returns(portfolio)
    assert result["return_ytd_pct"] is not None
    assert result["note"].startswith("PerformanceYTD is not present")


# --------------------------------------------------------------------------- SAA


def test_saa_deviation_saa96_returns_unavailable_without_raising(dataset):
    """SAA 96 is the real 'Keine Strategie' case: its AssetClass rows carry no min/target/max.
    ``saa_deviation`` must return ``available == False`` with reason 'Keine Strategie' — never raise."""
    portfolio_nr = next(
        nr for nr, (_, p) in dataset.portfolios.items()
        if ingest.intnum(p, "StrategicAssetAllocationId", -1) == 96
    )
    _, portfolio = dataset.portfolios[portfolio_nr]
    result = metrics.saa_deviation(portfolio)
    assert result["available"] is False
    assert result["reason"] == "Keine Strategie"
    assert result["rows"] == []


def test_saa_deviation_case007_shares_actual_vs_target(dataset):
    """CASE-007-01: Shares actual 0.567 vs target 0.75 — the UI's headline rebalance gap."""
    client = dataset.client("CASE-007")
    portfolio = next(
        p for p in ingest.listof(client, "Portfolios")
        if ingest.text(p, "PortfolioNr") == "CASE-007-01"
    )
    result = metrics.saa_deviation(portfolio)
    assert result["available"] is True
    shares = next(row for row in result["rows"] if row["category"] == "Shares")
    assert shares["actual"] == pytest.approx(0.567, abs=0.001)
    assert shares["target"] == pytest.approx(0.75, abs=0.001)
    assert shares["difference"] < 0  # underweight


# --------------------------------------------------------------------------- fund look-through


def test_fund_lookthrough_weights_sum_to_one(dataset):
    """``FundUnbundlingMappings.Weight`` is 0–100; per-fund sums are ≈100. ``lookthrough``
    divides by 100 and must yield weights that sum to ≈1.0 (within 2%)."""
    funds = {}
    for row in dataset.all_fund_mappings:
        fid = ingest.intnum(row, "FundSecurityId", -1)
        funds.setdefault(fid, []).append(row)
    # Pick a fund with a meaningful number of rows.
    fid = next(fid for fid, rows in funds.items() if len(rows) > 5)
    lt = metrics.lookthrough(fid, "asset_class")
    total = sum(row["weight"] for row in lt)
    assert total == pytest.approx(1.0, abs=0.02)


def test_lookthrough_does_not_clamp_negative_weights(dataset):
    """The case data has 484 negative-weight rows. ``lookthrough`` must pass them through
    unchanged — no clamping, no abs, no filtering."""
    negative_funds = {
        ingest.intnum(r, "FundSecurityId", -1)
        for r in dataset.all_fund_mappings
        if ingest.num(r, "Weight") < 0
    }
    assert len(negative_funds) > 0
    for fid in list(negative_funds)[:5]:
        lt = metrics.lookthrough(fid, "asset_class")
        raw_total = sum(ingest.num(r, "Weight") for r in dataset.fund_mappings(fid)) / 100.0
        lt_total = sum(row["weight"] for row in lt)
        # The look-through total must match the raw sum (within rounding), including negatives.
        assert lt_total == pytest.approx(raw_total, abs=0.001)


# --------------------------------------------------------------------------- ingest helpers


def test_opt_treats_absent_and_null_identically():
    """``opt`` is the foundation of the null-tolerant ingest layer: a missing key and an
    explicit ``null`` must be indistinguishable."""
    assert ingest.opt({"a": 1}, "b") is None
    assert ingest.opt({"a": 1, "b": None}, "b") is None
    assert ingest.opt({"a": 1}, "b") == ingest.opt({"a": 1, "b": None}, "b")


def test_num_never_returns_none():
    """``num`` must always return a float — never ``None``, even on absent or null keys."""
    assert ingest.num({}, "missing") == 0.0
    assert ingest.num({"x": None}, "x") == 0.0
    assert ingest.num({"x": "not a number"}, "x") == 0.0
    assert isinstance(ingest.num({}, "anything"), float)


def test_redact_removes_iban_keys():
    """``redact`` must strip every ``IBAN`` key, recursively, at any depth."""
    payload = {
        "IBAN": "CH12 3456 7890",
        "keep": 1,
        "nested": [{"IBAN": "CH00", "x": 1}, {"y": 2}],
    }
    cleaned = ingest.redact(payload)
    serialised = json.dumps(cleaned)
    assert "IBAN" not in serialised
    assert "CH12" not in serialised
    assert cleaned["keep"] == 1
    assert cleaned["nested"][0] == {"x": 1}


def test_no_endpoint_response_contains_iban(api):
    """The API boundary must redact IBANs from every response — F2, F3 and F4 alike."""
    # F2 — all clients
    r = api.get("/api/clients")
    assert r.status_code == 200
    assert "IBAN" not in r.text
    # F3 — one client (CASE-007 has cash accounts with IBANs)
    r = api.get("/api/clients/CASE-007")
    assert r.status_code == 200
    assert "IBAN" not in r.text
    # F4 — one portfolio
    r = api.get("/api/clients/CASE-007/portfolios/CASE-007-01")
    assert r.status_code == 200
    assert "IBAN" not in r.text
