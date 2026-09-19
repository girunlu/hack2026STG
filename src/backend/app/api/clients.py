"""F2 client overview, F3 client detail, F4 portfolio detail — projections over F5/F6.

Nothing here reads a file or index into raw JSON: every value comes from ``app.domain``. Derived
columns (``last_changed``, ``last_consultation``, ``days_to_birthday``) are computed against
``data_as_of`` — the newest date present in the data — and never against the wall clock, so the API
is deterministic. Each derived column carries its ``basis`` or a contract note saying how it is made.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from ..domain import crm, index, metrics, rail
from ..domain.ingest import day, intnum, listof, num, text
from ..i18n import DEFAULT_LANG, resolve_lang, t
from .schemas import ClientDetailResponse, ClientRow, ClientsResponse, Money, PortfolioDetailResponse, Tab


def get_lang(lang: str | None = Query(None, alias="lang")) -> str:
    """FastAPI dependency: resolve the response language from ?lang= query parameter."""
    return resolve_lang(lang, None)


router = APIRouter(prefix="/api", tags=["F2", "F3", "F4"])

# The advisor identity mocked from the URO screenshots (F1 spec §5). Not case data.
ADVISOR = {"name": "Hans Muster", "initials": "HM"}

BIRTHDAY_WINDOW_DAYS = 90
MATURITY_WINDOW_DAYS = 365


def _contract_notes(lang: str) -> list[str]:
    """Return contract notes translated to the requested language."""
    return [
        t("contract.street_absent", lang),
        t("contract.last_changed", lang),
        t("contract.last_consultation", lang),
        t("contract.days_to_birthday", lang),
    ]


# ------------------------------------------------------------------------------------- helpers


def _display_name(client: dict) -> str:
    company = text(client, "Company")
    if company:
        return company
    parts = [text(client, "FirstName"), text(client, "LastName")]
    return " ".join(part for part in parts if part).strip() or text(client, "ClientRef")


def _as_date(stamp: str | None) -> date | None:
    if not stamp:
        return None
    try:
        return date(int(stamp[:4]), int(stamp[5:7]), int(stamp[8:10]))
    except ValueError:
        return None


def _days_to_birthday(birthday: str | None, reference: str | None) -> int | None:
    born, today = _as_date(birthday), _as_date(reference)
    if not born or not today:
        return None
    for year in (today.year, today.year + 1):
        try:
            candidate = born.replace(year=year)
        except ValueError:  # 29 February
            candidate = date(year, 3, 1)
        if candidate >= today:
            return (candidate - today).days
    return None


def _last_changed(client: dict) -> str | None:
    stamps = [crm.latest_activity(client)["date"]]
    stamps += [day(p.get("FactoryDateUtc")) for _, p in _iter_portfolios(client)]
    stamps += [day(n.get("CreatedByDateUTC")) for n in listof(client, "ClientNotes")]
    candidates = [stamp for stamp in stamps if stamp]
    return max(candidates) if candidates else None


def _iter_portfolios(client: dict):
    return [(client, p) for p in listof(client, "Portfolios")]


def _split_portfolios(client: dict) -> tuple[list[dict], list[dict]]:
    """Own vs imported (ex-custody) portfolios, in the order they are attached.

    ``ingest.load_raw`` merges imported portfolios into ``Portfolios[]``, so one client record holds
    both. The dashboard's portfolio count and the client's AUM describe the bank's own book; the
    imported slice is reported next to it, exactly as the reference UI keeps ``Fremdbanken`` apart
    from ``Eigene Portfolios``. Counting them as one number was the defect this replaces.
    """
    portfolios = listof(client, "Portfolios")
    own = [p for p in portfolios if not p.get("IsExternal")]
    external = [p for p in portfolios if p.get("IsExternal")]
    return own, external


def _has_maturities(client: dict, reference: str | None) -> bool:
    dataset = index.get()
    start = _as_date(reference)
    if not start:
        return False
    limit = start + timedelta(days=MATURITY_WINDOW_DAYS)
    for _, portfolio in _iter_portfolios(client):
        for position in listof(portfolio, "SecurityPositions"):
            security = dataset.security(intnum(position, "SecurityId", -1))
            maturity = _as_date(day(security.get("MaturityDateUtc")) if security else None)
            if maturity and start <= maturity <= limit:
                return True
    return False


def _severity_counts(client: dict) -> tuple[int, int]:
    severities = [text(v, "Severity") for v in listof(client, "SuitabilityViolations")]
    return severities.count("Error"), severities.count("Warning")


def _client_row(client: dict, reference: str | None, lang: str = "en") -> ClientRow:
    errors, warnings = _severity_counts(client)
    activity = crm.latest_activity(client)
    own, external = _split_portfolios(client)
    gaps: list[str] = []
    if not num(client, "RiskProfileId", 0):
        gaps.append(t("contract.risk_profile_unavailable", lang))
    if not text(client, "Birthday"):
        gaps.append(t("contract.birthday_missing", lang))
    return ClientRow(
        ref=text(client, "ClientRef"),
        client_id=intnum(client, "ClientId", -1) or None,
        name=_display_name(client),
        type=text(client, "RegulatoryClientTypeName") or None,
        is_company=bool(client.get("IsClientACompany")),
        reporting_currency=text(client, "ReportingCurrency") or None,
        aum=round(num(client, "AssetsUnderManagementInDefaultCurrency"), 2),
        liquidity_pct=crm.liquidity_ratio(client),
        birthday=day(client.get("Birthday")),
        days_to_birthday=_days_to_birthday(day(client.get("Birthday")), reference),
        profiling_date=day(client.get("ProfilingDateUtc")),
        last_changed=_last_changed(client),
        last_consultation=activity["date"],
        last_consultation_basis=activity["basis"],
        portfolio_count=len(own),
        external_portfolio_count=len(external),
        external_aum=round(sum(num(p, "AssetsUnderManagementInDefaultCurrency") for p in external), 2),
        violation_count=errors,
        warning_count=warnings,
        has_violation=errors > 0,
        has_warning=warnings > 0,
        has_maturities=_has_maturities(client, reference),
        data_gaps=gaps,
    )


def _tabs(rows: list[ClientRow], lang: str = "en") -> list[Tab]:
    reference = index.get().data_as_of()
    stale = _as_date(reference)
    stale_before = (stale - timedelta(days=365)).isoformat() if stale else None
    return [
        Tab(id="kunden", label=t("tab.kunden.label", lang), count=len(rows), hint=t("tab.kunden.hint", lang)),
        Tab(id="beratungen", label=t("tab.beratungen.label", lang), hint=t("tab.beratungen.hint", lang),
            count=sum(1 for r in rows if r.last_consultation)),
        Tab(id="liquidity_gt_10", label=t("tab.liquidity.label", lang), hint=t("tab.liquidity.hint", lang),
            count=sum(1 for r in rows if (r.liquidity_pct or 0) > 0.10)),
        Tab(id="maturities", label=t("tab.maturities.label", lang),
            hint=t("tab.maturities.hint", lang, days=MATURITY_WINDOW_DAYS),
            count=sum(1 for r in rows if r.has_maturities)),
        Tab(id="last_consultation_gt_12m", label=t("tab.last_consultation.label", lang),
            hint=t("tab.last_consultation.hint", lang),
            count=sum(1 for r in rows if not r.last_consultation or (stale_before and r.last_consultation < stale_before))),
        Tab(id="rule_violations", label=t("tab.rule_violations.label", lang),
            hint=t("tab.rule_violations.hint", lang),
            count=sum(1 for r in rows if r.has_violation)),
        Tab(id="warnings", label=t("tab.warnings.label", lang), hint=t("tab.warnings.hint", lang),
            count=sum(1 for r in rows if r.has_warning)),
        Tab(id="birthdays", label=t("tab.birthdays.label", lang),
            hint=t("tab.birthdays.hint", lang, days=BIRTHDAY_WINDOW_DAYS),
            count=sum(1 for r in rows if r.days_to_birthday is not None and r.days_to_birthday <= BIRTHDAY_WINDOW_DAYS)),
    ]


def _risk_profile(client: dict) -> dict | None:
    profile = index.get().risk_profile(intnum(client, "RiskProfileId", -1))
    if not profile:
        return None
    return {
        "id": intnum(profile, "Id", -1),
        "name": text(profile, "Name"),
        "risk_level": intnum(profile, "RiskLevel", -1) or None,
        "max_vola": num(profile, "MaxVola") if "MaxVola" in profile else None,
        "max_prc": intnum(profile, "MaxPRC", -1) if "MaxPRC" in profile else None,
        "equity_quote": num(profile, "EquityQuoteInPercent") if "EquityQuoteInPercent" in profile else None,
    }


def _client_block(client: dict) -> dict:
    errors, warnings = _severity_counts(client)
    own, external = _split_portfolios(client)
    ref = text(client, "ClientRef")
    return {
        "ref": ref,
        "client_id": intnum(client, "ClientId", -1) or None,
        "display_name": _display_name(client),
        "first_name": text(client, "FirstName") or None,
        "last_name": text(client, "LastName") or None,
        "company": text(client, "Company") or None,
        "type": text(client, "RegulatoryClientTypeName") or None,
        "is_company": bool(client.get("IsClientACompany")),
        "is_employee": bool(client.get("IsEmployee")),
        "reporting_currency": text(client, "ReportingCurrency") or None,
        "aum": round(num(client, "AssetsUnderManagementInDefaultCurrency"), 2),
        "liquidity": round(num(client, "LiquidityInDefaultCurrency"), 2),
        "liquidity_pct": crm.liquidity_ratio(client),
        "risk_profile": _risk_profile(client),
        "risk_profile_id": intnum(client, "RiskProfileId", -1) or None,
        "esg_profile": text(client, "EsgProfileName") or None,
        "birthday": day(client.get("Birthday")),
        "profiling_date": day(client.get("ProfilingDateUtc")),
        "last_changed": _last_changed(client),
        "last_consultation": crm.latest_activity(client)["date"],
        "last_consultation_basis": crm.latest_activity(client)["basis"],
        "street": None,
        "zip": None,
        "city": None,
        "counts": {
            "portfolios": len(own),
            "external_portfolios": len(external),
            "proposals": len(listof(client, "Proposals")),
            "notes": len(listof(client, "ClientNotes")),
            "errors": errors,
            "warnings": warnings,
            "tags": len(listof(client, "Tags")),
        },
    }


def _portfolio_summary(client: dict, portfolio: dict, lang: str = "en") -> dict:
    dataset = index.get()
    trailing = metrics.returns(portfolio)
    focus = metrics.concentration(portfolio)
    gaps: list[str] = []
    if not isinstance(portfolio.get("SecurityPositions"), list):
        gaps.append(t("contract.security_positions_missing", lang))
    if "PerformanceYTD" not in portfolio:
        gaps.append(t("contract.performance_ytd_missing", lang))
    if not num(portfolio, "ValueAtRisk", 0) and "ValueAtRisk" not in portfolio:
        gaps.append(t("contract.value_at_risk_missing", lang))
    top_security = dataset.security(focus["top_security_id"]) if focus["top_security_id"] else None
    return {
        "id": intnum(portfolio, "PortfolioId", -1) or None,
        "nr": text(portfolio, "PortfolioNr"),
        "name": text(portfolio, "Name"),
        "currency": text(portfolio, "PortfolioCurrency") or None,
        "aum": round(num(portfolio, "AssetsUnderManagementInDefaultCurrency"), 2),
        "volatility": num(portfolio, "Volatility") if "Volatility" in portfolio else None,
        "expected_return": num(portfolio, "ExpectedReturn") if "ExpectedReturn" in portfolio else None,
        "value_at_risk": num(portfolio, "ValueAtRisk") if "ValueAtRisk" in portfolio else None,
        "service": text(portfolio, "InvestmentServiceName") or None,
        "strategy": text(portfolio, "StrategyName") or None,
        "saa_id": intnum(portfolio, "StrategicAssetAllocationId", -1) or None,
        "is_external": bool(portfolio.get("IsExternal")),
        # An imported portfolio carries ``Provenance: "ex_custody"``; only the case data has no
        # provenance field at all, so the absent-key default stays "clients.json".
        "source": text(portfolio, "Source") or text(portfolio, "Provenance") or "clients.json",
        "return_12m_pct": trailing["return_12m_pct"],
        "return_3m_pct": trailing["return_3m_pct"],
        "performance_as_of": trailing["as_of"],
        "top_weight": focus["top_weight"],
        "top_security": focus["top_security"],
        "top_currency": text(top_security, "Currency") or None,
        "position_count": len(listof(portfolio, "SecurityPositions")),
        "data_gaps": gaps,
    }


def _proposal_rows(client: dict, lang: str = "en") -> list[dict]:
    dataset = index.get()
    statuses = {intnum(s, "Id", -1): s for s in dataset.proposal_statuses}
    known = dataset.portfolio_ids_of(text(client, "ClientRef"))
    rows: list[dict] = []
    for proposal in listof(client, "Proposals"):
        portfolio_id = intnum(proposal, "PortfolioId", -1)
        container = dataset.portfolio_by_id(portfolio_id)
        status = text(proposal, "ProposalStatusName")
        status_row = statuses.get(intnum(proposal, "ProposalStatusId", -1), {})
        changed = day(proposal.get("FinalizedDateUTC")) or day(proposal.get("ProposedDateUTC"))
        rows.append({
            "id": intnum(proposal, "ProposalId", -1) or None,
            "portfolio_id": portfolio_id,
            "portfolio_nr": text(container, "PortfolioNr") if container else None,
            "portfolio_name": text(container, "Name") if container else None,
            "portfolio_known": portfolio_id in known,
            "container": text(container, "Name") if container else t("contract.portfolio_unknown", lang, id=portfolio_id),
            "advisory_type": text(proposal, "AdvisoryTypeName"),
            "service": text(container, "InvestmentServiceName") if container else None,
            "status": status,
            "status_archived": bool(status_row.get("IsArchived")),
            "status_allows_submit": bool(status_row.get("AllowTransactionSubmit")),
            "reason": text(proposal, "Reason") or None,
            "proposed_at": day(proposal.get("ProposedDateUTC")),
            "changed_at": changed,
            "changed_by": None,
            "expected_return": num(proposal, "ExpectedReturn") if "ExpectedReturn" in proposal else None,
            "volatility": num(proposal, "Volatility") if "Volatility" in proposal else None,
            "security_count": len(listof(proposal, "SecurityPositions")),
            "can_delete": status == "Entwurf",
            "data_gaps": [t("contract.changed_by_absent", lang)],
        })
    rows.sort(key=lambda row: (row["changed_at"] or "", row["id"] or 0), reverse=True)
    return rows


GROUP_ORDER = index.ASSET_CLASS_ORDER


def _positions(portfolio: dict, lang: str = "en") -> list[dict]:
    dataset = index.get()
    rows: list[dict] = []
    # One guard for the whole project: a risk figure that cannot be true becomes a declared gap,
    # never a number. See ``metrics.risk_contributions`` — one position in the case data overflows.
    unusable = {row["index"]: row for row in metrics.risk_contributions(portfolio)["dropped"]}
    for position_index, position in enumerate(listof(portfolio, "SecurityPositions")):
        security_id = intnum(position, "SecurityId", -1)
        bad_risk = unusable.get(position_index)
        security = dataset.security(security_id)
        mappings = dataset.fund_mappings(security_id)
        rows.append({
            "kind": "security",
            "position": text(position, "SecurityName"),
            "security_id": security_id or None,
            "kennung": text(position, "Isin") or None,
            "valor": text(position, "Valor") or None,
            "whg": text(position, "Currency") or None,
            "prc": intnum(security, "PRC", -1) if security and "PRC" in security else None,
            "quantity": num(position, "Quantity") if "Quantity" in position else None,
            "price": num(position, "PricePerUnit") if "PricePerUnit" in position else None,
            "value": round(num(position, "TotalAmountInPortfolioCurrency"), 4),
            "weight": num(position, "PortfolioValuePercentage") if "PortfolioValuePercentage" in position else None,
            "risk_contribution": None if bad_risk else (num(position, "ContributionVolatility") if "ContributionVolatility" in position else None),
            "marginal_risk": None if bad_risk else (num(position, "MarginalContributionToRisk") if "MarginalContributionToRisk" in position else None),
            "risk_figure_dropped": bool(bad_risk),
            "risk_figure_reason": bad_risk["reason"] if bad_risk else None,
            "sustainability_score": num(security, "SustainabilityScore") if security and "SustainabilityScore" in security else None,
            "sustainability_rating": intnum(security, "SustainabilityRatingId", -1) if security and "SustainabilityRatingId" in security else None,
            "asset_class": text(security, "SAA_AssetClassName", t("contract.not_classified", lang)) if security else t("contract.not_classified", lang),
            "group": text(security, "SAA_AssetClassName", t("contract.not_classified", lang)) if security else t("contract.not_classified", lang),
            "is_fund": bool(mappings),
            "lookthrough_rows": len(mappings),
            "has_price": num(position, "PricePerUnit") > 0,
            "cost_basis": None,
            "success": None,
            "rules": None,
        })
    for account in listof(portfolio, "AccountPositions"):
        rows.append({
            "kind": "account",
            "position": text(account, "AccountName"),
            "security_id": None,
            "kennung": None,
            "valor": None,
            "whg": text(account, "Currency") or None,
            "prc": None,
            "quantity": None,
            "price": None,
            "value": round(num(account, "TotalAmountInPortfolioCurrency"), 4),
            "weight": num(account, "PortfolioValuePercentage") if "PortfolioValuePercentage" in account else None,
            "risk_contribution": None,
            "marginal_risk": None,
            "risk_figure_dropped": False,
            "risk_figure_reason": None,
            "sustainability_score": None,
            "sustainability_rating": None,
            "asset_class": "Liquidity",
            "group": "Liquidity",
            "is_fund": False,
            "lookthrough_rows": 0,
            "has_price": True,
            "cost_basis": None,
            "success": None,
            "rules": None,
        })

    def sort_key(row: dict) -> tuple[int, float]:
        group = row["group"]
        rank = GROUP_ORDER.index(group) if group in GROUP_ORDER else len(GROUP_ORDER)
        return (rank, -row["value"])

    rows.sort(key=sort_key)
    return rows


def _groups(rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        bucket = grouped.setdefault(row["group"], {"category": row["group"], "value": 0.0, "positions": 0})
        bucket["value"] = round(bucket["value"] + row["value"], 4)
        bucket["positions"] += 1
    total = sum(bucket["value"] for bucket in grouped.values())
    ordered = sorted(
        grouped.values(),
        key=lambda bucket: GROUP_ORDER.index(bucket["category"]) if bucket["category"] in GROUP_ORDER else len(GROUP_ORDER),
    )
    for bucket in ordered:
        bucket["weight"] = round(bucket["value"] / total, 6) if total else 0.0
        bucket["expandable"] = True
    return ordered


def _portfolio_violations(client: dict, portfolio: dict, lang: str = "en") -> list[dict]:
    portfolio_id = intnum(portfolio, "PortfolioId", -1)
    return [v for v in metrics.violations(client, lang) if v["portfolio_id"] == portfolio_id]


# -------------------------------------------------------------------------------------- routes


@router.get("/clients", response_model=ClientsResponse)
def clients(lang: str = Depends(get_lang)) -> ClientsResponse:
    """F2 — every client, with the filter-tab counts computed from real data."""
    dataset = index.get()
    reference = dataset.data_as_of()
    rows = [_client_row(client, reference, lang) for client in dataset.clients]
    rows.sort(key=lambda row: row.name.casefold())
    book_total = round(sum(row.aum for row in rows), 2)
    errors = sum(row.violation_count for row in rows)
    warnings = sum(row.warning_count for row in rows)
    return ClientsResponse(
        advisor=ADVISOR,
        book_total=Money(currency="CHF", amount=book_total),
        data_as_of=reference,
        counts={
            "clients": len(rows),
            "portfolios": len(dataset.portfolios),
            "proposals": sum(len(listof(c, "Proposals")) for c in dataset.clients),
            # "Pendente Beratungen" on the dashboard — draft proposals, same definition the client
            # endpoint already uses for its own `open_proposals` count.
            "open_proposals": sum(
                1
                for client in dataset.clients
                for proposal in listof(client, "Proposals")
                if text(proposal, "ProposalStatusName") == "Entwurf"
            ),
            "notes": sum(len(listof(c, "ClientNotes")) for c in dataset.clients),
            "violating_clients": sum(1 for row in rows if row.has_violation),
            "warning_clients": sum(1 for row in rows if row.has_warning),
            "error_violations": errors,
            "warning_violations": warnings,
            "violations": errors + warnings,
            "maturities": sum(1 for row in rows if row.has_maturities),
        },
        tabs=_tabs(rows, lang),
        rows=rows,
        integrity=dataset.integrity_report(),
        notes=_contract_notes(lang),
        lang=lang,
    )


@router.get("/clients/{client_ref}", response_model=ClientDetailResponse)
def client_detail(client_ref: str, lang: str = Depends(get_lang)) -> ClientDetailResponse:
    """F3 — one client: portfolios, Beratungen, notes, tags, violations."""
    dataset = index.get()
    client = dataset.client(client_ref)
    if not client:
        raise HTTPException(status_code=404, detail=f"Unknown client {client_ref}")

    portfolios = [_portfolio_summary(client, p, lang) for _, p in _iter_portfolios(client)]
    proposals = _proposal_rows(client, lang)
    violations = metrics.violations(client, lang)
    notes = crm.notes(client)
    tags = crm.tags(client)
    overrides = crm.overrides(client)
    block = _client_block(client)

    gaps: list[str] = []
    if block["risk_profile"] is None:
        gaps.append(t("contract.risk_profile_unavailable_detail", lang))
    if not text(client, "Birthday"):
        gaps.append(t("contract.birthday_missing", lang))
    if block["company"] is None and not block["last_name"]:
        gaps.append(t("contract.no_last_name", lang))
    if any(not p["portfolio_known"] for p in proposals):
        gaps.append(t("contract.no_portfolio_on_client", lang))
    if not portfolios:
        gaps.append(t("contract.no_portfolio", lang))
    if not proposals:
        gaps.append(t("contract.no_consultations", lang))

    return ClientDetailResponse(
        client=block,
        portfolios=portfolios,
        proposals=proposals,
        violations=violations,
        notes=notes,
        tags=tags,
        overrides=overrides,
        counts={
            "portfolios": len(portfolios),
            "external_portfolios": sum(1 for p in portfolios if p["is_external"]),
            "proposals": len(proposals),
            "open_proposals": sum(1 for p in proposals if p["status"] == "Entwurf"),
            "rejected_proposals": sum(1 for p in proposals if p["status"] == "Abgelehnt"),
            "violations": len(violations),
            "errors": sum(1 for v in violations if v["severity"] == "Error"),
            "warnings": sum(1 for v in violations if v["severity"] == "Warning"),
            "dangling_violations": sum(1 for v in violations if not v["portfolio_known"]),
            "notes": len(notes),
            "distinct_notes": len({n["text"] for n in notes}),
            "region_tags": len(tags["region"]),
            "industry_tags": len(tags["industry"]),
            "overrides": len(overrides),
        },
        data_gaps=gaps,
        lang=lang,
    )


@router.get("/clients/{client_ref}/portfolios/{portfolio_nr}", response_model=PortfolioDetailResponse)
def portfolio_detail(client_ref: str, portfolio_nr: str, lang: str = Depends(get_lang)) -> PortfolioDetailResponse:
    """F4 — the analytical view of one portfolio."""
    dataset = index.get()
    found = dataset.portfolio(client_ref, portfolio_nr)
    if not found:
        raise HTTPException(status_code=404, detail=f"Unknown portfolio {portfolio_nr} for {client_ref}")
    client, portfolio = found

    saa = metrics.saa_deviation(portfolio)
    positions = _positions(portfolio, lang)
    groups = _groups(positions)
    total_value = round(sum(row["value"] for row in positions), 4)
    violations = _portfolio_violations(client, portfolio, lang)
    prc = metrics.prc_profile(portfolio)
    sustain = metrics.sustainability(portfolio)
    maturity = metrics.maturity_buckets(portfolio, dataset.data_as_of(), lang)

    gaps: list[str] = []
    if not saa["available"]:
        gaps.append(t("contract.no_saa_targets", lang))
    if not isinstance(portfolio.get("SecurityPositions"), list):
        gaps.append(t("contract.security_positions_missing", lang))
    unpriced = [row["position"] for row in positions if row["kind"] == "security" and not row["has_price"]]
    if unpriced:
        gaps.append(t("contract.no_market_price", lang, names=", ".join(unpriced[:5])))
    if "ValueAtRisk" not in portfolio:
        gaps.append(t("contract.value_at_risk_missing", lang))
    gaps.append(t("contract.price_cost_basis", lang))
    gaps.append(t("contract.per_position_rules", lang))
    if prc["max_prc"] is None:
        gaps.append(t("contract.prc_missing_all", lang))
    # A risk figure that cannot be true is declared here instead of being rendered (see _positions).
    risk = metrics.risk_contributions(portfolio)
    if risk["dropped"]:
        gaps.append(t("contract.risk_figure_dropped", lang,
                      count=len(risk["dropped"]),
                      names=", ".join(row["name"] for row in risk["dropped"][:3])))
    if not risk["available"]:
        gaps.append(t("contract.risk_contributions_unavailable", lang, reason=risk["reason"]))

    return PortfolioDetailResponse(
        client=_client_block(client),
        portfolio=_portfolio_summary(client, portfolio, lang),
        saa=saa,
        positions=positions,
        groups=groups,
        total={
            "value": total_value,
            "currency": text(portfolio, "PortfolioCurrency") or None,
            "positions": sum(1 for row in positions if row["kind"] == "security"),
            "accounts": sum(1 for row in positions if row["kind"] == "account"),
            "portfolio_aum": round(num(portfolio, "AssetsUnderManagementInDefaultCurrency"), 4),
        },
        exposures=metrics.exposures(portfolio, lang),
        fx=metrics.fx_exposure(portfolio),
        prc=prc,
        sustainability={**sustain, "esg_profile": text(client, "EsgProfileName") or None},
        maturity=maturity,
        metrics=rail.rail_widgets(client, portfolio, lang),
        violations=violations,
        integrity={
            "portfolio_known": intnum(portfolio, "PortfolioId", -1) in dataset.portfolio_ids_of(client_ref),
            "data_as_of": dataset.data_as_of(),
            "factory_date": day(portfolio.get("FactoryDateUtc")),
        },
        data_gaps=gaps,
        lang=lang,
    )
