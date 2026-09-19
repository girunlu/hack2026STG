"""R3 — Relevance engine.

Deterministic, LLM-free findings over F5 data. Returns a ranked list of finding dicts
in the BriefingFacts shape: {id, type, severity, score, portfolio_id, title, detail, evidence[]}.

Rules:
- concentration: top security weight, HHI
- allocation_drift: SAA deviation >= 5%
- rule_violation: display-only from SuitabilityViolations
- risk_alignment: Portfolio.Volatility vs RiskProfile.MaxVola (context only)
- preference_conflict: note keywords vs holdings (direct or look-through)
- liquidity_event: cash need note + illiquid concentration
- performance_driver: risk contribution from ContributionVolatility
- open_proposal: Entwurf status
- fx_exposure: currency concentration
- stale_data: performance series lag
- missing_data: nulls, absent keys, dangling refs
- material_change: executed trades inside the recent window (Transactions, dated via their proposal —
  the rows themselves carry no date, see PROJECT-NOTES.md §5)
- pending_task: a note that asks the advisor to do something (deduplicated against the note's other use)
- reinvestment: idle liquidity above both its SAA target and the product's own 10% mark
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..fields import unit as field_unit
from ..i18n import DEFAULT_LANG, t
from ..text import compact
from . import crm, index, metrics
from .ingest import as_date, day, intnum, listof, num, text

# ====================================================================================================
# Thresholds — module-level named constants with justification
# ====================================================================================================

# Concentration: high above 50%, medium above 25%. Four clients hold ~95% in one stock.
CONCENTRATION_HIGH = 0.50
CONCENTRATION_MEDIUM = 0.25

# Allocation drift: abs(difference) >= 5% triggers a finding.
DRIFT_THRESHOLD = 0.05

# FX exposure: high above 50%, medium above 30%. CASE-012 has 82.2% USD.
FX_HIGH = 0.50
FX_MEDIUM = 0.30

# Sector concentration: high above 50%, medium above 30%.
# Measured over 58 portfolios with metrics.exposures(p)["industry"]["splitting_on"]:
# Excluding NOT_CLASSIFIED, 15 portfolios / 15 clients fire at these thresholds.
SECTOR_HIGH = 0.50
SECTOR_MEDIUM = 0.30

# Preference conflict: keyword -> industry map (explicit, documented).
PREFERENCE_KEYWORDS = {
    "fossil": ["Energy"],
    "oil": ["Energy"],
    "coal": ["Energy"],
    "energy": ["Energy"],
    "alcohol": ["Consumer Staples"],
    "tobacco": ["Consumer Staples"],
    "weapons": ["Industrials"],
    "gambling": ["Consumer Discretionary"],
}

# Liquidity event: cash need note + largest single line > 20% or equity weight > 50%.
LIQUIDITY_ILLIQUID_SINGLE = 0.20
LIQUIDITY_ILLIQUID_EQUITY = 0.50

# Stale data: performance series ends 2026-07-01, data_as_of is 2026-09-03 (~11 weeks).
STALE_WEEKS_THRESHOLD = 8

# Material change: executed trades inside this window before data_as_of. 183 days ≈ six months.
# A transaction row has no date of its own, so it is dated by its proposal (see _material_change).
MATERIAL_CHANGE_DAYS = 183
# A single trade at or above this share of the portfolio's own value is worth the top severity.
MATERIAL_CHANGE_HIGH_RATIO = 0.10

# Reinvestment: liquidity above its SAA target by this much, and above the product's own 10% mark
# (the dashboard's "01 - Liquidity > 10%" tab uses the same threshold).
REINVEST_EXCESS = 0.05
REINVEST_MIN_SHARE = 0.10

# Pending task: a note that (a) states an explicit request or commitment the advisor owes the client,
# or (b) states an interest tied to a scheduled occasion, and (c) is not a standing restriction, a
# personal characteristic, or a note that another finding already speaks for.
# Strong markers fire alone; weak markers only with an occasion; closed markers always win.
TASK_STRONG_MARKERS = (
    "requested",
    "asked for",
    "asked about",
    "would like",
    "follow-up",
    "more detail",
    "needs approximately",
    "has expressed interest",
    "considering a",
    "details being clarified",
    "to be reviewed",
    "plans to",
    "planning to",
    "expects an",
)
TASK_WEAK_MARKERS = (
    "wants ",
    "wants to",
    "open to",
    "interested in",
    "watching ",
)
# An interest only becomes a task when it names when it should happen.
TASK_OCCASION_MARKERS = (
    "at the next",
    "next ",
    "before ",
    "within ",
    "coming ",
)
# ...unless the note itself closes the loop. These markers win over everything above.
TASK_CLOSED_MARKERS = (
    "already held",
    "meeting held",
    "no change to strategy",
    "explicitly accepts",
    "discussed again",
)

# The Liquidity bucket is cash, not an asset-class position: it is reported by ``reinvestment``
# (as idle money to deploy) instead of by ``allocation_drift`` (as a strategic deviation).
CASH_CATEGORY = "Liquidity"

# ====================================================================================================
# Finding shape
# ====================================================================================================

def _finding(
    type: str,
    severity: str,
    score: float,
    portfolio_id: int | None,
    title: str,
    detail: str,
    evidence: list[dict],
    security_id: int | None = None,
    isin: str | None = None,
) -> dict:
    """Build a finding dict. Evidence must be non-empty (PROJECT.md §8).

    ``security_id``/``isin`` identify the instrument when the finding is *about one* — a concentration,
    a performance driver. They carry no prose: they exist so the briefing can offer that instrument's
    market results beside the sentence, instead of leaving the advisor to retype its name into the
    search. Both are present on every finding so the shape never varies.
    """
    if not evidence:
        raise ValueError(f"finding of type {type} has no evidence")
    return {
        "type": type,
        "severity": severity,
        "score": round(min(max(score, 0.0), 1.0), 4),
        "portfolio_id": portfolio_id,
        "title": title,
        "detail": detail,
        "evidence": evidence,
        "security_id": security_id,
        "isin": isin,
    }


def _evidence(label: str, value: Any, source: str, path: str, unit: str | None = None) -> dict:
    """One evidence entry.

    ``unit="ratio"`` marks a 0–1 value whose prose states a percentage (volatility, a weight) so the
    evidence card can print ``12.73%`` beside the sentence that says 12.73% instead of a bare ``0.13``
    in a different unit. The numeric ``value`` is never rescaled — consumers compute with it.
    """
    return {"label": label, "value": value, "source": source, "path": path, "unit": unit}


# ====================================================================================================
# Extractors
# ====================================================================================================

def _concentration(client_ref: str, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Top security weight and HHI."""
    conc = metrics.concentration(portfolio)
    top_weight = conc["top_weight"]
    if top_weight is None:
        return []
    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    portfolio_nr = text(portfolio, "PortfolioNr")
    top_name = conc["top_security"]
    top_index = conc["top_index"]
    hhi = conc["hhi"]

    if top_weight >= CONCENTRATION_HIGH:
        severity = "high"
        score = 0.7 + 0.3 * (top_weight - CONCENTRATION_HIGH) / (1.0 - CONCENTRATION_HIGH)
    elif top_weight >= CONCENTRATION_MEDIUM:
        severity = "medium"
        score = 0.4 + 0.3 * (top_weight - CONCENTRATION_MEDIUM) / (CONCENTRATION_HIGH - CONCENTRATION_MEDIUM)
    else:
        return []

    pct = round(top_weight * 100, 2)
    title = (t("finding.concentration_title", lang, pct=pct, name=top_name)
             if top_name else t("finding.concentration_title_single", lang, pct=pct))
    detail = (t("finding.concentration_detail", lang, nr=portfolio_nr, pct=pct, name=top_name)
              if top_name else t("finding.concentration_detail_single", lang, nr=portfolio_nr, pct=pct))
    if hhi is not None:
        detail += f" HHI = {round(hhi, 4)}."

    # The concentrated instrument, so the block can offer its market results. ``top_index`` is the
    # index the evidence path already names, and it is the position's, not the master's.
    positions = listof(portfolio, "SecurityPositions")
    top_position = positions[top_index] if isinstance(top_index, int) and 0 <= top_index < len(positions) else None
    top_security_id = intnum(top_position, "SecurityId", 0) if top_position else 0
    top_isin = text(top_position, "Isin") if top_position else ""

    return [_finding(
        type="concentration",
        severity=severity,
        score=score,
        portfolio_id=portfolio_id,
        title=title,
        detail=detail,
        security_id=top_security_id or None,
        isin=top_isin or None,
        evidence=[
            _evidence(
                f"{top_name} weight" if top_name else "Top position weight",
                top_weight,
                "clients.json",
                f"clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[{top_index}].PortfolioValuePercentage",
                unit="ratio",
            ),
            _evidence("HHI", hhi, "computed", f"sum of squared weights from clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[*].PortfolioValuePercentage"),
        ],
    )]



def _sector_concentration(client_ref: str, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Industry concentration using fund look-through.

    Uses SECTOR_HIGH (0.50) and SECTOR_MEDIUM (0.30) thresholds, following the FX exposure
    convention. Excludes NOT_CLASSIFIED from ranking. When unclassified weight exceeds 10%,
    it is disclosed in evidence and detail.
    """
    industry_rows = metrics.exposure(portfolio, "industry", split_funds=True)
    if not industry_rows:
        return []
    
    # Calculate unclassified weight
    unclassified_weight = 0.0
    for row in industry_rows:
        if row["category"] == metrics.NOT_CLASSIFIED:
            unclassified_weight = row["weight"]
            break
    
    # Filter out NOT_CLASSIFIED and find top classified industry
    classified_rows = [row for row in industry_rows if row["category"] != metrics.NOT_CLASSIFIED]
    if not classified_rows:
        # Cash-only portfolio: `_missing_data` declares the absent SecurityPositions,
        # so there is nothing to rank and nothing to add.
        return []
    # First row is the largest by value (metrics.exposure sorts descending)
    top = classified_rows[0]
    top_weight = top["weight"]
    top_industry = top["category"]

    # Apply FX-style thresholds and scoring
    if top_weight >= SECTOR_HIGH:
        severity = "high"
        score = 0.6 + 0.3 * (top_weight - SECTOR_HIGH) / (1.0 - SECTOR_HIGH)
    elif top_weight >= SECTOR_MEDIUM:
        severity = "medium"
        score = 0.4 + 0.2 * (top_weight - SECTOR_MEDIUM) / (SECTOR_HIGH - SECTOR_MEDIUM)
    else:
        return []

    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    portfolio_nr = text(portfolio, "PortfolioNr")
    pct = round(top_weight * 100, 2)
    
    # Build evidence list
    evidence = [
        _evidence(
            f"{top_industry} weight",
            top_weight,
            "computed",
            f"sum of industry weights from clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[*] via FundUnbundlingMappings",
            unit="ratio",
        ),
    ]
    
    # Add unclassified weight to evidence if it exceeds 10%
    if unclassified_weight > 0.10:
        unclassified_pct = round(unclassified_weight * 100, 2)
        evidence.append(
            _evidence(
                "Unclassified weight",
                unclassified_weight,
                "computed",
                f"sum of unclassified weights from clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[*] via FundUnbundlingMappings",
                unit="ratio",
            )
        )
        # Mention unclassified weight in detail
        detail = t("finding.sector_concentration_detail_with_unclassified", lang, 
                   nr=portfolio_nr, pct=pct, industry=top_industry, 
                   unclassified_pct=unclassified_pct)
    else:
        detail = t("finding.sector_concentration_detail", lang, nr=portfolio_nr, pct=pct, industry=top_industry)
    
    title = t("finding.sector_concentration_title", lang, pct=pct, industry=top_industry)

    return [_finding(
        type="sector_concentration",
        severity=severity,
        score=score,
        portfolio_id=portfolio_id,
        title=title,
        detail=detail,
        evidence=evidence,
    )]


def _allocation_drift(client_ref: str, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """SAA deviation >= 5%."""
    dev = metrics.saa_deviation(portfolio)
    if not dev["available"]:
        portfolio_id = intnum(portfolio, "PortfolioId", -1)
        return [_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=portfolio_id,
            title=t("finding.no_strategy", lang),
            detail=t("finding.no_strategy_detail", lang, nr=text(portfolio, "PortfolioNr")),
            evidence=[_evidence(
                "SAA available",
                False,
                "computed",
                f"SAA lookup failed for StrategicAssetAllocationId={portfolio.get('StrategicAssetAllocationId')} at clients[{client_ref}].Portfolios[{text(portfolio, 'PortfolioNr')}]",
            )],
        )]

    findings = []
    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    portfolio_nr = text(portfolio, "PortfolioNr")

    for row in dev["rows"]:
        diff = row["difference"]
        if abs(diff) < DRIFT_THRESHOLD:
            continue
        category = row["category"]
        if category == CASH_CATEGORY:
            continue  # cash is reported by _reinvestment, never as a strategic deviation
        target = row["target"]
        actual = row["actual"]
        diff_pct = round(diff * 100, 2)
        target_pct = round(target * 100, 2)
        actual_pct = round(actual * 100, 2)

        if abs(diff) >= 0.15:
            severity = "high"
            score = 0.6 + 0.3 * (abs(diff) - 0.15) / 0.35
        elif abs(diff) >= 0.10:
            severity = "medium"
            score = 0.4 + 0.2 * (abs(diff) - 0.10) / 0.05
        else:
            severity = "medium"
            score = 0.3 + 0.1 * (abs(diff) - DRIFT_THRESHOLD) / 0.05

        direction = t("finding.allocation_direction_over" if diff > 0
                       else "finding.allocation_direction_under", lang)
        title = t("finding.allocation_title", lang, category=category, actual=actual_pct, target=target_pct)
        detail = t("finding.allocation_detail", lang, category=category, diff=abs(diff_pct),
                   direction=direction, target=target_pct)

        findings.append(_finding(
            type="allocation_drift",
            severity=severity,
            score=score,
            portfolio_id=portfolio_id,
            title=title,
            detail=detail,
            evidence=[
                _evidence(f"{category} target", target, "computed", f"reference.StrategicAssetAllocations[joined via StrategicAssetAllocationId].Mappings[{category}].TargetPercentage", unit="ratio"),
                _evidence(f"{category} actual", actual, "computed", f"aggregated from clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions", unit="ratio"),
            ],
        ))
    return findings


def _rule_violation(client_ref: str, client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Display-only from SuitabilityViolations."""
    dataset = index.get()
    known = dataset.portfolio_ids_of(client_ref)
    findings = []

    for violation_index, violation in enumerate(listof(client, "SuitabilityViolations")):
        portfolio_id = intnum(violation, "PortfolioId", -1)
        rule_code = text(violation, "RuleCode")
        # Evidence paths index the source array, the way every other path in the project does
        # (``SecurityPositions[0]``) — the record's own ``Id`` is not an array index.
        violation_id = violation_index
        severity_raw = text(violation, "Severity")
        severity = "high" if severity_raw == "Error" else "medium" if severity_raw == "Warning" else "low"
        score = 0.8 if severity == "high" else 0.5

        # Dangling reference: portfolio_id exists on no client.
        if portfolio_id not in known:
            findings.append(_finding(
                type="missing_data",
                severity="medium",
                score=0.4,
                portfolio_id=portfolio_id,
                title=t("finding.unknown_portfolio", lang),
                detail=t("finding.unknown_portfolio_detail", lang, code=rule_code, id=portfolio_id),
                evidence=[_evidence(
                    "PortfolioId",
                    portfolio_id,
                    "clients.json",
                    f"clients[{client_ref}].SuitabilityViolations[{violation_id}].PortfolioId",
                )],
            ))
            continue

        portfolio = dataset.portfolio_by_id(portfolio_id)
        portfolio_nr = text(portfolio, "PortfolioNr") if portfolio else None
        # The violation's own description. ``SuitabilityRules`` holds 54 rows but only 53 distinct
        # ``RuleCode``s ("Overweight in the equity region \"Switzerland\"" describes "Schweiz" once and
        # "Grossbritannien" once), so a lookup by code resolves to the last duplicate and puts the wrong
        # region in the briefing. The catalogue is only a fallback for a violation without its own text.
        rule_desc = text(violation, "RuleDescription") or text(dataset.rule(rule_code) or {}, "Description")
        path = listof(violation, "ViolationPath")

        evidence = []
        for idx, step in enumerate(path):
            field = text(step, "FieldName")
            left = num(step, "LeftValue")
            right = num(step, "RightValue")
            evidence.append(_evidence(
                field,
                {"left": left, "right": right},
                "computed",
                f"extracted from clients[{client_ref}].SuitabilityViolations[{violation_id}].ViolationPath[{idx}]",
                unit=field_unit(field),
            ))
        if not evidence:
            evidence.append(_evidence(
                "RuleCode",
                rule_code,
                "clients.json",
                f"clients[{client_ref}].SuitabilityViolations[{violation_id}]",
            ))

        title = t("finding.rule_violation_prefix", lang, desc=rule_desc or rule_code)
        detail = t("finding.rule_violation_detail", lang, nr=portfolio_nr, desc=rule_desc or rule_code)
        if path:
            parts = []
            for step in path:
                field = text(step, "FieldName")
                left = num(step, "LeftValue")
                right = num(step, "RightValue")
                parts.append(f"{field}: {left} vs {right}")
            detail += " " + ", ".join(parts)

        findings.append(_finding(
            type="rule_violation",
            severity=severity,
            score=score,
            portfolio_id=portfolio_id,
            title=title,
            detail=detail,
            evidence=evidence,
        ))
    return findings


def _risk_alignment(client_ref: str, client: dict, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Portfolio.Volatility vs RiskProfile.MaxVola (context only)."""
    dataset = index.get()
    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    portfolio_nr = text(portfolio, "PortfolioNr")
    risk_profile_id = intnum(client, "RiskProfileId", 0)

    if not risk_profile_id:
        return [_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=portfolio_id,
            title=t("finding.no_risk_profile", lang),
            detail=t("finding.no_risk_profile_detail", lang, ref=client_ref),
            evidence=[_evidence(
                "RiskProfileId",
                None,
                "clients.json",
                f"clients[{client_ref}].RiskProfileId",
            )],
        )]

    risk_profile = dataset.risk_profile(risk_profile_id)
    if not risk_profile:
        return [_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=portfolio_id,
            title=t("finding.risk_profile_not_found", lang),
            detail=t("finding.risk_profile_not_found_detail", lang, id=risk_profile_id),
            evidence=[_evidence(
                "RiskProfileId",
                risk_profile_id,
                "clients.json",
                f"clients[{client_ref}].RiskProfileId",
            )],
        )]

    max_vola = num(risk_profile, "MaxVola")
    volatility = num(portfolio, "Volatility") if "Volatility" in portfolio else None
    expected_return = num(portfolio, "ExpectedReturn") if "ExpectedReturn" in portfolio else None
    value_at_risk = num(portfolio, "ValueAtRisk") if "ValueAtRisk" in portfolio else None

    findings = []

    # Missing risk metrics.
    if volatility is None:
        findings.append(_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=portfolio_id,
            title=t("finding.volatility_unavailable", lang),
            detail=t("finding.volatility_unavailable_detail", lang, nr=portfolio_nr),
            evidence=[_evidence(
                "Volatility",
                None,
                "computed",
                f"field absent at clients[{client_ref}].Portfolios[{portfolio_nr}].Volatility",
            )],
        ))
    if expected_return is None:
        findings.append(_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=portfolio_id,
            title=t("finding.expected_return_unavailable", lang),
            detail=t("finding.expected_return_unavailable_detail", lang, nr=portfolio_nr),
            evidence=[_evidence(
                "ExpectedReturn",
                None,
                "computed",
                f"field absent at clients[{client_ref}].Portfolios[{portfolio_nr}].ExpectedReturn",
            )],
        ))
    if value_at_risk is None:
        findings.append(_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=portfolio_id,
            title=t("finding.var_unavailable", lang),
            detail=t("finding.var_unavailable_detail", lang, nr=portfolio_nr),
            evidence=[_evidence(
                "ValueAtRisk",
                None,
                "computed",
                f"field absent at clients[{client_ref}].Portfolios[{portfolio_nr}].ValueAtRisk",
            )],
        ))

    # Risk alignment observation (context only, never recompute).
    if volatility is not None:
        title = t("finding.risk_alignment_title", lang, vola=round(volatility * 100, 2),
                  max=round(max_vola * 100, 2))
        detail = t("finding.risk_alignment_detail", lang, nr=portfolio_nr,
                   vola=round(volatility * 100, 2), max=round(max_vola * 100, 2))
        findings.append(_finding(
            type="risk_alignment",
            severity="low",
            score=0.2,
            portfolio_id=portfolio_id,
            title=title,
            detail=detail,
            evidence=[
                _evidence("Portfolio.Volatility", volatility, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].Volatility", unit="ratio"),
                _evidence("RiskProfile.MaxVola", max_vola, "reference.json", f"reference.RiskProfiles[{risk_profile_id}].MaxVola", unit="ratio"),
            ],
        ))

    return findings

def _esg_alignment(client_ref: str, client: dict, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Portfolio sustainability score vs. ESG profile floor (observation only).

    The engine reports zero violations of the rule code ``Sustainable investments only``, so this
    extractor is an observation of the supplied values, not a recomputation of the bank rule — the
    same discipline ``_risk_alignment`` applies to volatility. A portfolio with no score coverage
    emits no finding here; the absence is declared by ``_missing_data`` instead of being doubled.
    """
    dataset = index.get()
    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    portfolio_nr = text(portfolio, "PortfolioNr")
    esg_profile_id = intnum(client, "EsgProfileId", 0)

    if not esg_profile_id:
        return []

    profile = next((p for p in dataset.esg_profiles if intnum(p, "Id", -1) == esg_profile_id), None)
    if not profile:
        return []
    floor = num(profile, "MinimumLevel")
    # Profile "No" carries MinimumLevel 0.001, which rounds to a displayed floor of 0.0 and says
    # nothing: a client who elected no ESG preference gets no ESG line. Only a real floor is a signal.
    if floor < 0.01:
        return []

    sust = metrics.sustainability(portfolio)
    score = sust["score"]
    if score is None:
        # No coverage: the absence is declared elsewhere (meta.unavailable / data_gaps), so we emit
        # nothing here rather than double-declaring.
        return []

    scored_weight = sust["scored_weight"]
    positioned_weight = sust["positioned_weight"]

    # Count positions >=2% below the profile's MinimumPositionLevel — a count, never a verdict.
    min_pos = num(profile, "MinimumPositionLevel")
    below_min_count = 0
    if min_pos > 0:
        for position in listof(portfolio, "SecurityPositions"):
            security = dataset.security(intnum(position, "SecurityId", -1))
            if not security or "SustainabilityScore" not in security:
                continue
            weight = num(position, "PortfolioValuePercentage")
            if weight >= 0.02 and num(security, "SustainabilityScore") < min_pos:
                below_min_count += 1

    if score < floor:
        # ``high`` is deliberate and consistent with ``preference_conflict``: the client elected this
        # ESG profile, the floor is the bank's own ``MinimumLevel``, and no engine rule reports it
        # (0 violations of "Sustainable investments only" in the case data). Exactly one portfolio in
        # the dataset breaches it (CASE-016-01, 3.10 vs 5.714), and at ``medium``/0.35 the block was
        # trimmed away on that client — the finding existed and the advisor never saw it. The wording
        # stays an observation; only the rank changes.
        severity = "high"
        score_value = 0.6
    else:
        severity = "low"
        score_value = 0.15

    title = t("finding.esg_alignment_title", lang, score=round(score, 2), floor=round(floor, 2))
    detail = t("finding.esg_alignment_detail", lang, nr=portfolio_nr, score=round(score, 2),
               floor=round(floor, 2))
    if below_min_count > 0:
        detail += t("finding.esg_alignment_positions_suffix", lang, count=below_min_count)

    evidence = [
        _evidence("Portfolio sustainability score", score, "computed",
                  f"aggregated from clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions"),
        _evidence("ESG profile floor", floor, "computed",
                  f"reference.EsgProfiles[joined via EsgProfileId].MinimumLevel"),
        _evidence("Scored weight", scored_weight, "computed",
                  f"sum of TotalAmountInPortfolioCurrency for scored positions in clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions"),
    ]
    if below_min_count > 0:
        evidence.append(_evidence("Positions below minimum position level", below_min_count, "computed",
                                  f"count of positions >=2% with SustainabilityScore < {min_pos} in clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions"))

    return [_finding(
        type="esg_alignment",
        severity=severity,
        score=score_value,
        portfolio_id=portfolio_id,
        title=title,
        detail=detail,
        evidence=evidence,
    )]


def _preference_conflict(client_ref: str, client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Note keywords vs holdings (direct or look-through).

    One finding per (note, position) combination: if multiple keywords match the same position,
    they are combined into a single finding with all matching keywords listed.
    """
    notes_list = crm.distinct_notes(client)
    if not notes_list:
        return []

    dataset = index.get()
    findings = []

    for note in notes_list:
        note_text = note["text"].lower()
        # Track which positions we've already processed for this note
        # Key: (portfolio_id, position_idx) -> list of matching keywords
        processed_positions: dict[tuple[int, int], list[str]] = {}

        for keyword, industries in PREFERENCE_KEYWORDS.items():
            if keyword not in note_text:
                continue
            # Scan holdings for conflict.
            for portfolio in listof(client, "Portfolios"):
                portfolio_id = intnum(portfolio, "PortfolioId", -1)
                portfolio_nr = text(portfolio, "PortfolioNr")
                for position_idx, position in enumerate(listof(portfolio, "SecurityPositions")):
                    security_id = intnum(position, "SecurityId", -1)
                    security = dataset.security(security_id)
                    if not security:
                        continue
                    weight = num(position, "PortfolioValuePercentage")
                    security_name = text(position, "SecurityName")

                    pos_key = (portfolio_id, position_idx)

                    # Direct holding: check SAA_IndustryName.
                    industry = text(security, "SAA_IndustryName")
                    if industry in industries:
                        if pos_key not in processed_positions:
                            processed_positions[pos_key] = []
                        if keyword not in processed_positions[pos_key]:
                            processed_positions[pos_key].append(keyword)
                        continue

                    # Fund look-through.
                    mappings = dataset.fund_mappings(security_id)
                    if not mappings:
                        continue
                    for mapping in mappings:
                        mapping_industry = text(mapping, "IndustryName")
                        if mapping_industry not in industries:
                            continue
                        mapping_weight_raw = num(mapping, "Weight")
                        if mapping_weight_raw <= 0:
                            continue
                        mapping_weight = mapping_weight_raw / 100.0
                        effective_weight = weight * mapping_weight
                        if effective_weight < 0.001:
                            continue
                        if pos_key not in processed_positions:
                            processed_positions[pos_key] = []
                        if keyword not in processed_positions[pos_key]:
                            processed_positions[pos_key].append(keyword)

        # Now emit one finding per position, combining all matching keywords
        for portfolio in listof(client, "Portfolios"):
            portfolio_id = intnum(portfolio, "PortfolioId", -1)
            portfolio_nr = text(portfolio, "PortfolioNr")
            for position_idx, position in enumerate(listof(portfolio, "SecurityPositions")):
                pos_key = (portfolio_id, position_idx)
                if pos_key not in processed_positions:
                    continue

                matching_keywords = processed_positions[pos_key]
                security_id = intnum(position, "SecurityId", -1)
                security = dataset.security(security_id)
                if not security:
                    continue
                weight = num(position, "PortfolioValuePercentage")
                security_name = text(position, "SecurityName")

                # Determine if this is a direct holding or look-through
                industry = text(security, "SAA_IndustryName")
                is_direct = any(
                    industry in PREFERENCE_KEYWORDS.get(kw, set())
                    for kw in matching_keywords
                )

                if is_direct:
                    pct = round(weight * 100, 2)
                    # Use first keyword for title, list all in detail
                    primary_keyword = matching_keywords[0]
                    keywords_str = ", ".join(matching_keywords)
                    findings.append(_finding(
                        type="preference_conflict",
                        severity="high",
                        score=0.7,
                        portfolio_id=portfolio_id,
                        title=t("finding.preference_conflict_direct", lang,
                                keyword=primary_keyword, name=security_name),
                        detail=t("finding.preference_conflict_direct_detail", lang,
                                 keyword=keywords_str, nr=portfolio_nr, pct=pct,
                                 name=security_name, industry=industry),
                        evidence=[
                            _evidence("Note", note["text"], "clients.json", note["path"]),
                            _evidence("Security", security_name, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[{position_idx}].SecurityName"),
                            _evidence("Industry", industry, "computed", f"reference.Securities[Id={security_id}].SAA_IndustryName"),
                            _evidence("Weight", weight, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[{position_idx}].PortfolioValuePercentage", unit="ratio"),
                        ],
                    ))
                else:
                    # Look-through case
                    mappings = dataset.fund_mappings(security_id)
                    if not mappings:
                        continue
                    for mapping in mappings:
                        mapping_industry = text(mapping, "IndustryName")
                        if not any(mapping_industry in PREFERENCE_KEYWORDS.get(kw, set()) for kw in matching_keywords):
                            continue
                        mapping_weight_raw = num(mapping, "Weight")
                        if mapping_weight_raw <= 0:
                            continue
                        mapping_weight = mapping_weight_raw / 100.0
                        effective_weight = weight * mapping_weight
                        if effective_weight < 0.001:
                            continue
                        pct = round(effective_weight * 100, 2)
                        primary_keyword = matching_keywords[0]
                        keywords_str = ", ".join(matching_keywords)
                        findings.append(_finding(
                            type="preference_conflict",
                            severity="medium",
                            score=0.5,
                            portfolio_id=portfolio_id,
                            title=t("finding.preference_conflict_lookup", lang,
                                    keyword=primary_keyword, name=security_name),
                            detail=t("finding.preference_conflict_lookup_detail", lang,
                                     keyword=keywords_str, nr=portfolio_nr, pct=pct,
                                     name=security_name, industry=mapping_industry),
                            evidence=[
                                _evidence("Note", note["text"], "clients.json", note["path"]),
                                _evidence("Fund", security_name, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[{position_idx}].SecurityName"),
                                _evidence("Industry (look-through)", mapping_industry, "computed", f"reference.FundUnbundlingMappings[FundSecurityId={security_id}].IndustryName"),
                                _evidence("Effective weight", effective_weight, "computed", f"clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[{position_idx}].PortfolioValuePercentage * reference.FundUnbundlingMappings[FundSecurityId={security_id}].Weight", unit="ratio"),
                            ],
                        ))
                        break  # Only one look-through finding per position
    return findings


def _liquidity_event(client_ref: str, client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Cash need note + illiquid concentration."""
    notes_list = crm.distinct_notes(client)
    if not notes_list:
        return []

    liquidity_keywords = ["liquidity", "liquidität", "property", "immobilie", "cash need", "mittelbedarf"]
    cash_need_notes = [n for n in notes_list if any(kw in n["text"].lower() for kw in liquidity_keywords)]
    if not cash_need_notes:
        return []

    dataset = index.get()
    findings = []

    for portfolio in listof(client, "Portfolios"):
        portfolio_id = intnum(portfolio, "PortfolioId", -1)
        portfolio_nr = text(portfolio, "PortfolioNr")
        conc = metrics.concentration(portfolio)
        top_weight = conc["top_weight"]
        top_index = conc["top_index"]
        if top_weight is None:
            continue

        # Check equity weight.
        exposure = metrics.exposure(portfolio, "asset_class", split_funds=False)
        equity_weight = next((row["weight"] for row in exposure if row["category"] == "Shares"), 0.0)

        if top_weight >= LIQUIDITY_ILLIQUID_SINGLE or equity_weight >= LIQUIDITY_ILLIQUID_EQUITY:
            note = cash_need_notes[0]
            title = t("finding.liquidity_need", lang)
            detail = t("finding.liquidity_need_detail", lang, note=compact(note["text"], 50),
                       nr=portfolio_nr, top=round(top_weight * 100, 1),
                       equity=round(equity_weight * 100, 1))
            findings.append(_finding(
                type="liquidity_event",
                severity="high",
                score=0.8,
                portfolio_id=portfolio_id,
                title=title,
                detail=detail,
                evidence=[
                    _evidence("Note", note["text"], "clients.json", note["path"]),
                    _evidence("Top position weight", top_weight, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[{top_index}].PortfolioValuePercentage", unit="ratio"),
                    _evidence("Equity weight", equity_weight, "computed", f"aggregated from clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions", unit="ratio"),
                ],
            ))
    return findings


def _performance_driver(client_ref: str, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Risk contribution from ContributionVolatility — the cleaned series, never the raw field.

    ``metrics.risk_contributions`` drops figures that cannot be true (one position in the case data
    carries an int64-overflow sentinel) for the same reason the UI does: a wrong number inside a
    briefing is worse than a declared gap. A portfolio with no usable series produces no finding
    here — ``_missing_data`` declares that gap instead of inventing a share.
    """
    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    portfolio_nr = text(portfolio, "PortfolioNr")

    risk = metrics.risk_contributions(portfolio)
    if not risk["available"] or not risk["rows"]:
        return []

    # Highest risk contribution first.
    top = max(risk["rows"], key=lambda row: row["contribution"])
    top_contrib = top["contribution"]
    top_name = top["name"]
    portfolio_vol = risk["volatility"] or 0.0

    if top_contrib <= 0 or portfolio_vol <= 0:
        return []

    share = top_contrib / portfolio_vol
    pct = round(share * 100, 1)

    title = t("finding.performance_driver", lang, name=top_name, pct=pct)
    detail = t("finding.performance_driver_detail", lang, nr=portfolio_nr, name=top_name,
               contrib=round(top_contrib * 100, 2), vola=round(portfolio_vol * 100, 2))

    # The instrument behind the risk figure, so the block can offer its market results. ``top['index']``
    # is the position index the evidence path already names.
    positions = listof(portfolio, "SecurityPositions")
    top_index = top.get("index")
    top_position = positions[top_index] if isinstance(top_index, int) and 0 <= top_index < len(positions) else None
    top_security_id = intnum(top_position, "SecurityId", 0) if top_position else 0
    top_isin = text(top_position, "Isin") if top_position else ""

    return [_finding(
        type="performance_driver",
        severity="medium",
        score=0.3 + 0.2 * share,
        portfolio_id=portfolio_id,
        title=title,
        detail=detail,
        security_id=top_security_id or None,
        isin=top_isin or None,
        evidence=[
            _evidence("ContributionVolatility", top_contrib, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions[{top['index']}].ContributionVolatility", unit="ratio"),
            _evidence("Portfolio.Volatility", portfolio_vol, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].Volatility", unit="ratio"),
        ],
    )]


def _open_proposal(client_ref: str, client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Entwurf proposals are open; Final and Abgelehnt are NOT.

    Field names come from the delivered data: proposals carry ``ProposalStatusName``,
    ``ProposalId``, ``AdvisoryTypeName``, ``Reason`` and ``ProposedDateUTC``. The earlier
    ``Status``/``Id``/``Title``/``CreatedByDateUTC`` read nothing, so this extractor silently
    produced zero findings.
    """
    findings = []
    for proposal in listof(client, "Proposals"):
        status = text(proposal, "ProposalStatusName")
        if status != "Entwurf":
            continue
        portfolio_id = intnum(proposal, "PortfolioId", -1)
        proposal_id = intnum(proposal, "ProposalId", -1)
        advisory = text(proposal, "AdvisoryTypeName") or t("finding.proposal_generic", lang)
        reason = text(proposal, "Reason")
        proposed = text(proposal, "ProposedDateUTC")
        positions = len(listof(proposal, "SecurityPositions"))

        # Keys `finding.open_proposal` / `_detail` come from the shared catalogue; the two suffixes are
        # this extractor's own, so they can never collide with another writer's placeholders.
        detail = t("finding.open_proposal_detail", lang,
                   date=proposed or t("finding.date_unknown", lang))
        if reason:
            detail += t("finding.open_proposal_reason_suffix", lang, reason=reason)
        detail += t("finding.open_proposal_positions_suffix", lang, count=positions)

        findings.append(_finding(
            type="open_proposal",
            severity="medium",
            score=0.55,
            portfolio_id=portfolio_id,
            title=t("finding.open_proposal", lang, title=advisory),
            detail=detail,
            evidence=[
                _evidence("ProposalStatusName", status, "clients.json", f"clients[{client_ref}].Proposals[{proposal_id}].ProposalStatusName"),
                _evidence("ProposedDateUTC", proposed, "computed",
                          f"clients[{client_ref}].Proposals[{proposal_id}].ProposedDateUTC (may be absent)"),
                _evidence(f"Count of {positions} positions", positions, "computed", f"len of clients[{client_ref}].Proposals[{proposal_id}].SecurityPositions"),
            ],
        ))
    return findings


def _material_change(client_ref: str, client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Executed trades inside the recent window — "what changed since we last spoke".

    A ``Transactions`` row carries no date and no type; it carries a ``ProposalId``. Every row in the
    provided data resolves to a proposal on the same client, so the trade is dated by that proposal's
    ``FinalizedDateUTC`` (execution) or ``ProposedDateUTC``. Only ``Final`` proposals count: a rejected
    or draft proposal is not an executed change. The dating basis is declared in the evidence rather
    than assumed silently, and no FX conversion is invented — an amount is only compared to AUM when
    it is already in the client's reporting currency.
    """
    dataset = index.get()
    as_of = as_date(dataset.data_as_of())
    if as_of is None:
        return []
    cutoff = as_of - timedelta(days=MATERIAL_CHANGE_DAYS)

    proposals = {intnum(p, "ProposalId", -1): p for p in listof(client, "Proposals")}
    rows: list[tuple[int, dict, dict, str]] = []
    for position, transaction in enumerate(listof(client, "Transactions")):
        proposal = proposals.get(intnum(transaction, "ProposalId", -1))
        if not proposal or text(proposal, "ProposalStatusName") != "Final":
            continue
        stamp = day(proposal.get("FinalizedDateUTC")) or day(proposal.get("ProposedDateUTC"))
        traded = as_date(stamp)
        if stamp and traded and traded >= cutoff:
            rows.append((position, transaction, proposal, stamp))

    if not rows:
        return []
    buys = [row for row in rows if num(row[1], "QuantityForTransaction") > 0]
    sells = [row for row in rows if num(row[1], "QuantityForTransaction") < 0]
    position, transaction, proposal, stamp = max(
        rows, key=lambda row: abs(num(row[1], "TotalAmount"))
    )
    amount = abs(num(transaction, "TotalAmount"))
    currency = text(transaction, "Currency")
    reporting = text(client, "ReportingCurrency")
    aum = num(client, "AssetsUnderManagementInDefaultCurrency")
    ratio = amount / aum if aum > 0 and currency and currency == reporting else None

    if ratio is not None and ratio >= MATERIAL_CHANGE_HIGH_RATIO:
        severity, score = "high", 0.55 + min(0.25, ratio)
    elif len(rows) >= 2:
        severity, score = "medium", 0.35
    else:
        severity, score = "low", 0.2

    name = text(transaction, "SecurityName")

    return [_finding(
        type="material_change",
        severity=severity,
        score=score,
        portfolio_id=intnum(proposal, "PortfolioId", -1),
        title=t("finding.material_change_title", lang,
                count=len(rows), cutoff=cutoff.isoformat(),
                buys=len(buys), sells=len(sells)),
        detail=t("finding.material_change_detail", lang,
                 name=name, amount=amount, currency=currency or reporting or "",
                 date=stamp),
        evidence=[
            _evidence(t("evidence.tx_window", lang), len(rows), "computed",
                      f"count of executed transactions within {MATERIAL_CHANGE_DAYS} days"),
            _evidence(t("evidence.tx_largest", lang), amount, "computed",
                      f"abs of clients[{client_ref}].Transactions[{position}].TotalAmount"),
            _evidence(t("evidence.tx_largest_name", lang), name, "computed",
                      f"clients[{client_ref}].Transactions[{position}].SecurityName (may be absent)"),
            _evidence(t("evidence.tx_date", lang), stamp, "computed",
                      f"from clients[{client_ref}].Proposals[{intnum(proposal, 'ProposalId', -1)}].FinalizedDateUTC or ProposedDateUTC"),
        ],
    )]


def _pending_task(
    client_ref: str,
    client: dict,
    used_note_paths: set[str],
    lang: str = DEFAULT_LANG,
) -> list[dict]:
    """Notes that ask for something the advisor still owes the client.

    The data has no task field (``PROJECT-NOTES.md`` §2), so a task is derived from the note that
    states it — lexicon-based and deterministic. A note that already produced another finding
    (a preference conflict, a liquidity need) is never recycled into a task: one note, one statement.
    Repeated notes are one task, and the evidence carries the note's own path.
    """
    findings = []
    for note in crm.notes(client):
        if note["duplicate_of"] is not None:
            continue  # the same sentence recorded several times is one task
        if note["path"] in used_note_paths:
            continue
        body = note["text"]
        lowered = body.lower()
        if any(marker in lowered for marker in TASK_CLOSED_MARKERS):
            continue
        strong = any(marker in lowered for marker in TASK_STRONG_MARKERS)
        weak = any(marker in lowered for marker in TASK_WEAK_MARKERS)
        if not strong and not (weak and any(m in lowered for m in TASK_OCCASION_MARKERS)):
            continue

        dated = any(marker in lowered for marker in TASK_OCCASION_MARKERS)
        findings.append(_finding(
            type="pending_task",
            severity="medium" if dated else "low",
            score=0.35 if dated else 0.25,
            portfolio_id=None,
            title=t("finding.pending_task_title", lang, text=compact(body, 90)),
            detail=t("finding.pending_task_detail", lang, date=note.get("date") or "—"),
            evidence=[_evidence(t("evidence.note", lang), body, "clients.json", note["path"])],
        ))
    return findings


def _reinvestment(client_ref: str, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Idle liquidity: above its SAA target by ``REINVEST_EXCESS`` and above ``REINVEST_MIN_SHARE``.

    Cash is deliberately not an ``allocation_drift``: a deviation says "you are off your strategy",
    this says "this money is not working". The 10% mark is the product's own convention (the
    dashboard's "01 - Liquidity > 10%" tab).
    """
    dev = metrics.saa_deviation(portfolio)
    if not dev["available"]:
        return []
    row = next((r for r in dev["rows"] if r["category"] == CASH_CATEGORY), None)
    if not row or row["actual"] is None or row["target"] is None:
        return []
    actual, target = float(row["actual"]), float(row["target"])
    if actual < REINVEST_MIN_SHARE or (actual - target) < REINVEST_EXCESS:
        return []

    portfolio_nr = text(portfolio, "PortfolioNr")
    currency = text(portfolio, "PortfolioCurrency") or text(portfolio, "Currency")
    value = metrics.portfolio_value(portfolio)
    excess = actual - target
    severity = "high" if excess >= 0.25 else "medium"

    return [_finding(
        type="reinvestment",
        severity=severity,
        score=0.45 if severity == "medium" else 0.6,
        portfolio_id=intnum(portfolio, "PortfolioId", -1),
        title=t("finding.reinvestment_title", lang,
                actual=round(actual * 100, 2), target=round(target * 100, 2)),
        detail=t("finding.reinvestment_detail", lang,
                 amount=round(value * actual, 2), currency=currency or "",
                 nr=portfolio_nr),
        evidence=[
            _evidence(t("evidence.cash_target", lang), target, "computed",
                      f"from StrategicAssetAllocation (joined via StrategicAssetAllocationId).Mappings[{CASH_CATEGORY}].TargetPercentage", unit="ratio"),
            _evidence(t("evidence.cash_actual", lang), actual, "computed",
                      f"computed from clients[{client_ref}].Portfolios[{portfolio_nr}].AccountPositions (cash share of portfolio value)", unit="ratio"),
            _evidence(t("evidence.portfolio_value", lang), round(value, 2), "computed",
                      f"sum of clients[{client_ref}].Portfolios[{portfolio_nr}].AccountPositions and SecurityPositions"),
        ],
    )]


def _used_note_paths(findings: list[dict]) -> set[str]:
    """Note paths already cited by a finding, so a task never repeats another finding's evidence."""
    return {
        str(evidence.get("path"))
        for finding in findings
        for evidence in (finding.get("evidence") or [])
        if "ClientNotes[" in str(evidence.get("path"))
    }


def _fx_exposure(client_ref: str, portfolio: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Currency concentration."""
    fx = metrics.fx_exposure(portfolio)
    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    portfolio_nr = text(portfolio, "PortfolioNr")
    portfolio_currency = fx["portfolio_currency"]

    findings = []
    for row in fx["rows"]:
        currency = row["currency"]
        weight = row["weight"]
        if currency == portfolio_currency:
            continue
        if weight >= FX_HIGH:
            severity = "high"
            score = 0.6 + 0.3 * (weight - FX_HIGH) / (1.0 - FX_HIGH)
        elif weight >= FX_MEDIUM:
            severity = "medium"
            score = 0.4 + 0.2 * (weight - FX_MEDIUM) / (FX_HIGH - FX_MEDIUM)
        else:
            continue

        pct = round(weight * 100, 2)
        title = f"{pct}% in {currency}"
        detail = t("finding.fx_detail", lang, nr=portfolio_nr, pct=pct,
                   currency=currency, base=portfolio_currency)

        findings.append(_finding(
            type="fx_exposure",
            severity=severity,
            score=score,
            portfolio_id=portfolio_id,
            title=title,
            detail=detail,
            evidence=[
                _evidence(f"{currency} weight", weight, "computed", f"aggregated from clients[{client_ref}].Portfolios[{portfolio_nr}].SecurityPositions", unit="ratio"),
                _evidence("Portfolio currency", portfolio_currency, "clients.json", f"clients[{client_ref}].Portfolios[{portfolio_nr}].PortfolioCurrency"),
            ],
        ))
    return findings


def _stale_data(client_ref: str, client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Performance series lag."""
    dataset = index.get()
    data_as_of = dataset.data_as_of()
    if not data_as_of:
        return []

    # Find newest performance point across all portfolios, tracking which portfolio and index.
    newest_perf = None
    newest_portfolio_nr = None
    newest_index = None
    for portfolio in listof(client, "Portfolios"):
        portfolio_nr = text(portfolio, "PortfolioNr")
        for idx, point in enumerate(listof(portfolio, "PerformanceHistory")):
            stamp = point.get("Date") if isinstance(point, dict) else None
            if stamp and (newest_perf is None or stamp > newest_perf):
                newest_perf = stamp
                newest_portfolio_nr = portfolio_nr
                newest_index = idx

    if not newest_perf or newest_portfolio_nr is None or newest_index is None:
        return []

    # Compute weeks gap.
    from datetime import datetime
    try:
        d1 = datetime.strptime(newest_perf[:10], "%Y-%m-%d")
        d2 = datetime.strptime(data_as_of[:10], "%Y-%m-%d")
        weeks = (d2 - d1).days / 7
    except Exception:
        return []

    if weeks < STALE_WEEKS_THRESHOLD:
        return []

    return [_finding(
        type="stale_data",
        severity="low",
        score=0.1,
        portfolio_id=None,
        title=t("finding.stale_data_title", lang, weeks=round(weeks)),
        detail=t("finding.stale_data_detail", lang, last=newest_perf[:10], as_of=data_as_of[:10]),
        evidence=[
            _evidence("Last performance date", newest_perf, "clients.json",
                      f"clients[{client_ref}].Portfolios[{newest_portfolio_nr}].PerformanceHistory[{newest_index}].Date"),
            _evidence("data_as_of", data_as_of, "computed",
                      f"from reference data (data_as_of field)"),
        ],
    )]


def _missing_data(client_ref: str, client: dict, lang: str = DEFAULT_LANG) -> list[dict]:
    """Nulls, absent keys, dangling refs."""
    findings = []
    dataset = index.get()

    # No notes.
    if not listof(client, "ClientNotes"):
        findings.append(_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=None,
            title=t("finding.no_notes", lang),
            detail=t("finding.no_notes_detail", lang, ref=client_ref),
            evidence=[_evidence("ClientNotes", [], "clients.json", f"clients[{client_ref}].ClientNotes")],
        ))

    # No proposals.
    if not listof(client, "Proposals"):
        findings.append(_finding(
            type="missing_data",
            severity="low",
            score=0.1,
            portfolio_id=None,
            title=t("finding.no_proposals", lang),
            detail=t("finding.no_proposals_detail", lang, ref=client_ref),
            evidence=[_evidence("Proposals", [], "clients.json", f"clients[{client_ref}].Proposals")],
        ))

    # Portfolios without SecurityPositions key.
    for portfolio in listof(client, "Portfolios"):
        if not isinstance(portfolio.get("SecurityPositions"), list):
            portfolio_id = intnum(portfolio, "PortfolioId", -1)
            findings.append(_finding(
                type="missing_data",
                severity="medium",
                score=0.3,
                portfolio_id=portfolio_id,
                title=t("finding.no_security_positions", lang),
                detail=t("finding.no_security_positions_detail", lang, nr=text(portfolio, "PortfolioNr")),
                evidence=[_evidence(
                    "SecurityPositions",
                    None,
                    "computed",
                    f"key absent at clients[{client_ref}].Portfolios[{text(portfolio, 'PortfolioNr')}].SecurityPositions",
                )],
            ))

    return findings


# ====================================================================================================
# Main entry point
# ====================================================================================================

def findings(client_ref: str, portfolio_nr: str | None = None, lang: str = DEFAULT_LANG) -> list[dict]:
    """Return ranked findings for a client (and optionally a specific portfolio).

    Deterministic: no dict-iteration or set-ordering leakage — sort explicitly.
    """
    dataset = index.get()
    client = dataset.client(client_ref)
    if not client:
        return []

    portfolios = listof(client, "Portfolios")
    scope_ids: set[int] = set()
    if portfolio_nr:
        portfolios = [p for p in portfolios if text(p, "PortfolioNr") == portfolio_nr]
        scope_ids = {intnum(p, "PortfolioId", -1) for p in portfolios}

    raw: list[dict] = []

    # Client-level findings.
    raw.extend(_rule_violation(client_ref, client, lang))
    raw.extend(_preference_conflict(client_ref, client, lang))
    raw.extend(_liquidity_event(client_ref, client, lang))
    raw.extend(_stale_data(client_ref, client, lang))
    raw.extend(_missing_data(client_ref, client, lang))
    raw.extend(_open_proposal(client_ref, client, lang))
    raw.extend(_material_change(client_ref, client, lang))
    # Tasks run last: a note that already speaks through another finding is not repeated as a task.
    raw.extend(_pending_task(client_ref, client, _used_note_paths(raw), lang))

    # Portfolio-level findings.
    for portfolio in portfolios:
        raw.extend(_concentration(client_ref, portfolio, lang))
        raw.extend(_sector_concentration(client_ref, portfolio, lang))
        raw.extend(_esg_alignment(client_ref, client, portfolio, lang))
        raw.extend(_allocation_drift(client_ref, portfolio, lang))
        raw.extend(_reinvestment(client_ref, portfolio, lang))
        raw.extend(_risk_alignment(client_ref, client, portfolio, lang))
        raw.extend(_performance_driver(client_ref, portfolio, lang))
        raw.extend(_fx_exposure(client_ref, portfolio, lang))

    # Scope discipline. The client-level extractors walk *all* of the client's portfolios (violations,
    # proposals, transactions, preference notes), so without this filter a briefing for one portfolio
    # reported the other depots' findings as its own — an ex-custody briefing claimed the main depot's
    # volatility breach. Findings that carry no portfolio id stay: they are the client's own story
    # (an open task from a note, a data gap), not another portfolio's number.
    if portfolio_nr:
        raw = [finding for finding in raw
               if finding.get("portfolio_id") is None or finding.get("portfolio_id") in scope_ids]

    # Sort: score desc, severity (high > medium > low), type.
    severity_order = {"high": 0, "medium": 1, "low": 2}
    raw.sort(key=lambda f: (-f["score"], severity_order.get(f["severity"], 9), f["type"]))

    # Assign ids.
    for i, finding in enumerate(raw, start=1):
        finding["id"] = f"f{i}"

    return raw
