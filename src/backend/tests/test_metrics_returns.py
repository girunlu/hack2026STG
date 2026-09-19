"""Tests for the return_available_* and return_basis keys in metrics.returns()."""

from __future__ import annotations

import pytest

from app.domain import metrics


def _make_portfolio(points: list[tuple[str, float]]) -> dict:
    """Build a minimal portfolio dict with the given PerformanceHistory."""
    return {
        "PerformanceHistory": [{"Date": d, "Value": v} for d, v in points],
    }


def test_12_point_series_uses_available_span():
    """12 monthly points (span ~11 months) → return_12m_pct None, return_available_pct ≈ 11.11."""
    # 12 points: 450000 → 500000 over 11 months
    points = [
        ("2025-01-31", 450000.0),
        ("2025-02-28", 455000.0),
        ("2025-03-31", 460000.0),
        ("2025-04-30", 465000.0),
        ("2025-05-31", 470000.0),
        ("2025-06-30", 475000.0),
        ("2025-07-31", 480000.0),
        ("2025-08-31", 485000.0),
        ("2025-09-30", 490000.0),
        ("2025-10-31", 495000.0),
        ("2025-11-30", 498000.0),
        ("2025-12-31", 500000.0),
    ]
    portfolio = _make_portfolio(points)
    result = metrics.returns(portfolio)

    assert result["return_12m_pct"] is None
    # 3m IS computable with 12 points, but spec says keep existing keys unchanged
    # The key point: when 12m is missing, use oldest-to-newest for return_available_*
    assert result["return_available_pct"] == pytest.approx(11.11, abs=0.01)
    assert result["return_available_days"] is not None
    assert result["return_basis"] is not None
    assert result["return_basis"].startswith("available:")
    assert result["points"] == 12


def test_58_point_series_uses_12m_basis(dataset):
    """58-point series (CASE-007-01) → basis '12m' and return_available_pct == return_12m_pct."""
    from app.domain import ingest

    client = dataset.client("CASE-007")
    portfolio = next(
        p for p in ingest.listof(client, "Portfolios")
        if ingest.text(p, "PortfolioNr") == "CASE-007-01"
    )
    result = metrics.returns(portfolio)

    assert result["return_12m_pct"] is not None
    assert result["return_12m_pct"] == pytest.approx(15.15, abs=0.01)
    assert result["return_available_pct"] == result["return_12m_pct"]
    assert result["return_basis"] == "12m"
    assert result["return_available_days"] is not None


def test_1_point_series_all_none():
    """1-point series → all return fields None, basis None."""
    points = [("2025-12-31", 500000.0)]
    portfolio = _make_portfolio(points)
    result = metrics.returns(portfolio)

    assert result["return_12m_pct"] is None
    assert result["return_3m_pct"] is None
    assert result["return_available_pct"] is None
    assert result["return_available_days"] is None
    assert result["return_basis"] is None
    assert result["points"] == 1


def test_empty_series_no_crash():
    """Empty series → no crash, all return fields None."""
    portfolio = _make_portfolio([])
    result = metrics.returns(portfolio)

    assert result["return_12m_pct"] is None
    assert result["return_3m_pct"] is None
    assert result["return_available_pct"] is None
    assert result["return_available_days"] is None
    assert result["return_basis"] is None
    assert result["points"] == 0
    assert result["as_of"] is None
