"""Guards for the risk figures the provided data overflows.

One position in the case data — ``CASE-041-01`` / ``XS1412417617`` — carries a
``MarginalContributionToRisk`` of 9'223'372.03685 (an int64-overflow sentinel), which turns its
``ContributionVolatility`` into 574'339.3767 against a portfolio volatility of 0.098. Before this
guard existed the figure reached the positions table as ``57433937.67%`` and R3's risk driver would
have claimed a ~586-million-percent share of portfolio risk.

The rule these tests defend: a risk figure that cannot be true is never served and never claimed — it
is withheld and declared, exactly like every other gap in this project.
"""

from __future__ import annotations

import pytest

from app.domain import index, metrics

# A contribution is a fraction of the portfolio's own volatility. The tolerance absorbs rounding in
# the export, where the strict identity ``sum(ContributionVolatility) == Volatility`` holds for only
# 14 of 57 portfolios — a tight bound would test the data instead of the guard.
VOLA_TOLERANCE = 1.02


@pytest.fixture(scope="session")
def portfolios(dataset) -> dict[str, dict]:
    return {portfolio["PortfolioNr"]: portfolio for _, portfolio in dataset.portfolios.values()}


def _all_portfolios():
    """(client_ref, portfolio) for every portfolio currently loaded."""
    for (client, portfolio) in index.get().portfolios.values():
        yield client["ClientRef"], portfolio


def test_overflowing_contribution_is_detected(portfolios):
    """The sentinel row is found and named, and the rest of that portfolio stays usable."""
    risk = metrics.risk_contributions(portfolios["CASE-041-01"])

    assert len(risk["dropped"]) == 1
    dropped = risk["dropped"][0]
    assert dropped["name"].startswith("1.25 % National Australia Bank")
    assert dropped["contribution"] > 1  # impossible as a fraction of volatility
    assert "exceeds" in dropped["reason"]
    # The portfolio still has a usable series, and it is a fraction — not the 574'339 artefact.
    assert risk["available"] is True
    assert 0 < risk["sum"] < 1


def test_unpopulated_series_is_declared_unavailable(portfolios):
    """CASE-023-01 has a volatility but no contributions at all: unavailable, with a reason."""
    risk = metrics.risk_contributions(portfolios["CASE-023-01"])

    assert risk["available"] is False
    assert risk["reason"]
    assert risk["dropped"] == []  # nothing is discarded — there is simply nothing there


def test_no_portfolio_serves_an_implausible_risk_figure(api):
    """Across every F4 response, a served risk figure stays inside its own portfolio volatility."""
    checked = 0
    withheld = 0
    for client_ref, portfolio in _all_portfolios():
        response = api.get(f"/api/clients/{client_ref}/portfolios/{portfolio['PortfolioNr']}")
        assert response.status_code == 200, f"{portfolio['PortfolioNr']}: {response.status_code}"
        body = response.json()
        volatility = body["portfolio"]["volatility"]
        limit = (volatility or 1.0) * VOLA_TOLERANCE + 1e-9
        for row in body["positions"]:
            if row["risk_figure_dropped"]:
                withheld += 1
                assert row["risk_contribution"] is None
                continue
            if row["risk_contribution"] is None:
                continue
            assert abs(row["risk_contribution"]) <= limit, (
                f"{portfolio['PortfolioNr']} {row['position']}: "
                f"{row['risk_contribution']} exceeds volatility {volatility}"
            )
            checked += 1
    assert checked > 600  # 703 positions minus the withheld ones
    assert withheld == 1  # exactly the sentinel row, no more


def test_withheld_figure_is_declared_not_hidden(api):
    """The F4 payload names the withheld figure and marks the row instead of rendering a number."""
    body = api.get("/api/clients/CASE-041/portfolios/CASE-041-01").json()

    flagged = [row for row in body["positions"] if row["risk_figure_dropped"]]
    assert len(flagged) == 1
    assert flagged[0]["risk_contribution"] is None
    assert flagged[0]["marginal_risk"] is None
    assert any("Risk contribution withheld" in gap for gap in body["data_gaps"])


def test_risk_driver_never_claims_a_withheld_figure(dataset):
    """R3's risk driver stays inside the portfolio volatility, and cites the position it names."""
    from app.domain import relevance

    seen = 0
    for client in dataset.clients:
        client_ref = client["ClientRef"]
        for finding in relevance.findings(client_ref):
            if finding["type"] != "performance_driver":
                continue
            contribution = next(
                (e["value"] for e in finding["evidence"] if e["label"] == "ContributionVolatility"), None
            )
            volatility = next(
                (e["value"] for e in finding["evidence"] if e["label"] == "Portfolio.Volatility"), None
            )
            assert contribution is not None and volatility is not None
            assert contribution <= volatility * VOLA_TOLERANCE + 1e-9, (
                f"{client_ref}: driver claims {contribution} against volatility {volatility}"
            )
            assert any("SecurityPositions[" in e["path"] for e in finding["evidence"])
            seen += 1
    assert seen > 20  # the driver fires broadly; a silent regression to zero would fail here
