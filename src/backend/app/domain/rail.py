"""Metric-rail descriptors for the portfolio screen (F4).

The screen renders what the data supports and **omits the rest** — a widget whose inputs are missing
is not emitted at all, so no component has to invent an empty gauge. Widgets the data cannot back
(scenarios, issuer risk) are simply absent, and so is any widget whose own value is unavailable
(no ESG profile, no risk figures).

Every title and label is localised through :func:`app.i18n.t`: the rail is API-produced prose, and the
product is bilingual (English default, German on request).
"""

from __future__ import annotations

from ..i18n import DEFAULT_LANG, t
from . import crm, index, metrics
from .ingest import listof, num, text


def _pct(value: float | None) -> float | None:
    return round(value * 100, 4) if value is not None else None


def rail_widgets(client: dict, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Ordered metric-rail widgets, each with the formula that produced its value."""
    dataset = index.get()
    widgets: list[dict] = []
    reference = dataset.data_as_of()

    saa = metrics.saa_deviation(portfolio)
    if saa["available"]:
        outside = [
            row for row in saa["rows"]
            if (row["min"] is not None and row["actual"] < row["min"] - index.EPSILON)
            or (row["max"] is not None and row["actual"] > row["max"] + index.EPSILON)
        ]
        worst = max(
            (row for row in saa["rows"] if row["difference"] is not None),
            key=lambda row: abs(row["difference"]),
            default=None,
        )
        widgets.append({
            "id": "saa",
            "title": t("rail.saa", lang),
            "type": "donut",
            "alert": bool(outside),
            # A supported widget must not read as an empty gauge: the centre carries the largest
            # actual-vs-target deviation, and the sub-line names either the breach count or the
            # category behind that number.
            "value": _pct(worst["difference"]) if worst else None,
            "sub": (
                t("rail.saa_alert_sub", lang, count=len(outside)) if outside
                else (worst["category"] if worst else None)
            ),
            "formula": "centre = largest actual-vs-target deviation; alert when an actual leaves Min/Max",
        })

    portfolios = dataset.portfolios_of(text(client, "ClientRef"))
    errors = [
        v for v in metrics.violations(client, lang)
        if v["severity"] == "Error" and v["portfolio_known"]
    ]
    clean = sum(
        1 for p in portfolios
        if not any(v["portfolio_id"] == int(num(p, "PortfolioId", -1)) and v["severity"] == "Error" for v in errors)
    )
    widgets.append({
        "id": "suitability",
        "title": t("rail.suitability", lang),
        "type": "gauge",
        "value": round(clean / len(portfolios) * 100, 1) if portfolios else None,
        "sub": t("rail.suitability_sub_one" if len(errors) == 1 else "rail.suitability_sub", lang,
                 count=len(errors)),
        "formula": "share of the client's portfolios without an Error-severity violation",
    })

    volatility = num(portfolio, "Volatility") if "Volatility" in portfolio else None
    expected = num(portfolio, "ExpectedReturn") if "ExpectedReturn" in portfolio else None
    if volatility is not None or expected is not None:
        widgets.append({
            "id": "risk_return",
            "title": t("rail.risk_return", lang),
            "type": "scatter",
            "value": _pct(volatility),
            "sub": _pct(expected),
            "value_label": t("rail.risk_label", lang),
            "sub_label": t("rail.return_label", lang),
            "formula": "Portfolio.Volatility / Portfolio.ExpectedReturn, as delivered by the risk engine",
        })

    prc = metrics.prc_profile(portfolio)
    if prc["max_prc"] is not None:
        widgets.append({
            "id": "product_risk",
            "title": t("rail.product_risk", lang),
            "type": "donut",
            "value": _pct(prc["share_prc_ge_5"]),
            "sub": t("rail.product_risk_sub", lang, prc=prc["max_prc"]),
            "formula": "share of value in holdings with PRC >= 5",
        })

    exposures = metrics.exposures(portfolio, lang)
    for widget_id, key, dimension, chart in (
        ("countries", "rail.countries", "country", "map"),
        ("industries", "rail.industries", "industry", "donut"),
        ("currencies", "rail.currencies", "currency", "donut"),
    ):
        rows = [row for row in exposures[dimension]["splitting_on"] if row["weight"] > 0]
        if not rows:
            continue
        # Choose the largest *classified* bucket: 155 of 277 held securities carry no industry
        # classification, and a headline of "not classified" would tell the advisor nothing.
        unclassified = sum(row["weight"] for row in rows if row["category"] == metrics.NOT_CLASSIFIED)
        classified = [row for row in rows if row["category"] != metrics.NOT_CLASSIFIED]
        top = (classified or rows)[0]
        suffix = t("rail.unclassified", lang, pct=round(unclassified * 100)) if unclassified > 0.005 else ""
        widgets.append({
            "id": widget_id,
            "title": t(key, lang),
            "type": chart,
            "value": _pct(top["weight"]),
            "sub": f"{top.get('label') or top['category']}{suffix}",
            "formula": f"value-weighted {dimension} exposure with fund look-through (FundUnbundlingMappings)",
        })

    maturity = metrics.maturity_buckets(portfolio, reference, lang)
    if maturity["classified_weight"] > 0:
        dated = [b for b in maturity["buckets"] if b["category"] != metrics.NOT_CLASSIFIED]
        top = max(dated, key=lambda b: b["value"]) if dated else None
        widgets.append({
            "id": "maturities",
            "title": t("rail.maturities", lang),
            "type": "bar",
            "value": _pct(maturity["classified_weight"]),
            "sub": (top.get("label") or top["category"]) if top else None,
            "formula": "share of value in dated holdings, bucketed by MaturityDateUtc",
        })

    overrides = crm.overrides(client)
    widgets.append({
        "id": "restrictions",
        "title": t("rail.restrictions", lang),
        "type": "rows",
        "value": len(overrides),
        "sub": None,
        "rows": [
            {"label": t("rail.restrictions_overrides", lang), "value": len(overrides)},
            {"label": t("rail.restrictions_rules", lang), "value": len(dataset.suitability_rules)},
            {"label": t("rail.restrictions_violations", lang), "value": len(listof(client, "SuitabilityViolations"))},
        ],
        "formula": "IndividualRuleOverrides / SuitabilityRules / SuitabilityViolations counts",
    })

    trailing = metrics.returns(portfolio)
    if trailing["return_12m_pct"] is not None:
        widgets.append({
            "id": "performance",
            "title": t("rail.performance", lang),
            "type": "line",
            "value": trailing["return_12m_pct"],
            "sub": t("rail.performance_sub", lang),
            "direction": "up" if trailing["return_12m_pct"] >= 0 else "down",
            "formula": "trailing 12m from PerformanceHistory",
        })

    sustain = metrics.sustainability(portfolio)
    esg_profile = text(client, "EsgProfileName") or None
    if esg_profile or sustain["score"] is not None:
        widgets.append({
            "id": "sustainability",
            "title": t("rail.sustainability", lang),
            "type": "donut",
            "value": esg_profile,
            "sub": (
                t("rail.sustainability_sub", lang, score=sustain["score"])
                if sustain["score"] is not None else t("rail.sustainability_sub_none", lang)
            ),
            "formula": "value-weighted SustainabilityScore over scored holdings",
        })

    widgets.append({
        "id": "positions",
        "title": t("rail.positions", lang),
        "type": "grid",
        "value": len(listof(portfolio, "SecurityPositions")),
        "sub": t("rail.positions_sub", lang),
        "formula": "SecurityPositions count",
    })
    return widgets
