"""Named buy / sell / switch candidates — the data half of the brief's last action kind.

``task_def.md`` lists *"Identifying securities to buy, sell or switch"* among the possible next best
actions, and `REVIEW.md` §9.4 measured it at **0/47 clients**: R5 could say "reduce the
concentration" but never name an instrument. Both ingredients are already in the flat files, so this
is a join rather than a new data source (`REVIEW.md` §11.1.1):

* an **open proposal** (``ProposalStatusName == "Entwurf"``) is a complete target portfolio — its
  ``SecurityPositions`` carry ``Isin``, ``SecurityName`` and ``ProposalValuePercentage``, and the five
  drafts sum to 0.966–1.002 of the portfolio. Comparing those weights with what the client holds
  today names the instruments the bank's own document adds, increases, reduces or exits;
* ``reference.RecommendationLists`` (one list, *"Recommendation list free assets"*, 232 members) is
  the bank's investment universe — the engine even evaluates a ``PositionInRecommendationListRuleField``
  — so for an asset class below its SAA target, the members of that class the client does **not**
  already hold are the names worth discussing.

Deliberately **data, not prose**: no catalogue keys and no rendered sentence, because R4/R5 own the
wording and `app/i18n.py`. Every row carries its numbers, the stable keys a renderer needs
(``direction``, ``reason_code``, ``asset_class``) and non-empty evidence, and every drop is reported
(``buy_pools``, ``avoided``, ``gaps``) instead of silently applied.

Rules inherited from `PROJECT.md` §7–§8 and enforced here:

* a proposal position has no ``SecurityId``, only an ``Isin``, and one ISIN can be several currency
  share classes (9 of the 12 duplicated ISINs in the master disagree on ``InRecommendationList``).
  A held line therefore uses the position's own ``SecurityId``; an ambiguous ISIN that is not held
  yields a field only when every master row agrees, and otherwise ``None`` plus a declared gap;
* weights are compared, **amounts are never converted** — a proposal amount stays in the proposal's
  own currency and a held amount in the portfolio currency;
* a candidate in an industry the client asked to avoid is excluded, and the exclusion is reported
  with the note that caused it: recommending a fossil name to `CASE-017` would contradict our own
  ``preference_conflict`` finding;
* a recommendation-list member is a **candidate to discuss**, never a suitability verdict — the rule
  engine's outputs are given, not reproducible (`PROJECT.md` §7.5).
"""

from __future__ import annotations

from typing import Any

from . import crm, index, metrics
from .ingest import intnum, listof, num, text
from .relevance import CASH_CATEGORY, DRIFT_THRESHOLD, PREFERENCE_KEYWORDS

# A draft proposal re-weights almost every line by a few basis points; only a move of at least one
# percentage point is a decision an advisor can act on. Measured over the five Entwurf proposals:
# 1 pp keeps 31 of 135 lines, and drops CASE-034's draft entirely (nothing in it moves by more than
# 0.6 pp), which is the honest answer for a proposal that only re-rounds.
MATERIAL_WEIGHT_DELTA = 0.01
# A line the proposal weights below this is not a position worth recommending.
MIN_TARGET_WEIGHT = 0.005
# Names offered per underweight asset class. The pools hold up to 147 rows, so every class reports
# how many names existed and how many are offered — the drop is disclosed, never hidden.
MAX_BUYS_PER_CLASS = 3

# ``relevance._open_proposal`` reads the same literal: a draft is open, Final and Abgelehnt are not.
OPEN_PROPOSAL_STATUS = "Entwurf"

BUY = "buy"
SELL = "sell"

# Stable reason codes. The renderer turns them into words; they are never shown raw to an advisor.
REASON_PROPOSAL_NEW = "proposal_new_position"
REASON_PROPOSAL_INCREASE = "proposal_increase"
REASON_PROPOSAL_DECREASE = "proposal_decrease"
REASON_PROPOSAL_EXIT = "proposal_exit"
REASON_UNDERWEIGHT_CLASS = "underweight_saa_class"

# Why the rows of one class are ordered the way they are — declared, because a ranking is a choice.
# Currency-group match first (the portfolio's own group), then the lower instrument volatility, then
# the name, so the result never depends on dict or file ordering.
RANKED_BY = ("currency_group_match", "volatility_ascending", "name")


def _evidence(label: str, value: Any, source: str, path: str, unit: str | None = None) -> dict:
    """One evidence entry, in the ``PROJECT.md`` §5.2 shape.

    ``relevance._evidence`` is the other producer of this shape (including the ``unit`` marker the
    evidence card needs to print a ratio as a percentage); the two must stay in sync.
    """
    return {"label": label, "value": value, "source": source, "path": path, "unit": unit}


def _classification(isin: str) -> tuple[int | None, str | None, str | None, bool | None, bool]:
    """Master-row facts for an ISIN: ``(security_id, asset_class, industry, in_list, ambiguous)``.

    A field is reported only when every master row of that ISIN agrees, so a currency share class is
    never answered for with its sibling's classification.
    """
    dataset = index.get()
    rows = dataset.securities_by_isin(isin)
    if not rows:
        return None, None, None, None, False
    if len(rows) == 1:
        row = rows[0]
        security_id = intnum(row, "Id", -1)
        return (security_id or None, text(row, "SAA_AssetClassName") or None,
                text(row, "SAA_IndustryName") or None,
                dataset.in_recommendation_list(security_id), False)

    classes = {text(row, "SAA_AssetClassName") for row in rows}
    industries = {text(row, "SAA_IndustryName") for row in rows}
    memberships = {bool(dataset.recommendation_lists(intnum(row, "Id", -1))) for row in rows}
    return (None,
            classes.pop() or None if len(classes) == 1 else None,
            industries.pop() or None if len(industries) == 1 else None,
            memberships.pop() if len(memberships) == 1 else None,
            True)


def _avoided_industries(client: dict) -> dict[str, tuple[str, str]]:
    """``industry -> (keyword, note path)`` the client asked to avoid, using R3's own keyword map."""
    avoided: dict[str, tuple[str, str]] = {}
    for note in crm.distinct_notes(client):
        lowered = str(note.get("text") or "").lower()
        for keyword, industries in PREFERENCE_KEYWORDS.items():
            if keyword not in lowered:
                continue
            for industry in industries:
                avoided.setdefault(industry, (keyword, str(note.get("path") or "")))
    return avoided


def _portfolio_rows(client: dict, portfolio_nr: str | None) -> list[dict]:
    portfolios = listof(client, "Portfolios")
    if portfolio_nr:
        portfolios = [p for p in portfolios if text(p, "PortfolioNr") == portfolio_nr]
    return portfolios


# ====================================================================================================
# Open proposals -> named moves
# ====================================================================================================

def _moves(client_ref: str, client: dict, portfolio_nr: str | None) -> tuple[list[dict], list[dict]]:
    """Named instruments an open proposal buys or sells, plus the gaps declared on the way."""
    rows: list[dict] = []
    gaps: list[dict] = []

    for proposal in listof(client, "Proposals"):
        if text(proposal, "ProposalStatusName") != OPEN_PROPOSAL_STATUS:
            continue
        proposal_id = intnum(proposal, "ProposalId", -1)
        portfolio_id = intnum(proposal, "PortfolioId", -1)
        portfolio = next((p for p in listof(client, "Portfolios")
                          if intnum(p, "PortfolioId", -1) == portfolio_id), None)
        if portfolio is None:
            # A dangling proposal reference is R3's ``missing_data`` finding, not a candidate.
            gaps.append({"code": "proposal_portfolio_unknown", "proposal_id": proposal_id,
                         "portfolio_id": portfolio_id})
            continue
        nr = text(portfolio, "PortfolioNr")
        if portfolio_nr and nr != portfolio_nr:
            continue

        status_path = f"clients[{client_ref}].Proposals[{proposal_id}].ProposalStatusName"
        held: dict[str, tuple[int, dict]] = {}
        for position_index, position in enumerate(listof(portfolio, "SecurityPositions")):
            isin = text(position, "Isin")
            if isin:
                held[isin] = (position_index, position)

        common = {
            "proposal_id": proposal_id,
            "proposal_status": text(proposal, "ProposalStatusName"),
            "proposal_reason": text(proposal, "Reason") or None,
            "proposal_date": text(proposal, "ProposedDateUTC") or None,
            "portfolio_id": portfolio_id,
            "portfolio_nr": nr,
        }

        proposed_isins: set[str] = set()
        for position_index, position in enumerate(listof(proposal, "SecurityPositions")):
            isin = text(position, "Isin")
            if not isin:
                continue
            proposed_isins.add(isin)
            target = num(position, "ProposalValuePercentage")
            if target < MIN_TARGET_WEIGHT:
                continue
            held_entry = held.get(isin)
            current = num(held_entry[1], "PortfolioValuePercentage") if held_entry else None
            delta = target - (current or 0.0)
            if current is None:
                direction, reason = BUY, REASON_PROPOSAL_NEW
            elif delta >= MATERIAL_WEIGHT_DELTA:
                direction, reason = BUY, REASON_PROPOSAL_INCREASE
            elif delta <= -MATERIAL_WEIGHT_DELTA:
                direction, reason = SELL, REASON_PROPOSAL_DECREASE
            else:
                continue  # an immaterial re-weight is not an action

            base = f"clients[{client_ref}].Proposals[{proposal_id}].SecurityPositions[{position_index}]"
            evidence = [
                _evidence("ProposalValuePercentage", target, "clients.json",
                          f"{base}.ProposalValuePercentage", unit="ratio"),
                _evidence("ProposalStatusName", common["proposal_status"], "clients.json", status_path),
            ]
            if held_entry:
                held_index, held_position = held_entry
                evidence.append(_evidence(
                    "PortfolioValuePercentage", current, "clients.json",
                    f"clients[{client_ref}].Portfolios[{nr}].SecurityPositions[{held_index}].PortfolioValuePercentage",
                    unit="ratio"))
                security_id = intnum(held_position, "SecurityId", -1) or None
            else:
                security_id = None

            amount = num(position, "TotalAmountInProposalCurrency") if "TotalAmountInProposalCurrency" in position else None
            if amount is not None:
                evidence.append(_evidence("TotalAmountInProposalCurrency", amount, "clients.json",
                                          f"{base}.TotalAmountInProposalCurrency"))

            rows.append(_row(
                client_ref=client_ref, direction=direction, reason_code=reason, isin=isin,
                name=text(position, "SecurityName"), security_id=security_id,
                current_weight=current, target_weight=target, delta=delta,
                amount=amount,
                amount_currency=text(position, "Currency") or text(proposal, "Currency") or None,
                evidence=evidence, gaps=gaps, **common,
            ))

        # Held today, absent from the target portfolio: the proposal exits the line.
        for isin, (position_index, position) in held.items():
            if isin in proposed_isins:
                continue
            current = num(position, "PortfolioValuePercentage")
            if current < MATERIAL_WEIGHT_DELTA:
                continue
            held_base = f"clients[{client_ref}].Portfolios[{nr}].SecurityPositions[{position_index}]"
            amount = (num(position, "TotalAmountInPortfolioCurrency")
                      if "TotalAmountInPortfolioCurrency" in position else None)
            evidence = [
                _evidence("PortfolioValuePercentage", current, "clients.json",
                          f"{held_base}.PortfolioValuePercentage", unit="ratio"),
                _evidence("Proposal target weight", 0.0, "computed",
                          f"ISIN {isin} is absent from clients[{client_ref}].Proposals[{proposal_id}].SecurityPositions",
                          unit="ratio"),
                _evidence("ProposalStatusName", common["proposal_status"], "clients.json", status_path),
            ]
            if amount is not None:
                evidence.append(_evidence("TotalAmountInPortfolioCurrency", amount, "clients.json",
                                          f"{held_base}.TotalAmountInPortfolioCurrency"))
            rows.append(_row(
                client_ref=client_ref, direction=SELL, reason_code=REASON_PROPOSAL_EXIT, isin=isin,
                name=text(position, "SecurityName"),
                security_id=intnum(position, "SecurityId", -1) or None,
                current_weight=current, target_weight=0.0, delta=-current,
                amount=amount,
                amount_currency=text(portfolio, "PortfolioCurrency") or None,
                evidence=evidence, gaps=gaps, **common,
            ))

    rows.sort(key=lambda row: (str(row["portfolio_nr"]), -abs(float(row["delta"] or 0.0)), str(row["isin"])))
    return rows, gaps


def _row(client_ref: str, direction: str, reason_code: str, isin: str, name: str,
         security_id: int | None, current_weight: float | None, target_weight: float | None,
         delta: float, amount: float | None, amount_currency: str | None, evidence: list[dict],
         gaps: list[dict], **common: Any) -> dict:
    """One named move, with its master-row facts resolved as far as the data honestly allows."""
    dataset = index.get()
    resolved_id, asset_class, industry, in_list, ambiguous = _classification(isin)
    if security_id is None:
        security_id = resolved_id
    elif asset_class is None or industry is None:
        # The held position's own SecurityId is the authoritative join (PROJECT.md §7.2).
        security = dataset.security(security_id) or {}
        asset_class = asset_class or text(security, "SAA_AssetClassName") or None
        industry = industry or text(security, "SAA_IndustryName") or None

    if security_id is not None and in_list is None:
        in_list = dataset.in_recommendation_list(security_id)
    if asset_class:
        evidence.append(_evidence("SAA_AssetClassName", asset_class, "computed",
                                  f"reference.Securities[Isin={isin}].SAA_AssetClassName"))
    if ambiguous:
        gaps.append({"code": "ambiguous_isin", "isin": isin, "client_ref": client_ref,
                     "portfolio_nr": common.get("portfolio_nr")})
    elif security_id is None:
        gaps.append({"code": "unresolved_isin", "isin": isin, "client_ref": client_ref,
                     "portfolio_nr": common.get("portfolio_nr")})

    return {
        "direction": direction,
        "reason_code": reason_code,
        "security_id": security_id,
        "isin": isin,
        "name": name or None,
        "asset_class": asset_class,
        "industry": industry,
        "in_recommendation_list": in_list,
        "current_weight": round(current_weight, 6) if current_weight is not None else None,
        "target_weight": round(target_weight, 6) if target_weight is not None else None,
        "delta": round(delta, 6),
        "amount": round(amount, 2) if amount is not None else None,
        "amount_currency": amount_currency,
        "evidence": evidence,
        **common,
    }


def proposal_moves(client_ref: str, portfolio_nr: str | None = None) -> list[dict]:
    """Instruments an open (``Entwurf``) proposal buys or sells, biggest move first.

    A buy and a sell inside the same ``asset_class`` of one proposal are what the brief calls a
    *switch*; grouping the two legs is a rendering decision, so both are reported separately here.
    """
    dataset = index.get()
    client = dataset.client(client_ref)
    if not client:
        return []
    return _moves(client_ref, client, portfolio_nr)[0]


# ====================================================================================================
# Underweight asset class -> named candidates from the bank's own list
# ====================================================================================================

def _buys(client_ref: str, client: dict, portfolio_nr: str | None) -> dict:
    """Recommendation-list names for every asset class below its SAA target, plus the disclosures."""
    dataset = index.get()
    avoided = _avoided_industries(client)
    list_ids = {text(row, "Name"): intnum(row, "Id", -1) for row in dataset.all_recommendation_lists}
    rows: list[dict] = []
    pools: list[dict] = []
    excluded: list[dict] = []
    gaps: list[dict] = []

    for portfolio in _portfolio_rows(client, portfolio_nr):
        nr = text(portfolio, "PortfolioNr")
        portfolio_id = intnum(portfolio, "PortfolioId", -1)
        deviation = metrics.saa_deviation(portfolio)
        if not deviation["available"]:
            # SAA 96 carries no usable targets; R3 reports the missing strategy, and we simply have
            # no target to buy toward.
            gaps.append({"code": "saa_unavailable", "client_ref": client_ref, "portfolio_nr": nr})
            continue

        held_isins = {text(position, "Isin") for position in listof(portfolio, "SecurityPositions")}
        portfolio_group = dataset.currency_group(text(portfolio, "PortfolioCurrency"))

        for target_row in deviation["rows"]:
            category = target_row["category"]
            difference = target_row["difference"]
            # Cash is ``reinvestment``'s business, and only a class *below* target needs a new name.
            if category == CASH_CATEGORY or difference > -DRIFT_THRESHOLD:
                continue

            pool = [security for security in dataset.recommendation_pool(category)
                    if text(security, "Isin") not in held_isins]
            offered = []
            for security in pool:
                industry = text(security, "SAA_IndustryName")
                if industry in avoided:
                    keyword, note_path = avoided[industry]
                    excluded.append({"security_id": intnum(security, "Id", -1),
                                     "name": text(security, "Name"), "industry": industry,
                                     "keyword": keyword, "note_path": note_path,
                                     "asset_class": category, "portfolio_nr": nr})
                else:
                    offered.append(security)
            offered.sort(key=lambda security: (
                0 if dataset.currency_group(text(security, "Currency")) == portfolio_group else 1,
                1 if security.get("Volatility") is None else 0,
                num(security, "Volatility"),
                text(security, "Name"),
            ))

            pools.append({
                "portfolio_id": portfolio_id,
                "portfolio_nr": nr,
                "category": category,
                "target_weight": target_row["target"],
                "actual_weight": target_row["actual"],
                "difference": difference,
                "pool_size": len(pool),
                "offered": min(len(offered), MAX_BUYS_PER_CLASS),
                "excluded_by_preference": sum(1 for row in excluded
                                              if row["portfolio_nr"] == nr and row["asset_class"] == category),
                "ranked_by": list(RANKED_BY),
            })
            if not offered:
                gaps.append({"code": "no_list_member_for_class", "client_ref": client_ref,
                             "portfolio_nr": nr, "category": category})

            for rank, security in enumerate(offered[:MAX_BUYS_PER_CLASS], start=1):
                security_id = intnum(security, "Id", -1)
                lists = dataset.recommendation_lists(security_id)
                master = f"reference.Securities[Id={security_id}]"
                volatility = num(security, "Volatility") if "Volatility" in security else None
                rows.append({
                    "direction": BUY,
                    "reason_code": REASON_UNDERWEIGHT_CLASS,
                    "security_id": security_id,
                    "isin": text(security, "Isin") or None,
                    "name": text(security, "Name") or None,
                    "asset_class": text(security, "SAA_AssetClassName") or None,
                    "industry": text(security, "SAA_IndustryName") or None,
                    "country_group": text(security, "SAA_CountryGroupName") or None,
                    "currency": text(security, "Currency") or None,
                    "currency_group": dataset.currency_group(text(security, "Currency")),
                    "volatility": volatility,
                    "prc": num(security, "PRC") if "PRC" in security else None,
                    "sustainability_score": num(security, "SustainabilityScore") if "SustainabilityScore" in security else None,
                    "recommendation_lists": lists,
                    "target_category": category,
                    "target_weight": target_row["target"],
                    "actual_weight": target_row["actual"],
                    "difference": difference,
                    "rank": rank,
                    "ranked_by": list(RANKED_BY),
                    "proposal_id": None,
                    "proposal_status": None,
                    "proposal_reason": None,
                    "proposal_date": None,
                    "portfolio_id": portfolio_id,
                    "portfolio_nr": nr,
                    "evidence": [
                        _evidence(f"{category} target", target_row["target"], "computed",
                                  "reference.StrategicAssetAllocations[joined via StrategicAssetAllocationId]"
                                  f".Mappings[{category}].TargetPercentage", unit="ratio"),
                        _evidence(f"{category} actual", target_row["actual"], "computed",
                                  f"aggregated from clients[{client_ref}].Portfolios[{nr}].SecurityPositions",
                                  unit="ratio"),
                        _evidence("Recommendation list", ", ".join(lists), "computed",
                                  f"reference.RecommendationLists[Id={list_ids.get(lists[0], -1)}]"
                                  f".Securities[SecurityId={security_id}]"),
                        _evidence("SAA_AssetClassName", text(security, "SAA_AssetClassName"), "computed",
                                  f"{master}.SAA_AssetClassName"),
                        _evidence("Volatility", volatility, "computed", f"{master}.Volatility", unit="ratio"),
                    ],
                })
    return {"rows": rows, "pools": pools, "excluded": excluded, "gaps": gaps}


# ====================================================================================================
# Entry point
# ====================================================================================================

def candidates(client_ref: str, portfolio_nr: str | None = None) -> dict:
    """Every nameable instrument for one client (optionally one portfolio), as data.

    ``moves`` are the instruments an open proposal buys or sells; ``buys`` are recommendation-list
    members for an asset class below its SAA target. ``buy_pools`` discloses how many names existed
    per class and how many are offered, ``excluded`` names every candidate a client preference ruled
    out (with the note that did it), and ``gaps`` carries what could not be determined.
    """
    dataset = index.get()
    client = dataset.client(client_ref)
    if not client:
        return {"scope": {"client_ref": client_ref, "portfolio_nr": portfolio_nr},
                "moves": [], "buys": [], "buy_pools": [], "excluded": [], "gaps": []}

    moves, move_gaps = _moves(client_ref, client, portfolio_nr)
    buys = _buys(client_ref, client, portfolio_nr)
    return {
        "scope": {"client_ref": client_ref, "portfolio_nr": portfolio_nr},
        "moves": moves,
        "buys": buys["rows"],
        "buy_pools": buys["pools"],
        "excluded": buys["excluded"],
        "gaps": buys["gaps"] + move_gaps,
    }
