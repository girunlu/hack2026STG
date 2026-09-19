"""F5 — derived metrics.

Every number here is recomputed from raw records. Notably ``PerformanceYTD`` is **null on all 57
portfolios** (in fact the key is absent), so returns always come from ``PerformanceHistory``.

Fund look-through uses ``FundUnbundlingMappings`` (join on ``FundSecurityId``), whose ``Weight`` is
**0–100** and may be **negative** (484 rows are). Weights are therefore divided by 100 and never
clamped.

Suitability violations are **display-only** (``PROJECT.md`` §7 rule 5): they are read from the data,
never re-derived from ``RiskProfile.MaxVola`` vs ``Portfolio.Volatility``.
"""

from __future__ import annotations

import math
from typing import Any

from ..fields import label as field_label, unit as field_unit
from ..i18n import DEFAULT_LANG, t
from . import index
from .ingest import day, intnum, listof, num, text

# Which security field and which look-through field carry each analysis dimension.
DIMENSIONS: dict[str, tuple[str, str]] = {
    "asset_class": ("SAA_AssetClassName", "AssetClassName"),
    "currency": ("SAA_CurrencyGroupName", "CurrencyGroupName"),
    "country": ("SAA_CountryGroupName", "CountryGroupName"),
    "industry": ("SAA_IndustryName", "IndustryName"),
}

NOT_CLASSIFIED = "Nicht klassifiziert"
FIVE_YEARS_DAYS = 1826

# Stable maturity-bucket keys (the F4 screen colours by them) with their display labels.
MATURITY_LABEL_KEYS: dict[str, str] = {
    "Unter 1 Jahr": "label.maturity_under_1y",
    "1–5 Jahre": "label.maturity_1_5",
    "5–10 Jahre": "label.maturity_5_10",
    "Über 10 Jahre": "label.maturity_over_10",
    NOT_CLASSIFIED: "label.not_classified",
}


def _points(portfolio: dict) -> list[tuple[str, float]]:
    """Sorted (date, value) performance points."""
    rows = []
    for point in listof(portfolio, "PerformanceHistory"):
        stamp = day(point.get("Date"))
        if stamp:
            rows.append((stamp, num(point, "Value")))
    return sorted(rows, key=lambda row: row[0])


def _days_between(date_a: str, date_b: str) -> int:
    """Days between two ISO date strings (YYYY-MM-DD)."""
    from datetime import date as _date
    ya, ma, da = (int(x) for x in date_a.split("-")[:3])
    yb, mb, db = (int(x) for x in date_b.split("-")[:3])
    return (_date(yb, mb, db) - _date(ya, ma, da)).days

def returns(portfolio: dict) -> dict:
    """Trailing returns in percent, computed from ``PerformanceHistory`` (monthly points).

    ``CASE-007-01`` must yield +15.15% over 12m and +7.67% over 3m.
    """
    points = _points(portfolio)
    result: dict[str, Any] = {
        "as_of": points[-1][0] if points else None,
        "points": len(points),
        "return_3m_pct": None,
        "return_12m_pct": None,
        "return_24m_pct": None,
        "return_ytd_pct": None,
        "return_available_pct": None,
        "return_available_days": None,
        "return_basis": None,
        "source": "PerformanceHistory",
        "note": "PerformanceYTD is not present in the data; computed here.",
    }
    if not points:
        return result
    last_date, last_value = points[-1]

    def trailing(months: int) -> float | None:
        position = len(points) - 1 - months
        if position < 0 or last_value == 0:
            return None
        base = points[position][1]
        if base == 0:
            return None
        return round((last_value / base - 1) * 100, 4)

    for label, months in (("return_3m_pct", 3), ("return_12m_pct", 12), ("return_24m_pct", 24)):
        result[label] = trailing(months)

    previous_year_points = [p for p in points if p[0][:4] < last_date[:4]]
    if previous_year_points and previous_year_points[-1][1]:
        base = previous_year_points[-1][1]
        result["return_ytd_pct"] = round((last_value / base - 1) * 100, 4)
        result["ytd_base"] = previous_year_points[-1][0]

    # Compute return_available_* and return_basis
    if result["return_12m_pct"] is not None:
        # Mirror 12m return
        result["return_available_pct"] = result["return_12m_pct"]
        base_date_str = points[-13][0]
        result["return_available_days"] = _days_between(base_date_str, last_date)
        result["return_basis"] = "12m"
    elif len(points) >= 2:
        # Use oldest to newest
        first_date, first_value = points[0]
        if first_value != 0 and last_value != 0:
            result["return_available_pct"] = round((last_value / first_value - 1) * 100, 4)
            result["return_available_days"] = _days_between(first_date, last_date)
            result["return_basis"] = f"available:{result['return_available_days']}d"

    return result


def portfolio_value(portfolio: dict) -> float:
    """Sum of the portfolio's own position values (securities + cash accounts)."""
    total = sum(num(p, "TotalAmountInPortfolioCurrency") for p in listof(portfolio, "SecurityPositions"))
    total += sum(num(a, "TotalAmountInPortfolioCurrency") for a in listof(portfolio, "AccountPositions"))
    return total


def concentration(portfolio: dict) -> dict:
    """Largest single line and HHI over security positions (weights are already fractions 0–1)."""
    positions = listof(portfolio, "SecurityPositions")
    if not positions:
        return {
            "positions": 0,
            "top_weight": None,
            "top_security": None,
            "top_security_id": None,
            "top_index": None,
            "hhi": None,
            "securities_weight": 0.0,
        }
    top_idx = max(range(len(positions)), key=lambda i: num(positions[i], "PortfolioValuePercentage"))
    top = positions[top_idx]
    return {
        "positions": len(positions),
        "top_weight": round(num(top, "PortfolioValuePercentage"), 6),
        "top_security": text(top, "SecurityName"),
        "top_security_id": intnum(top, "SecurityId", -1),
        "top_index": top_idx,
        "top_isin": text(top, "Isin"),
        "hhi": round(sum(num(p, "PortfolioValuePercentage") ** 2 for p in positions), 6),
        "securities_weight": round(sum(num(p, "PortfolioValuePercentage") for p in positions), 6),
    }


def _cash_buckets(portfolio: dict, dimension: str) -> dict[str, float]:
    """Cash accounts carry no asset class; map them deliberately per dimension."""
    dataset = index.get()
    buckets: dict[str, float] = {}
    for account in listof(portfolio, "AccountPositions"):
        value = num(account, "TotalAmountInPortfolioCurrency")
        if dimension == "asset_class":
            category = "Liquidity"
        elif dimension == "currency":
            category = dataset.currency_group(text(account, "Currency", "?"))
        else:
            category = NOT_CLASSIFIED
        buckets[category] = buckets.get(category, 0.0) + value
    return buckets


def exposure(portfolio: dict, dimension: str, split_funds: bool = False, lang: str = DEFAULT_LANG) -> list[dict]:
    """Weight by dimension over the whole portfolio.

    ``split_funds=True`` allocates a fund across its ``FundUnbundlingMappings`` rows; ``False`` treats
    each fund as a single line classified by its own ``SAA_*`` fields.

    ``category`` stays the stable key (data vocabulary, or the ``NOT_CLASSIFIED`` sentinel) so colour
    maps and comparisons keep working; ``label`` is what a screen shows.
    """
    if dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}")
    dataset = index.get()
    security_field, mapping_field = DIMENSIONS[dimension]
    buckets = _cash_buckets(portfolio, dimension)
    total = sum(buckets.values())

    for position in listof(portfolio, "SecurityPositions"):
        value = num(position, "TotalAmountInPortfolioCurrency")
        total += value
        security_id = intnum(position, "SecurityId", -1)
        mappings = dataset.fund_mappings(security_id) if split_funds else []
        if mappings:
            for row in mappings:
                category = text(row, mapping_field, NOT_CLASSIFIED) or NOT_CLASSIFIED
                buckets[category] = buckets.get(category, 0.0) + value * num(row, "Weight") / 100.0
        else:
            security = dataset.security(security_id)
            category = text(security, security_field, NOT_CLASSIFIED) or NOT_CLASSIFIED
            buckets[category] = buckets.get(category, 0.0) + value

    rows = [
        {
            "category": category,
            "label": t("label.not_classified", lang) if category == NOT_CLASSIFIED else category,
            "value": round(amount, 4),
            "weight": round(amount / total, 6) if total else 0.0,
        }
        for category, amount in buckets.items()
    ]
    rows.sort(key=lambda row: -row["value"])
    return rows


def exposures(portfolio: dict, lang: str = DEFAULT_LANG) -> dict:
    """All four dimensions, with and without fund look-through."""
    return {
        dimension: {
            "splitting_off": exposure(portfolio, dimension, split_funds=False, lang=lang),
            "splitting_on": exposure(portfolio, dimension, split_funds=True, lang=lang),
        }
        for dimension in DIMENSIONS
    }


def lookthrough(security_id: int, dimension: str = "asset_class") -> list[dict]:
    """A single fund's breakdown by dimension, weights as fractions (``Weight`` is 0–100)."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}")
    _, mapping_field = DIMENSIONS[dimension]
    buckets: dict[str, float] = {}
    for row in index.get().fund_mappings(security_id):
        category = text(row, mapping_field, NOT_CLASSIFIED) or NOT_CLASSIFIED
        buckets[category] = buckets.get(category, 0.0) + num(row, "Weight") / 100.0
    return [
        {"category": category, "weight": round(weight, 6)}
        for category, weight in sorted(buckets.items(), key=lambda item: -item[1])
    ]


def fx_exposure(portfolio: dict) -> dict:
    """Weights by position currency (cash and securities), using the position's own currency."""
    dataset = index.get()
    buckets: dict[str, float] = {}
    for position in listof(portfolio, "SecurityPositions"):
        code = text(position, "Currency", "?") or "?"
        buckets[code] = buckets.get(code, 0.0) + num(position, "TotalAmountInPortfolioCurrency")
    for account in listof(portfolio, "AccountPositions"):
        code = text(account, "Currency", "?") or "?"
        buckets[code] = buckets.get(code, 0.0) + num(account, "TotalAmountInPortfolioCurrency")
    total = sum(buckets.values())
    rows = [
        {
            "currency": code,
            "currency_group": dataset.currency_group(code),
            "value": round(amount, 4),
            "weight": round(amount / total, 6) if total else 0.0,
        }
        for code, amount in buckets.items()
    ]
    rows.sort(key=lambda row: -row["value"])
    return {"rows": rows, "total": round(total, 4), "portfolio_currency": text(portfolio, "PortfolioCurrency")}


def saa_targets(saa: dict | None) -> list[dict]:
    """Asset-class target rows of an SAA, in canonical order.

    SAA 96 ("Consolidaton Investmentservice / CHF / no strategy") has ``AssetClass`` rows that carry
    no ``Min``/``Target``/``Max`` — it is the real "no strategy" case, and returns ``[]`` here.
    """
    if not saa:
        return []
    rows = []
    for mapping in listof(saa, "Mappings"):
        if text(mapping, "Dimension") != "AssetClass":
            continue
        if "TargetPercentage" not in mapping:
            continue
        rows.append({
            "category": text(mapping, "Category"),
            "min": num(mapping, "MinPercentage") if "MinPercentage" in mapping else None,
            "target": num(mapping, "TargetPercentage"),
            "max": num(mapping, "MaxPercentage") if "MaxPercentage" in mapping else None,
        })
    order = index.ASSET_CLASS_ORDER
    rows.sort(key=lambda row: order.index(row["category"]) if row["category"] in order else len(order))
    return rows


def saa_deviation(portfolio: dict) -> dict:
    """Actual vs agreed asset-class weights ("splitting off" — the portfolio's own classification)."""
    dataset = index.get()
    saa = dataset.saa(intnum(portfolio, "StrategicAssetAllocationId", -1))
    targets = saa_targets(saa)
    actual = {row["category"]: row["weight"] for row in exposure(portfolio, "asset_class", split_funds=False)}
    result: dict[str, Any] = {
        "available": bool(targets),
        "saa_id": intnum(portfolio, "StrategicAssetAllocationId", -1) or None,
        "saa_name": text(saa, "Name") if saa else None,
        "description": text(saa, "Description") if saa else None,
        "reason": None if targets else "Keine Strategie",
        "rows": [],
    }
    for target in targets:
        weight = actual.get(target["category"], 0.0)
        result["rows"].append({
            **target,
            "actual": round(weight, 6),
            "difference": round(weight - target["target"], 6),
        })
    return result


def prc_profile(portfolio: dict) -> dict:
    """Product-risk (PRC) distribution by value, for the metric rail."""
    dataset = index.get()
    buckets: dict[int, float] = {}
    total = 0.0
    for position in listof(portfolio, "SecurityPositions"):
        security = dataset.security(intnum(position, "SecurityId", -1))
        value = num(position, "TotalAmountInPortfolioCurrency")
        total += value
        prc = intnum(security, "PRC", 0) if security else 0
        buckets[prc] = buckets.get(prc, 0.0) + value
    share_high = sum(v for k, v in buckets.items() if k >= 5)
    return {
        "distribution": {str(k): round(v / total, 6) for k, v in sorted(buckets.items()) if total},
        "share_prc_ge_5": round(share_high / total, 6) if total else None,
        "max_prc": max(buckets) if buckets else None,
    }


def sustainability(portfolio: dict) -> dict:
    """Value-weighted average sustainability score over scored holdings."""
    dataset = index.get()
    weighted = 0.0
    weight = 0.0
    for position in listof(portfolio, "SecurityPositions"):
        security = dataset.security(intnum(position, "SecurityId", -1))
        if not security or "SustainabilityScore" not in security:
            continue
        score = num(security, "SustainabilityScore")
        value = num(position, "TotalAmountInPortfolioCurrency")
        weighted += score * value
        weight += value
    return {
        "score": round(weighted / weight, 2) if weight else None,
        "scored_weight": round(weight, 4),
        "positioned_weight": round(sum(num(p, "TotalAmountInPortfolioCurrency") for p in listof(portfolio, "SecurityPositions")), 4),
    }


def maturity_buckets(portfolio: dict, as_of: str | None = None, lang: str = DEFAULT_LANG) -> dict:
    """Maturity profile of dated holdings. Returns ``classified_weight == 0`` when nothing is dated.

    Bucket keys stay stable (the F4 screen maps colours by them); ``label`` carries the display text.
    """
    dataset = index.get()
    reference = as_of or dataset.data_as_of()
    reference_date = day(reference)
    buckets = {"Unter 1 Jahr": 0.0, "1–5 Jahre": 0.0, "5–10 Jahre": 0.0, "Über 10 Jahre": 0.0, NOT_CLASSIFIED: 0.0}
    classified = 0.0
    total = 0.0
    for position in listof(portfolio, "SecurityPositions"):
        value = num(position, "TotalAmountInPortfolioCurrency")
        total += value
        security = dataset.security(intnum(position, "SecurityId", -1))
        maturity = day(security.get("MaturityDateUtc")) if security else None
        if not maturity or not reference_date:
            buckets[NOT_CLASSIFIED] += value
            continue
        classified += value
        days = (int(maturity[:4]) - int(reference_date[:4])) * 365 + (int(maturity[5:7]) - int(reference_date[5:7])) * 30
        if days < 365:
            buckets["Unter 1 Jahr"] += value
        elif days <= FIVE_YEARS_DAYS:
            buckets["1–5 Jahre"] += value
        elif days <= 2 * FIVE_YEARS_DAYS:
            buckets["5–10 Jahre"] += value
        else:
            buckets["Über 10 Jahre"] += value
    return {
        "as_of": reference,
        "classified_weight": round(classified / total, 6) if total else 0.0,
        "buckets": [
            {
                "category": category,
                "label": t(MATURITY_LABEL_KEYS.get(category, "label.not_classified"), lang),
                "value": round(amount, 4),
                "weight": round(amount / total, 6) if total else 0.0,
            }
            for category, amount in buckets.items()
        ],
    }


def violations(client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """The client's suitability violations, read from the data and explained via ``ViolationPath``.

    The rule text is the violation's **own** ``RuleDescription``. ``SuitabilityRules`` holds 54 rows but
    only 53 distinct ``RuleCode``s — ``Overweight in the equity region "Switzerland"`` exists twice, once
    describing "Schweiz" and once "Grossbritannien" — so looking the text up by code resolves to the last
    duplicate and reports the wrong region (CASE-008, CASE-044). The catalogue is only a fallback for a
    violation that carries no description of its own.

    Every ``ViolationPath`` step is served twice: as an ``explanation`` row (field, label, unit, left,
    right, operator) and as a ``values`` row (the same comparison with its limit), so F3 can print the
    engine's own numbers in the right unit instead of a bare 0.1264 next to prose that says 12.64%.
    """
    dataset = index.get()
    client_ref = text(client, "ClientRef")
    known = dataset.portfolio_ids_of(client_ref)
    rows = []
    for position, violation in enumerate(listof(client, "SuitabilityViolations")):
        portfolio_id = intnum(violation, "PortfolioId", -1)
        portfolio = dataset.portfolio_by_id(portfolio_id)
        rule_code = text(violation, "RuleCode")
        description = text(violation, "RuleDescription") or text(dataset.rule(rule_code) or {}, "Description")
        base_path = f"clients[{client_ref}].SuitabilityViolations[{position}]"

        steps = []
        for offset, step in enumerate(listof(violation, "ViolationPath")):
            field_name = text(step, "FieldName")
            steps.append({
                "field": field_name,
                "label": field_label(field_name, lang),
                "unit": field_unit(field_name),
                "left": num(step, "LeftValue"),
                "right": num(step, "RightValue"),
                "operator": intnum(step, "Operator", -1),
                "path": f"{base_path}.ViolationPath[{offset}]",
            })

        rows.append({
            "id": intnum(violation, "Id", -1) or None,
            "rule_code": rule_code,
            "rule_description": description,
            "severity": text(violation, "Severity"),
            "error_level": intnum(violation, "ErrorLevel", -1),
            "portfolio_id": portfolio_id,
            "portfolio_nr": text(portfolio, "PortfolioNr") if portfolio else None,
            "portfolio_known": portfolio_id in known,
            "explanation": steps,
            "values": [
                {
                    "field": step["field"],
                    "label": step["label"],
                    "value": step["left"],
                    "limit": step["right"],
                    "unit": step["unit"],
                    "source": "clients.json",
                    "path": step["path"],
                }
                for step in steps
            ],
        })
    return rows


# --------------------------------------------------------------------------- risk contributions

# A contribution is a share of the portfolio's own volatility, so no single position can contribute
# more risk than the portfolio carries. The provided data breaks that once: ``CASE-041-01`` holds
# ``XS1412417617`` with ``MarginalContributionToRisk`` 9'223'372.03685 — an int64-overflow sentinel —
# which turns ``ContributionVolatility`` into 574'339.3767 against a portfolio volatility of 0.098.
# Such a row is dropped and declared, never rendered: a wrong number on screen is worse than a gap.
RISK_ROW_TOLERANCE = 1.02


def risk_contributions(portfolio: dict) -> dict:
    """Per-position risk contributions, with impossible source values dropped and declared.

    ``ContributionVolatility`` = ``MarginalContributionToRisk`` × ``PortfolioValuePercentage``, i.e. a
    fraction of ``Portfolio.Volatility``; ``abs(contribution) <= Volatility`` must therefore hold.
    Rows that break it, or that are not finite, are reported under ``dropped`` with their raw values
    and the reason, so callers can show a declared gap instead of the figure.

    ``available`` is ``False`` when no risk series exists for the portfolio (volatility absent, or
    every contribution zero — three portfolios in the case data are like that). Negative
    contributions are legitimate (a hedge) and are kept.
    """
    volatility = num(portfolio, "Volatility") if "Volatility" in portfolio else None
    rows: list[dict] = []
    dropped: list[dict] = []
    for position_index, position in enumerate(listof(portfolio, "SecurityPositions")):
        contribution = num(position, "ContributionVolatility")
        marginal = num(position, "MarginalContributionToRisk")
        row = {
            "index": position_index,
            "security_id": intnum(position, "SecurityId", -1) or None,
            "name": text(position, "SecurityName"),
            "contribution": contribution,
            "marginal": marginal,
        }
        reason = None
        if not (math.isfinite(contribution) and math.isfinite(marginal)):
            reason = "value is not finite"
        elif volatility:
            if abs(contribution) > volatility * RISK_ROW_TOLERANCE + 1e-9:
                reason = f"contribution {contribution!r} exceeds the portfolio's own volatility {volatility!r}"
        elif abs(contribution) > 1.0:
            reason = f"contribution {contribution!r} is not a fraction of volatility"
        if reason:
            dropped.append({**row, "reason": reason})
        else:
            rows.append(row)

    if not volatility:
        available, unavailable_reason = False, "Portfolio.Volatility is not available"
    elif not any(row["contribution"] for row in rows):
        available, unavailable_reason = False, "risk contributions are not populated in the source data"
    else:
        available, unavailable_reason = True, None
    return {
        "available": available,
        "reason": unavailable_reason,
        "volatility": volatility,
        "sum": sum(row["contribution"] for row in rows),
        "rows": rows,
        "dropped": dropped,
    }
