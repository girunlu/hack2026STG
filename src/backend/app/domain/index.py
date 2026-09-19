"""F5 — joins and integrity.

Loads the provided files once into an in-memory :class:`Dataset` and exposes every join the rest of
the backend needs. Rules that matter (see ``notes-task/PROJECT.md`` §7):

* Join securities on ``SecurityId``, never on ``Isin`` — one ISIN can be several share classes.
* ``FundUnbundlingMappings`` joins on ``FundSecurityId``; its ``Weight`` is **0–100** (per-fund sums
  are ≈100) and may be **negative**.
* ``StrategicAssetAllocations[].Mappings[].{Min,Target,Max}Percentage`` are fractions 0–1.
* Suitability violations are **display-only**; they are never recomputed or validated here.
"""

from __future__ import annotations

from typing import Any

from .. import cache
from .ingest import day, intnum, listof, load_raw, num, text

# Tolerance for comparing two float weights that should be equal.
EPSILON = 1e-9

# Canonical order of asset-class categories in the SAA panel.
ASSET_CLASS_ORDER = ["Liquidity", "Bonds", "Shares", "Real estate", "Specialties andCommodities"]


class Dataset:
    """Normalised, indexed view of ``clients.json`` + ``reference.json``."""

    def __init__(self, clients: list, reference: dict) -> None:
        self.clients: list[dict] = clients
        self.reference: dict = reference

        self.securities: list[dict] = listof(reference, "Securities")
        self.suitability_rules: list[dict] = listof(reference, "SuitabilityRules")
        self.risk_profiles: list[dict] = listof(reference, "RiskProfiles")
        self.saas: list[dict] = listof(reference, "StrategicAssetAllocations")
        self.all_fund_mappings: list[dict] = listof(reference, "FundUnbundlingMappings")
        self.tags: list[dict] = listof(reference, "Tags")
        self.advisory_types: list[dict] = listof(reference, "AdvisoryTypes")
        self.proposal_statuses: list[dict] = listof(reference, "ProposalStatuses")
        self.esg_profiles: list[dict] = listof(reference, "EsgProfiles")
        self.investment_services: list[dict] = listof(reference, "InvestmentServices")
        self.strategies: list[dict] = listof(reference, "Strategies")
        self.all_recommendation_lists: list[dict] = listof(reference, "RecommendationLists")

        self._by_ref: dict[str, dict] = {text(c, "ClientRef"): c for c in self.clients}
        self._securities: dict[int, dict] = {intnum(s, "Id", -1): s for s in self.securities}
        self._risk_profiles: dict[int, dict] = {intnum(p, "Id", -1): p for p in self.risk_profiles}
        self._saas: dict[int, dict] = {intnum(a, "Id", -1): a for a in self.saas}
        self._rules: dict[str, dict] = {text(r, "RuleCode"): r for r in self.suitability_rules}
        self._services: dict[int, dict] = {intnum(s, "Id", -1): s for s in self.investment_services}
        self._strategies: dict[int, dict] = {intnum(s, "Id", -1): s for s in self.strategies}

        self._funds: dict[int, list[dict]] = {}
        for row in self.all_fund_mappings:
            self._funds.setdefault(intnum(row, "FundSecurityId", -1), []).append(row)

        # ISIN -> every master row carrying it. One ISIN can be several currency share classes
        # (§7.2), so a caller that needs a classification has to cope with more than one row.
        self._by_isin: dict[str, list[dict]] = {}
        for security in self.securities:
            isin = text(security, "Isin")
            if isin:
                self._by_isin.setdefault(isin, []).append(security)

        # SecurityId -> names of the recommendation lists it belongs to. Membership of a named list
        # is the bank's own investment universe; ``Securities[].InRecommendationList`` is a wider
        # flag (403 rows vs 232 members) and every member carries it, so membership is the stricter
        # source and the one an evidence path can point at.
        self._recommendation_lists: dict[int, list[str]] = {}
        for row in self.all_recommendation_lists:
            name = text(row, "Name")
            for member in listof(row, "Securities"):
                self._recommendation_lists.setdefault(intnum(member, "SecurityId", -1), []).append(name)

        # SAA asset class -> recommendation-list members in that class. Built once per load, so
        # naming a candidate for an underweight class is a lookup, not a 504-row scan.
        self._recommendation_pools: dict[str, list[dict]] = {}
        for security in self.securities:
            if intnum(security, "Id", -1) in self._recommendation_lists:
                self._recommendation_pools.setdefault(text(security, "SAA_AssetClassName"), []).append(security)

        # portfolio number -> (client, portfolio)
        self.portfolios: dict[str, tuple[dict, dict]] = {}
        for client in self.clients:
            for portfolio in listof(client, "Portfolios"):
                nr = text(portfolio, "PortfolioNr")
                if nr:
                    self.portfolios[nr] = (client, portfolio)

        # currency code -> currency group, derived from the securities table (no hard-coded table)
        self._currency_group: dict[str, str] = {}
        for security in self.securities:
            code = text(security, "Currency")
            group = text(security, "CurrencyGroupName")
            if code and group:
                self._currency_group.setdefault(code, group)
        for code, group in (("CHF", "Swiss francs"), ("EUR", "Euro"), ("USD", "US-Dollar")):
            self._currency_group.setdefault(code, group)

        # client ref -> set of portfolio ids that exist on that client
        self._client_portfolio_ids: dict[str, set[int]] = {
            text(c, "ClientRef"): {intnum(p, "PortfolioId", -1) for p in listof(c, "Portfolios")}
            for c in self.clients
        }

    # ---- lookups -------------------------------------------------------------------------------

    def client(self, ref: str) -> dict | None:
        return self._by_ref.get(ref)

    def security(self, security_id: int) -> dict | None:
        return self._securities.get(security_id)

    def securities_by_isin(self, isin: str) -> list[dict]:
        """Every master row with this ISIN, in file order (``[]`` when the ISIN is unknown)."""
        return list(self._by_isin.get(isin, ()))

    def security_by_isin(self, isin: str) -> dict | None:
        rows = self._by_isin.get(isin) or []
        return rows[0] if rows else None

    def saa(self, saa_id: int) -> dict | None:
        return self._saas.get(saa_id)

    def risk_profile(self, profile_id: int) -> dict | None:
        return self._risk_profiles.get(profile_id)

    def rule(self, rule_code: str) -> dict | None:
        return self._rules.get(rule_code)

    def investment_service(self, service_id: int) -> dict | None:
        return self._services.get(service_id)

    def strategy(self, strategy_id: int) -> dict | None:
        return self._strategies.get(strategy_id)

    def fund_mappings(self, security_id: int) -> list[dict]:
        """Look-through rows for a fund; ``[]`` when the security is not a fund with mappings."""
        return self._funds.get(security_id, [])

    def recommendation_lists(self, security_id: int) -> list[str]:
        """Names of the recommendation lists a security belongs to (``[]`` when it is in none)."""
        return list(self._recommendation_lists.get(security_id, ()))

    def in_recommendation_list(self, security_id: int) -> bool:
        """Whether the security is a member of any recommendation list."""
        return security_id in self._recommendation_lists

    def recommendation_pool(self, saa_asset_class: str) -> list[dict]:
        """Recommendation-list members classified in one SAA asset class, in file order."""
        return list(self._recommendation_pools.get(saa_asset_class, ()))

    def currency_group(self, currency: str) -> str:
        """Currency group for a cash position (``BTC``/``ETH``/``OZG`` fall back to ``Andere``)."""
        return self._currency_group.get(currency, "Andere")

    def portfolio(self, client_ref: str, portfolio_nr: str) -> tuple[dict, dict] | None:
        found = self.portfolios.get(portfolio_nr)
        if not found or text(found[0], "ClientRef") != client_ref:
            return None
        return found

    def portfolios_of(self, client_ref: str) -> list[dict]:
        client = self.client(client_ref)
        return listof(client, "Portfolios") if client else []

    def portfolio_ids_of(self, client_ref: str) -> set[int]:
        return set(self._client_portfolio_ids.get(client_ref, set()))

    def portfolio_by_id(self, portfolio_id: int) -> dict | None:
        for _, portfolio in self.portfolios.values():
            if intnum(portfolio, "PortfolioId", -1) == portfolio_id:
                return portfolio
        return None

    def data_as_of(self) -> str | None:
        """Newest date actually present in the data: last performance point or a factory date."""
        dates: list[str] = []
        for _, portfolio in self.portfolios.values():
            for point in listof(portfolio, "PerformanceHistory"):
                stamp = day(point.get("Date") if isinstance(point, dict) else None)
                if stamp:
                    dates.append(stamp)
            stamp = day(portfolio.get("FactoryDateUtc"))
            if stamp:
                dates.append(stamp)
        return max(dates) if dates else None

    # ---- integrity -----------------------------------------------------------------------------

    def integrity_report(self) -> dict:
        """Dangling references and missing profiles, returned **as data**, never as exceptions."""
        dangling: list[dict] = []
        for client in self.clients:
            ref = text(client, "ClientRef")
            known = self._client_portfolio_ids.get(ref, set())
            for violation in listof(client, "SuitabilityViolations"):
                portfolio_id = intnum(violation, "PortfolioId", -1)
                if portfolio_id not in known:
                    dangling.append({
                        "client_ref": ref,
                        "kind": "violation",
                        "portfolio_id": portfolio_id,
                        "rule_code": text(violation, "RuleCode"),
                        "severity": text(violation, "Severity"),
                        "reason": "portfolio id exists on no client",
                    })
            for proposal in listof(client, "Proposals"):
                portfolio_id = intnum(proposal, "PortfolioId", -1)
                if portfolio_id not in known:
                    dangling.append({
                        "client_ref": ref,
                        "kind": "proposal",
                        "portfolio_id": portfolio_id,
                        "rule_code": None,
                        "severity": None,
                        "reason": "portfolio id exists on no client",
                    })

        without_risk_profile = [text(c, "ClientRef") for c in self.clients if not num(c, "RiskProfileId", 0)]
        without_positions = [
            nr for nr, (_, p) in self.portfolios.items() if not isinstance(p.get("SecurityPositions"), list)
        ]
        notes = [text(n, "Note") for c in self.clients for n in listof(c, "ClientNotes")]
        return {
            "dangling_portfolio_refs": dangling,
            "clients_without_risk_profile": without_risk_profile,
            "portfolios_without_positions": sorted(without_positions),
            "notes_total": len(notes),
            "notes_distinct": len(set(notes)),
            "known_data_typos": ["'Specialties andCommodities' (missing space) — exact-string matching"],
            "counts": {
                "clients": len(self.clients),
                "portfolios": len(self.portfolios),
                "securities": len(self.securities),
                "fund_mappings": len(self.all_fund_mappings),
            },
        }


_dataset: Dataset | None = None


def load(force: bool = False) -> Dataset:
    """Load (once) and return the process-wide dataset.

    This is the single reload path (see ``PROJECT.md`` §5.5), so it is also where any cached derivation
    of the dataset is dropped: a briefing computed from the previous data must never survive an upload,
    an import or a reload.
    """
    global _dataset
    if _dataset is None or force:
        clients, reference = load_raw()
        _dataset = Dataset(clients, reference)
        cache.invalidate()
    return _dataset


def get() -> Dataset:
    """Accessor used by every consumer; loads lazily on first use."""
    return load()
