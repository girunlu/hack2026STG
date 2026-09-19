"""R2 — context assembly: everything the briefing needs, in one deterministic bundle.

Produces the ``BriefingFacts`` keystone of ``notes-task/PROJECT.md`` §5.2. The bundle is the only thing
R4, R5, R6, B2 and T1 consume, so it is assembled explicitly here rather than by each consumer.

Pipeline order (the same order the UI reports progress in):

1. ``collect``   — client, portfolios, notes and tags from F5/F6
2. ``analyse``   — R3 findings over the collected data
3. ``rules``     — the data's own suitability violations, read as delivered
4. ``market``    — X1 live news filtered to the holdings in scope
5. ``house_view``— X2 curated view, matched against real exposures
6. ``actions``   — R5 candidates derived from the findings

Every stage is timed for real; nothing here sleeps or fabricates a delay. A stage that cannot run
(network down, no market coverage) records itself as unavailable instead of failing the request.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

from ..domain import crm, index, metrics
from ..i18n import DEFAULT_LANG, t
from ..text import compact
from ..domain.ingest import intnum, listof, num, text

ENGINE_VERSION = "0.1.0"

STAGES: list[tuple[str, str]] = [
    ("collect", "Klientendaten sammeln"),
    ("analyse", "Portfolio analysieren"),
    ("rules", "Regeln prüfen"),
    ("market", "Marktkontext abrufen"),
    ("house_view", "Bank-Sicht abgleichen"),
    ("actions", "Massnahmen ableiten"),
    ("compose", "Briefing verfassen"),
]


class UnknownClient(LookupError):
    """Raised when the requested client reference does not exist."""


class UnknownPortfolio(LookupError):
    """Raised when the portfolio does not belong to the requested client."""


class Stages:
    """Real per-stage timing, so the trigger can show genuine progress rather than a dead spinner."""

    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        self._rows: list[dict] = []
        self._started: dict[str, float] = {}
        self._lang = lang

    def start(self, stage_id: str) -> None:
        self._started[stage_id] = time.perf_counter()

    def finish(self, stage_id: str, status: str = "ok", note: str | None = None) -> None:
        key = f"stage.{stage_id}"
        label = t(key, self._lang)
        if label == key:  # not in the catalogue — fall back to the local map
            label = dict(STAGES).get(stage_id, stage_id)
        started = self._started.pop(stage_id, None)
        self._rows.append({
            "id": stage_id,
            "label": label,
            "ms": round((time.perf_counter() - started) * 1000, 1) if started else None,
            "status": status,
            "note": note,
        })

    def run(self, stage_id: str, action: Callable[[], Any], status_note: Callable[[Any], str | None] | None = None) -> Any:
        self.start(stage_id)
        try:
            result = action()
        except Exception as error:  # a failing stage degrades, it never aborts the briefing
            self.finish(stage_id, "unavailable", f"{type(error).__name__}: {error}")
            return None
        self.finish(stage_id, "ok", status_note(result) if status_note else None)
        return result

    @property
    def rows(self) -> list[dict]:
        return list(self._rows)

    def status_of(self, stage_id: str) -> str | None:
        for row in self._rows:
            if row["id"] == stage_id:
                return str(row["status"])
        return None


def _client_block(client: dict) -> dict:
    dataset = index.get()
    profile = dataset.risk_profile(intnum(client, "RiskProfileId", -1))
    return {
        "ref": text(client, "ClientRef"),
        "display_name": (text(client, "Company") or " ".join(
            part for part in (text(client, "FirstName"), text(client, "LastName")) if part
        ).strip()),
        "type": text(client, "RegulatoryClientTypeName") or None,
        "is_company": bool(client.get("IsClientACompany")),
        "reporting_currency": text(client, "ReportingCurrency") or None,
        "aum": round(num(client, "AssetsUnderManagementInDefaultCurrency"), 2),
        "liquidity": round(num(client, "LiquidityInDefaultCurrency"), 2),
        "risk_profile": {
            "id": intnum(profile, "Id", -1) or None,
            "name": text(profile, "Name"),
            "risk_level": intnum(profile, "RiskLevel", -1) or None,
            "max_vola": num(profile, "MaxVola") if "MaxVola" in profile else None,
            "max_prc": intnum(profile, "MaxPRC", -1) if "MaxPRC" in profile else None,
        } if profile else None,
        "esg_profile": text(client, "EsgProfileName") or None,
        "birthday": text(client, "Birthday") or None,
        "profiling_date": text(client, "ProfilingDateUtc") or None,
        "tags": [
            {"name": text(tag, "TagName"), "type": text(tag, "TagTypeName")}
            for tag in listof(client, "Tags")
        ],
        "overrides": crm.overrides(client),
    }


def _portfolio_block(portfolio: dict, lang: str = DEFAULT_LANG) -> dict:
    trailing = metrics.returns(portfolio)
    focus = metrics.concentration(portfolio)
    fx = metrics.fx_exposure(portfolio)
    gaps: list[str] = []
    if not isinstance(portfolio.get("SecurityPositions"), list):
        gaps.append(t("contract.security_positions_missing", lang))
    if "PerformanceYTD" not in portfolio:
        gaps.append(t("contract.performance_ytd_missing", lang))
    if "ValueAtRisk" not in portfolio:
        gaps.append(t("contract.value_at_risk_missing", lang))
    if "ExpectedReturn" not in portfolio:
        gaps.append(t("contract.expected_return_missing", lang))
    if str(trailing.get("return_basis") or "").startswith("available"):
        gaps.append(t("contract.return_basis_available", lang, days=trailing.get("return_available_days")))
    # Disclose dropped risk contributions (e.g., CASE-041 with int64 overflow)
    risk_data = metrics.risk_contributions(portfolio)
    dropped = risk_data.get("dropped", [])
    if dropped:
        names = [d.get("name") for d in dropped if d.get("name")]
        gaps.append(t("contract.risk_contributions_dropped", lang, count=len(dropped), names=", ".join(names[:3])))
    # An imported ex-custody portfolio must be labelled everywhere it appears, the briefing included
    # (B1: "carry a provenance flag everywhere it appears, including in the briefing text").
    is_external = bool(portfolio.get("IsExternal"))
    if is_external:
        gaps.append(t("contract.external_portfolio", lang, nr=text(portfolio, "PortfolioNr")))
    return {
        "id": intnum(portfolio, "PortfolioId", -1) or None,
        "nr": text(portfolio, "PortfolioNr"),
        "is_external": is_external,
        "provenance": text(portfolio, "Provenance") or ("clients.json" if not is_external else None),
        "name": text(portfolio, "Name"),
        "currency": text(portfolio, "PortfolioCurrency") or None,
        "aum": round(num(portfolio, "AssetsUnderManagementInDefaultCurrency"), 2),
        "volatility": num(portfolio, "Volatility") if "Volatility" in portfolio else None,
        "expected_return": num(portfolio, "ExpectedReturn") if "ExpectedReturn" in portfolio else None,
        "value_at_risk": num(portfolio, "ValueAtRisk") if "ValueAtRisk" in portfolio else None,
        "return_12m_pct": trailing["return_12m_pct"],
        "return_3m_pct": trailing["return_3m_pct"],
        "return_available_pct": trailing.get("return_available_pct"),
        "return_available_days": trailing.get("return_available_days"),
        "return_basis": trailing.get("return_basis"),
        "performance_as_of": trailing["as_of"],
        # The largest single line, straight from the metric — not inferred from a finding, which only
        # exists above a threshold and therefore read as "—" on the print sheet for most clients.
        "top_weight": focus["top_weight"],
        "top_security": focus["top_security"],
        # Currency vocabulary for the follow-up Q&A: the group weights the F4 rail shows, plus the
        # position currencies that map a code ("EUR", "USD") onto those groups.
        "currency_exposures": metrics.exposure(portfolio, "currency", lang=lang),
        "position_currencies": [
            {"code": row["currency"], "group": row["currency_group"], "weight": row["weight"]}
            for row in fx["rows"]
        ],
        "service": text(portfolio, "InvestmentServiceName") or None,
        "strategy": text(portfolio, "StrategyName") or None,
        "data_gaps": gaps,
    }


MAX_NEWS_HOLDINGS = 4
# A position from 2% up is worth a market line: the brief requires the portfolio to be connected to
# market developments. A fund-only portfolio has no single-security coverage at all — CASE-007 holds
# nothing but funds, and its briefing therefore declares the gap instead of inventing sector news.
NEWS_WEIGHT_FLOOR = 0.02
NEWS_DEADLINE_SECONDS = 8.0


def _market_block(portfolio_nrs: list[str], stages: Stages, lang: str = "en") -> tuple[list[dict], list[str], dict]:
    """X1: live headlines, filtered to the holdings actually in scope.

    Only positions that matter are queried (``NEWS_WEIGHT_FLOOR`` = 2% weight, at most
    ``MAX_NEWS_HOLDINGS`` = 4, equities first): fetching news for every line of a 20-position
    portfolio takes minutes and produces noise, not insight. The stage is additionally bounded by
    X1's own wall-clock budget, so the briefing always returns promptly.
    """
    dataset = index.get()
    held: dict[int, dict] = {}
    for nr in portfolio_nrs:
        found = dataset.portfolios.get(nr)
        if not found:
            continue
        _, portfolio = found
        for position in listof(portfolio, "SecurityPositions"):
            security_id = intnum(position, "SecurityId", -1)
            security = dataset.security(security_id)
            if not security or security_id in held:
                continue
            held[security_id] = {
                **security,
                "weight": num(position, "PortfolioValuePercentage"),
                "portfolio_nr": nr,
            }
    significant = [item for item in held.values() if item["weight"] >= NEWS_WEIGHT_FLOOR]
    # Direct equities are what news is actually about; a generic fund wrapper yields generic,
    # useless matches. Equities first, then the remaining large positions.
    equities = [item for item in significant if text(item, "SecurityTypeName").startswith("Shares")]
    others = [item for item in significant if not text(item, "SecurityTypeName").startswith("Shares")]
    ranked = (
        sorted(equities, key=lambda item: -item["weight"])
        + sorted(others, key=lambda item: -item["weight"])
    )[:MAX_NEWS_HOLDINGS]
    weights = {intnum(item, "Id", -1): item["weight"] for item in ranked}

    def fetch() -> dict:
        from ..external import news

        return news.fetch_market_context(ranked, weights=weights, deadline_seconds=NEWS_DEADLINE_SECONDS,
                                         lang=lang)

    stages.start("market")
    try:
        result = fetch()
    except Exception as error:  # a failing stage degrades, it never aborts the briefing
        stages.finish("market", "unavailable", f"{type(error).__name__}: {error}")
        return [], [t("stage.market_unavailable", lang)], {
            "providers_used": [], "fetched_at": None, "unavailable_items": [], "queried": len(ranked),
        }
    if not isinstance(result, dict):
        stages.finish("market", "unavailable", t("stage.market_unavailable", lang))
        return [], [t("stage.market_unavailable", lang)], {
            "providers_used": [], "fetched_at": None, "unavailable_items": [], "queried": len(ranked),
        }

    items = list(result.get("items") or [])
    raw_unavailable = list(result.get("unavailable") or [])

    # Carry the instrument each headline is about onto the item itself. The briefing offers the
    # market results of the instrument an insight names, and a linked security id alone would force
    # the UI to resolve it; the ISIN is what the search screen accepts.
    isin_by_id = {intnum(security, "Id", -1): text(security, "Isin") for security in ranked}
    for item in items:
        if not isinstance(item, dict):
            continue
        linked = [sid for sid in (item.get("linked_security_ids") or []) if sid in isin_by_id]
        item["security_id"] = linked[0] if linked else None
        item["isin"] = isin_by_id.get(linked[0]) if linked else None
        if not item["isin"]:
            item["isin"] = None

    unavailable_items = [
        {
            "name": str(item.get("name") or t("stage.unknown", lang)) if isinstance(item, dict) else str(item),
            "isin": item.get("isin") if isinstance(item, dict) else None,
            "reason": str(item.get("reason") or "") if isinstance(item, dict) else "",
        }
        for item in raw_unavailable
    ]
    summary: list[str] = []
    if unavailable_items:
        sample = ", ".join(compact(item["name"], 40) for item in unavailable_items[:3])
        summary.append(
            t("stage.market_unavailable_for", lang,
              count=len(unavailable_items), sample=sample)
        )
    # The stage status must tell the truth: no headlines means no market context, whether the
    # portfolio holds nothing queryable or the providers returned nothing usable.
    if items:
        status, note = "ok", t("stage.market_items", lang, count=len(items))
    elif not ranked:
        status, note = "unavailable", t("stage.market_not_applicable", lang)
    else:
        status, note = "unavailable", (summary[0] if summary else t("stage.market_unavailable", lang))
    stages.finish("market", status, note)
    meta = {
        "providers_used": result.get("providers_used") or [],
        "fetched_at": result.get("fetched_at"),
        "notes": result.get("notes") or [],
        "unavailable_items": unavailable_items,
        "queried": len(ranked),
        "is_mock": False,
    }
    return items, summary, meta


HOUSE_VIEW_DIMENSIONS = {
    "AssetClass": "asset_class",
    "CurrencyGroup": "currency",
    "CountryGroup": "country",
    "Industry": "industry",
}


def _house_view_block(portfolios: list[dict], stages: Stages) -> tuple[dict, list[str]]:
    """X2: the curated view, matched against the real exposure of each portfolio in scope."""

    def build() -> dict:
        from ..external import house_view

        view = house_view.house_view()
        matches: list[dict] = []
        for portfolio in portfolios:
            # ``house_view.match`` compares against the SAA vocabulary ("Shares", "Bonds",
            # "Swiss francs", …), which is what ``Securities[].SAA_*`` fields carry — the same
            # roll-up every other target comparison uses (PROJECT.md §7 rule 4).
            #
            # It must NOT use fund look-through here: ``split_funds=True`` explodes funds into their
            # ``FundUnbundlingMappings.AssetClassName`` fine taxonomy ("Equities Switzerland",
            # "Equities EmMa"), which cannot match an SAA category by construction. Doing so made
            # CASE-007 report "Shares 4.9%" instead of the real 56.7%, i.e. a stance justified by a
            # number that did not describe the portfolio.
            flat = {
                dimension: {
                    row["category"]: row["weight"]
                    for row in metrics.exposure(portfolio, key, split_funds=False)
                    if row["weight"] > 0
                }
                for dimension, key in HOUSE_VIEW_DIMENSIONS.items()
            }
            # The portfolio's own SAA targets, so a stance is not turned into a claim about the
            # portfolio ("portfolio overweight" while the same briefing says the asset class sits
            # 18.3 pp *below* its target). Dimensions without a target (currency, region, sector) get
            # no overweight/underweight statement at all — see ``house_view._classify_relation``.
            saa = metrics.saa_deviation(portfolio)
            targets = {
                str(row.get("category")): row.get("target")
                for row in (saa.get("rows") or [])
                if isinstance(row.get("target"), (int, float))
            } if saa.get("available") else {}
            matches.extend(house_view.match(flat, [portfolio], targets=targets) or [])
        return {**view, "matches": matches}

    result = stages.run("house_view", build)
    if not isinstance(result, dict):
        return {"source": None, "as_of": None, "mock": True, "stances": [], "matches": [],
                "unavailable": ["Bank-Sicht (Mock) nicht verfügbar"]}, ["Bank-Sicht (Mock) nicht verfügbar"]
    return result, [str(item) for item in (result.get("unavailable") or [])]


def assemble(client_ref: str, portfolio_nr: str | None = None, stages: Stages | None = None, lang: str = "en") -> dict:
    """Build the ``BriefingFacts`` bundle for one client (optionally scoped to one portfolio)."""
    dataset = index.get()
    tracker = stages or Stages(lang)
    client = dataset.client(client_ref)
    if not client:
        raise UnknownClient(f"Unknown client {client_ref!r}")

    def collect() -> tuple[dict, list[dict]]:
        blocks = [_portfolio_block(p, lang) for p in dataset.portfolios_of(client_ref)]
        if portfolio_nr:
            found = dataset.portfolio(client_ref, portfolio_nr)
            if not found:
                raise UnknownPortfolio(f"Unknown portfolio {portfolio_nr!r} for {client_ref}")
            blocks = [block for block in blocks if block["nr"] == portfolio_nr]
        return _client_block(client), blocks

    tracker.start("collect")
    client_block, portfolio_blocks = collect()
    tracker.finish("collect", "ok", t("stage.portfolios", lang, count=len(portfolio_blocks)))

    portfolio_dicts = [
        dataset.portfolios[p["nr"]][1] for p in portfolio_blocks if p["nr"] in dataset.portfolios
    ]

    def analyse() -> list[dict]:
        from ..domain import relevance

        return relevance.findings(client_ref, portfolio_nr, lang)

    finding_rows = tracker.run(
        "analyse", analyse, status_note=lambda rows: t("stage.findings", lang, count=len(rows))
    ) or []

    tracker.start("rules")
    violation_rows = metrics.violations(client, lang)
    if portfolio_nr:
        scoped_id = intnum(portfolio_dicts[0], "PortfolioId", -1) if portfolio_dicts else -1
        violation_rows = [row for row in violation_rows if row["portfolio_id"] == scoped_id]
    tracker.finish("rules", "ok", t("stage.violations", lang, count=len(violation_rows)))

    market_context, market_unavailable, market_meta = _market_block(
        [block["nr"] for block in portfolio_blocks], tracker, lang
    )
    house, house_unavailable = _house_view_block(portfolio_dicts, tracker)

    # Instrument candidates for buy/sell recommendations
    from ..domain import candidates
    instrument_candidates_data = candidates.candidates(client_ref, portfolio_nr)

    unavailable: list[str] = []
    for block in portfolio_blocks:
        unavailable.extend(block["data_gaps"])
    unavailable.extend(market_unavailable)
    unavailable.extend(house_unavailable)
    if client_block["risk_profile"] is None:
        unavailable.append(t("contract.risk_profile_unavailable", lang))
    if not portfolio_blocks:
        unavailable.append(t("contract.no_portfolio", lang))

    facts: dict = {
        "client": client_block,
        "portfolios": portfolio_blocks,
        "findings": finding_rows,
        "violations": violation_rows,
        "market_context": market_context,
        "market_meta": market_meta,
        "house_view": house,
        "instrument_candidates": instrument_candidates_data,
        "actions": [],
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data_as_of": dataset.data_as_of(),
            "unavailable": sorted(set(unavailable)),
            "engine_version": ENGINE_VERSION,
            "scope": {"client_ref": client_ref, "portfolio_nr": portfolio_nr},
            "stages": tracker.rows,
        },
    }

    tracker.start("actions")
    try:
        from . import actions as actions_module

        facts["actions"] = actions_module.build_actions(facts, lang)
        tracker.finish("actions", "ok", t("stage.actions_count", lang, count=len(facts["actions"])))
    except (SyntaxError, ImportError, NameError, AttributeError, TypeError) as error:
        # A programming error must never degrade into "this client has no actions": the briefing
        # would render, look complete, and silently drop the brief's fifth requirement. An
        # IndentationError left in actions.py did exactly that — it surfaced only as a stage note.
        raise
    except Exception as error:
        tracker.finish("actions", "unavailable", f"{type(error).__name__}: {error}")

    facts["meta"]["stages"] = tracker.rows
    return facts
