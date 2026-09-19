"""Investigate defects A and B in relevance.py"""
import json
import sys
from pathlib import Path

# Load data
data_dir = Path("D:/hack26/unriskomega-2026/core-case/portfolio-data")
with open(data_dir / "clients.json") as f:
    clients = json.load(f)

# Build client lookup
client_map = {c["ClientRef"]: c for c in clients}

# Defect A: Check the 8 portfolios mentioned
print("=" * 80)
print("DEFECT A: Broken evidence paths")
print("=" * 80)

problem_portfolios = [
    "CASE-001-01", "CASE-006-02", "CASE-006-03", "CASE-014-01",
    "CASE-021-02", "CASE-025-01", "CASE-036-02", "CASE-046-01"
]

for client_ref, client in client_map.items():
    for portfolio in client.get("Portfolios", []):
        portfolio_nr = portfolio.get("PortfolioNr")
        if portfolio_nr in problem_portfolios:
            print(f"\n{client_ref} / {portfolio_nr}:")
            print(f"  Has SecurityPositions key: {'SecurityPositions' in portfolio}")
            if "SecurityPositions" in portfolio:
                print(f"  SecurityPositions type: {type(portfolio['SecurityPositions'])}")
                if isinstance(portfolio["SecurityPositions"], list):
                    print(f"  SecurityPositions length: {len(portfolio['SecurityPositions'])}")
            else:
                print(f"  Portfolio keys: {list(portfolio.keys())}")
                # Check if there's an aggregate value
                if "AccountPositions" in portfolio:
                    accounts = portfolio["AccountPositions"]
                    print(f"  AccountPositions: {len(accounts)} accounts")
                    if accounts:
                        total = sum(a.get("TotalAmountInPortfolioCurrency", 0) for a in accounts)
                        print(f"  Sum of AccountPositions TotalAmountInPortfolioCurrency: {total}")

# Defect B: Check the 5 draft proposal clients
print("\n" + "=" * 80)
print("DEFECT B: Draft proposals (Entwurf)")
print("=" * 80)

draft_clients = ["CASE-017", "CASE-034", "CASE-037", "CASE-042", "CASE-045"]

for client_ref in draft_clients:
    client = client_map.get(client_ref)
    if not client:
        print(f"\n{client_ref}: NOT FOUND")
        continue
    
    proposals = client.get("Proposals", [])
    draft_proposals = [p for p in proposals if p.get("ProposalStatusName") == "Entwurf"]
    
    print(f"\n{client_ref}:")
    print(f"  Total proposals: {len(proposals)}")
    print(f"  Draft (Entwurf) proposals: {len(draft_proposals)}")
    
    for p in draft_proposals:
        print(f"    - ProposalId: {p.get('ProposalId')}")
        print(f"      AdvisoryTypeName: {p.get('AdvisoryTypeName')}")
        print(f"      ProposedDateUTC: {p.get('ProposedDateUTC')}")
        print(f"      Reason: {p.get('Reason', '')[:50]}")
        print(f"      SecurityPositions: {len(p.get('SecurityPositions', []))} positions")

print("\n" + "=" * 80)
print("Checking PerformanceHistory structure for stale_data defect")
print("=" * 80)

# Check a client with stale data
sample_client = client_map.get("CASE-001")
if sample_client:
    for portfolio in sample_client.get("Portfolios", []):
        perf_history = portfolio.get("PerformanceHistory", [])
        if perf_history:
            print(f"\n{portfolio.get('PortfolioNr')}:")
            print(f"  PerformanceHistory length: {len(perf_history)}")
            print(f"  Last point: {perf_history[-1] if perf_history else 'None'}")
            print(f"  Second-to-last: {perf_history[-2] if len(perf_history) > 1 else 'None'}")
            break
