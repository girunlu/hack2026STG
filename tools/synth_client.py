#!/usr/bin/env python3
"""
Deterministic synthetic client generator for the UNRISKOMEGA drill kit.

Generates clients in the exact `clients.json` shape, reproducing verified invariants:
- 58 monthly PerformanceHistory points (2021-10-01 to 2026-07-01), last value = AUM
- SecurityPositions + AccountPositions weights sum to 1.0 (±0.01)
- TotalAmountInPortfolioCurrency = weight × AUM
- SecurityIds drawn from the REAL master universe in reference.json
- SuitabilityViolations with ViolationPath[] (LeftValue/RightValue/Operator)
- Proposals with ProposalStatusName in {Final, Abgelehnt, Entwurf}
- Notes from the 53 real note texts
- Tags from the 19-item vocabulary

Supports archetypes:
- concentrated: single-stock concentration (e.g., 95% in one position)
- fund_only: all positions are investment funds
- cash_heavy: >50% in cash/account positions
- draft_proposal: has Entwurf (draft) proposals
- no_risk_profile: missing RiskProfileId
- dirty_dangling_refs: violations/proposals pointing at non-existent portfolio IDs
- foreign_currency_heavy: >50% in non-CHF positions
- broken: unresolvable SecurityId + null RiskProfileId (proves graceful refusal)

Usage:
    python tools/synth_client.py --help
    python tools/synth_client.py --seed 42 --archetype concentrated --output drill-clients.json
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PATH = REPO_ROOT / "unriskomega-2026" / "core-case" / "portfolio-data" / "reference.json"
CLIENTS_PATH = REPO_ROOT / "unriskomega-2026" / "core-case" / "portfolio-data" / "clients.json"


def load_reference() -> dict:
    with REFERENCE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def load_real_notes() -> list[str]:
    with CLIENTS_PATH.open(encoding="utf-8") as f:
        clients = json.load(f)
    notes = set()
    for client in clients:
        for note in client.get("ClientNotes", []):
            text = note.get("Note")
            if text:
                notes.add(text)
    return sorted(notes)


def generate_guid(rng: random.Random) -> str:
    hex_chars = "0123456789ABCDEF"
    parts = [
        "".join(rng.choice(hex_chars) for _ in range(8)),
        "".join(rng.choice(hex_chars) for _ in range(4)),
        "".join(rng.choice(hex_chars) for _ in range(4)),
        "".join(rng.choice(hex_chars) for _ in range(4)),
        "".join(rng.choice(hex_chars) for _ in range(12)),
    ]
    return "-".join(parts)


def generate_performance_history(
    rng: random.Random, aum: float, start_date: str = "2021-10-01", months: int = 58
) -> list[dict]:
    """Generate 58 monthly performance points, last value = AUM."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    values = []
    current = aum * rng.uniform(0.6, 0.8)
    for i in range(months):
        if i == months - 1:
            values.append({"Date": start.strftime("%Y-%m-%d"), "Value": round(aum, 2)})
        else:
            values.append({"Date": start.strftime("%Y-%m-%d"), "Value": round(current, 2)})
            change = rng.uniform(-0.05, 0.08)
            current = max(current * (1 + change), aum * 0.3)
        if start.month == 12:
            start = start.replace(year=start.year + 1, month=1)
        else:
            start = start.replace(month=start.month + 1)
    return values


def sec_field(sec: dict, key: str, default):
    """Defensive access — reference.json omits null fields."""
    v = sec.get(key)
    return v if v is not None else default


def make_security_position(rng, sec, aum, weight):
    price = max(sec_field(sec, "EndOfDayPrice", 1.0), 0.01)
    qty = aum * weight / price
    return {
        "SecurityId": sec["Id"],
        "Isin": sec_field(sec, "Isin", ""),
        "Valor": sec_field(sec, "Valor", ""),
        "SecurityName": sec_field(sec, "Name", "Unknown"),
        "Quantity": round(qty, 4),
        "PricePerUnit": price,
        "Currency": sec_field(sec, "Currency", "CHF"),
        "TotalAmountInPortfolioCurrency": round(aum * weight, 2),
        "PortfolioValuePercentage": round(weight, 6),
        "MarginalContributionToRisk": round(rng.uniform(0.05, 0.2), 6),
        "ContributionVolatility": round(rng.uniform(0.02, 0.1), 6),
    }


def make_account(name, currency, aum, weight):
    return {
        "AccountName": name,
        "Currency": currency,
        "TotalAmountInPortfolioCurrency": round(aum * weight, 2),
        "PortfolioValuePercentage": round(weight, 6),
        "MarginalContributionToRisk": 0.0,
        "ContributionVolatility": 0.0,
    }


def generate_positions(rng, securities, aum, archetype):
    positions = []
    accounts = []

    if archetype == "concentrated":
        sec = rng.choice(securities)
        positions.append(make_security_position(rng, sec, aum, 0.95))
        accounts.append(make_account("Cash Account CHF", "CHF", aum, 0.05))

    elif archetype == "fund_only":
        funds = [s for s in securities if "fund" in sec_field(s, "SecurityTypeName", "").lower()]
        if not funds:
            funds = securities[:5]
        weights = [0.3, 0.25, 0.2, 0.15, 0.1]
        for sec, w in zip(funds[:5], weights):
            positions.append(make_security_position(rng, sec, aum, w))

    elif archetype == "cash_heavy":
        sec = rng.choice(securities)
        positions.append(make_security_position(rng, sec, aum, 0.4))
        accounts.append(make_account("Savings Account CHF", "CHF", aum, 0.6))

    elif archetype == "foreign_currency_heavy":
        foreign = [s for s in securities if sec_field(s, "Currency", "") in ("USD", "EUR")]
        chf = [s for s in securities if sec_field(s, "Currency", "") == "CHF"]
        if not foreign:
            foreign = securities[:2]
        if not chf:
            chf = securities[-2:]
        positions.append(make_security_position(rng, foreign[0], aum, 0.35))
        positions.append(make_security_position(rng, foreign[1 % len(foreign)], aum, 0.35))
        positions.append(make_security_position(rng, chf[0], aum, 0.3))

    else:  # balanced
        selected = rng.sample(securities, min(3, len(securities)))
        weights = [0.4, 0.35, 0.2]
        for sec, w in zip(selected, weights):
            positions.append(make_security_position(rng, sec, aum, w))
        accounts.append(make_account("Cash Account CHF", "CHF", aum, 0.05))

    return positions, accounts


def generate_violations(rng, portfolio_id, suitability_rules, archetype):
    if archetype == "broken":
        return []
    violations = []
    num = rng.randint(1, 3)
    for rule in rng.sample(suitability_rules, min(num, len(suitability_rules))):
        left = rng.uniform(0.1, 0.25)
        right = rng.uniform(0.05, 0.15)
        violations.append({
            "Id": rng.randint(100000, 999999),
            "RuleCode": rule["RuleCode"],
            "RuleDescription": rule["Description"],
            "ErrorLevel": rng.choice([0, 1, 2]),
            "Severity": rng.choice(["Warning", "Error"]),
            "PortfolioId": portfolio_id,
            "LastViolatedDateUTC": "2026-08-15T10:30:00Z",
            "ViolationPath": [
                {
                    "FieldName": "SimulationVolatilityRuleField`1",
                    "LeftValue": round(left, 6),
                    "RightValue": round(right, 6),
                    "Operator": rng.choice([10, 20, 30, 40, 50, 60]),
                }
            ],
        })
    return violations


def generate_proposals(rng, portfolio_id, securities, proposal_statuses, advisory_types, archetype):
    if archetype == "broken":
        return []
    proposals = []
    for _ in range(rng.randint(1, 3)):
        status = rng.choice(proposal_statuses)
        advisory = rng.choice(advisory_types)
        sec = rng.choice(securities)
        weight = rng.uniform(0.05, 0.25)
        price = max(sec_field(sec, "EndOfDayPrice", 1.0), 0.01)
        proposal = {
            "ProposalId": rng.randint(100000, 999999),
            "PublicGuid": generate_guid(rng),
            "PortfolioId": portfolio_id,
            "ProposalStatusId": status["Id"],
            "ProposalStatusName": status["Name"],
            "AdvisoryTypeId": advisory["Id"],
            "AdvisoryTypeName": advisory["Name"],
            "Currency": "CHF",
            "StrategicAssetAllocationId": rng.randint(90, 105),
            "ProposedDateUTC": "2026-08-10T14:00:00Z",
            "Reason": rng.choice([
                "Follow-up from prior meeting",
                "Change of risk tolerance",
                "Market rebalancing",
            ]),
            "ExpectedReturn": round(rng.uniform(0.03, 0.08), 6),
            "Volatility": round(rng.uniform(0.08, 0.18), 6),
            "ValueAtRisk": round(rng.uniform(0.05, 0.15), 6),
            "SecurityPositions": [
                {
                    "Isin": sec_field(sec, "Isin", ""),
                    "SecurityName": sec_field(sec, "Name", "Unknown"),
                    "Quantity": round(rng.uniform(10, 100), 2),
                    "PricePerUnit": price,
                    "Currency": sec_field(sec, "Currency", "CHF"),
                    "TotalAmountInProposalCurrency": round(rng.uniform(5000, 50000), 2),
                    "ProposalValuePercentage": round(weight, 6),
                }
            ],
            "AccountPositions": [],
            "Contracts": [],
            "StandingOrders": [],
        }
        if status["Name"] == "Final":
            proposal["FinalizedDateUTC"] = "2026-08-12T16:00:00Z"
        proposals.append(proposal)
    return proposals


def generate_client(rng, client_ref, reference, real_notes, archetype):
    securities = reference["Securities"]
    suitability_rules = reference["SuitabilityRules"]
    risk_profiles = reference["RiskProfiles"]
    proposal_statuses = reference["ProposalStatuses"]
    advisory_types = reference["AdvisoryTypes"]
    tags = reference["Tags"]

    aum = rng.uniform(500000, 2000000)
    risk_profile = rng.choice(risk_profiles) if archetype not in ("no_risk_profile", "broken") else None

    client = {
        "ClientId": rng.randint(1000, 9999),
        "ClientRef": client_ref,
        "FirstName": rng.choice(["Anna", "Beat", "Clara", "David", "Eva"]),
        "LastName": rng.choice(["Müller", "Meier", "Schmid", "Keller", "Weber"]),
        "IsClientACompany": False,
        "IsEmployee": False,
        "RegulatoryClientTypeId": 13,
        "RegulatoryClientTypeName": "Private client",
        "ReportingCurrency": "CHF",
        "Birthday": f"{rng.randint(1950, 1990)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        "ProfilingDateUtc": "2026-01-15T09:00:00Z",
        "AssetsUnderManagementInDefaultCurrency": round(aum, 2),
        "LiquidityInDefaultCurrency": round(aum * rng.uniform(0.95, 1.0), 2),
    }
    if risk_profile:
        client["RiskProfileId"] = risk_profile["Id"]
        client["RiskProfileName"] = risk_profile["Name"]
    if rng.random() > 0.3:
        client["EsgProfileId"] = rng.choice([1, 2])
        client["EsgProfileName"] = "Yes" if client["EsgProfileId"] == 1 else "No"

    portfolio_id = rng.randint(10000, 99999)
    positions, accounts = generate_positions(rng, securities, aum, archetype)

    if archetype == "broken":
        # Inject unresolvable SecurityId
        positions[0]["SecurityId"] = 999999
        positions[0]["Isin"] = "XX0000000000"
        positions[0]["SecurityName"] = "Unknown Security"

    portfolio = {
        "PortfolioId": portfolio_id,
        "PublicGuid": generate_guid(rng),
        "PortfolioNr": f"{client_ref}-01",
        "Name": rng.choice(["Depot A", "Vorsorge Indiv", "Anlageportfolio"]),
        "PortfolioCurrency": "CHF",
        "StrategicAssetAllocationId": rng.randint(90, 105),
        "InvestmentServiceId": 12,
        "InvestmentServiceName": "Individual Pension - Depository Advisory",
        "StrategyId": 5,
        "StrategyName": "Investor profile 5",
        "ReferenceCurrency": "CHF",
        "AssetsUnderManagementInDefaultCurrency": round(aum, 2),
        "LiquidityInDefaultCurrency": round(aum * rng.uniform(0.95, 1.0), 2),
        "Volatility": round(rng.uniform(0.08, 0.18), 6),
        "ExpectedReturn": round(rng.uniform(0.03, 0.08), 6),
        "ValueAtRisk": round(rng.uniform(0.05, 0.15), 6),
        "FactoryDateUtc": "2026-09-03T11:15:26.1149572Z",
        "SecurityPositions": positions,
        "AccountPositions": accounts,
        "PerformanceHistory": generate_performance_history(rng, aum),
    }
    client["Portfolios"] = [portfolio]

    violations = generate_violations(rng, portfolio_id, suitability_rules, archetype)
    if archetype == "dirty_dangling_refs":
        violations.append({
            "Id": rng.randint(100000, 999999),
            "RuleCode": rng.choice(suitability_rules)["RuleCode"],
            "RuleDescription": "Dangling reference test",
            "ErrorLevel": 1,
            "Severity": "Warning",
            "PortfolioId": 99999,
            "LastViolatedDateUTC": "2026-08-15T10:30:00Z",
            "ViolationPath": [
                {
                    "FieldName": "SimulationFilterTopLevelSAAAssetClassRuleField",
                    "LeftValue": 0.5,
                    "RightValue": 0.3,
                    "Operator": 30,
                }
            ],
        })
    client["SuitabilityViolations"] = violations

    proposals = generate_proposals(rng, portfolio_id, securities, proposal_statuses, advisory_types, archetype)
    if archetype == "dirty_dangling_refs":
        proposals.append({
            "ProposalId": rng.randint(100000, 999999),
            "PublicGuid": generate_guid(rng),
            "PortfolioId": 99999,
            "ProposalStatusId": 3,
            "ProposalStatusName": "Final",
            "AdvisoryTypeId": 2,
            "AdvisoryTypeName": "Investment proposal",
            "Currency": "CHF",
            "StrategicAssetAllocationId": 95,
            "ProposedDateUTC": "2026-08-10T14:00:00Z",
            "Reason": "Dangling proposal test",
            "ExpectedReturn": 0.05,
            "Volatility": 0.12,
            "ValueAtRisk": 0.08,
            "SecurityPositions": [],
            "AccountPositions": [],
            "Contracts": [],
            "StandingOrders": [],
        })
    client["Proposals"] = proposals
    client["Transactions"] = []
    client["IndividualRuleOverrides"] = []

    num_tags = rng.randint(1, 3)
    client["Tags"] = [
        {"TagName": t["Name"], "TagTypeName": t["TagTypeName"], "Scope": "Client"}
        for t in rng.sample(tags, num_tags)
    ]

    num_notes = rng.randint(1, 2)
    client["ClientNotes"] = [
        {"Note": note, "CreatedByDateUTC": "2026-01-10T14:30:00Z"}
        for note in rng.sample(real_notes, num_notes)
    ]

    return client


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic clients for UNRISKOMEGA drill")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism (default: 42)")
    parser.add_argument("--archetype", type=str, default="balanced",
                        choices=["balanced", "concentrated", "fund_only", "cash_heavy",
                                 "no_risk_profile", "dirty_dangling_refs", "foreign_currency_heavy", "broken"],
                        help="Client archetype (default: balanced)")
    parser.add_argument("--count", type=int, default=1, help="Number of clients to generate (default: 1)")
    parser.add_argument("--output", type=str, required=True, help="Output JSON file path")
    parser.add_argument("--prefix", type=str, default="DRILL", help="ClientRef prefix (default: DRILL)")
    args = parser.parse_args()

    reference = load_reference()
    real_notes = load_real_notes()
    rng = random.Random(args.seed)

    clients = []
    for i in range(args.count):
        client_ref = f"{args.prefix}-{i+1:03d}"
        client = generate_client(rng, client_ref, reference, real_notes, args.archetype)
        clients.append(client)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(clients, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(clients)} client(s) with archetype '{args.archetype}' → {output_path}")
    print(f"Seed: {args.seed} (deterministic)")


if __name__ == "__main__":
    main()
