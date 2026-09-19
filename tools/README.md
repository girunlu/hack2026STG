# UNRISKOMEGA Rehearsal Kit

Deterministic drill kit for rehearsing the unseen-client presentation scenario.

## Quick Start (< 1 minute)

```bash
# Run the full rehearsal drill
python tools/drill.py
```

This will:
1. Start an isolated backend on port 8001 (hub name: `api-drill`)
2. Generate 5 synthetic clients with different archetypes
3. Upload and brief each client
4. Validate the briefings against invariants
5. Run the negative test matrix (REVIEW §13.1)
6. Print a PASS/FAIL table
7. Clean up and stop the server

**The live demo on ports 8000/5173 is never touched.**

## Archetypes

The kit generates clients with these archetypes to exercise different code paths:

| Archetype | What it demonstrates |
|---|---|
| `balanced` | Normal diversified portfolio (3 securities + cash) |
| `concentrated` | Single-stock concentration (95% in one position) |
| `cash_heavy` | High liquidity (60% cash, 40% securities) |
| `foreign_currency_heavy` | FX exposure (70% USD/EUR, 30% CHF) |
| `broken` | Graceful refusal: unresolvable `SecurityId` 999999 + null `RiskProfileId` |

Additional archetypes available via `synth_client.py --help`:
- `fund_only` — all positions are investment funds
- `draft_proposal` — has `Entwurf` (draft) proposals
- `no_risk_profile` — missing `RiskProfileId`
- `dirty_dangling_refs` — violations/proposals pointing at non-existent portfolio IDs

## Determinism

The generator is **fully deterministic**: the same seed produces byte-identical output.

```bash
# Generate 3 balanced clients with seed 42
python tools/synth_client.py --seed 42 --archetype balanced --count 3 --output test.json

# Same command → identical file
python tools/synth_client.py --seed 42 --archetype balanced --count 3 --output test.json
```

## Invariants Reproduced

Every generated client satisfies the verified invariants from REVIEW §8.3:

1. **58 monthly `PerformanceHistory` points** (2021-10-01 to 2026-07-01), last value = `AssetsUnderManagementInDefaultCurrency`
2. **SecurityPositions + AccountPositions weights sum to 1.0** (±0.01)
3. **`TotalAmountInPortfolioCurrency = weight × AUM`**
4. **`SecurityId`s drawn from the REAL master universe** in `reference.json` (so prices, volatility, industry and SAA classification resolve)
5. **`SuitabilityViolations` always carry `ViolationPath[]`** with `LeftValue`/`RightValue`/`Operator`
6. **Proposals have `ProposalStatusName` in {Final, Abgelehnt, Entwurf}** with their own `SecurityPositions` carrying `Isin`/`SecurityName`/`ProposalValuePercentage`/`TotalAmountInProposalCurrency`/`Quantity`/`PricePerUnit`
7. **Notes drawn from the 53 real note texts** in `clients.json`
8. **Tags from the real 19-item vocabulary** in `reference.json`

## Honest Caveat

A generated client whose securities are **absent from the trimmed `reference.json`** loses price/volatility/industry/SAA/news for those lines. The app declares them unresolved rather than inventing data — that is the same graceful-refusal behaviour `DRILL-102` shows.

**Full fidelity for a brand-new instrument would need a reference intake endpoint** (`POST /api/dataset/reference`) that does not exist today (REVIEW §5.3 Option B, currently out of frame).

## File Layout

```
tools/
├── synth_client.py    # Deterministic client generator
├── drill.py           # Full rehearsal drill (isolated backend)
└── README.md          # This file
```

## Negative Test Matrix

The drill runs every test from REVIEW §13.1:

| Input | Expected |
|---|---|
| Empty array `[]` | 400 |
| Malformed JSON | 400 |
| Duplicate `ClientRef` | 409 with `clashing_refs` |
| Single object (not array) | 200 (accepted) |
| Wrapped `{"Clients":[…]}` | 200 (accepted) |
| Client with no portfolios | 200 with declared gaps |

## What the Drill Validates

For each generated client, the drill checks:

1. **Upload succeeds** (200, `clients_added` reported)
2. **Briefing succeeds** (200)
3. **Three sections** in the brief's order
4. **≥1 traceable block per section** (every `evidence_refs` entry resolvable in `evidence_index`)
5. **≥1 declared `meta.unavailable`** (honest about gaps)
6. **Word count inside 120–260 band**

## Isolated Backend

The drill starts its own uvicorn on **port 8001** (never 8000) with:
- Hub process name: `api-drill`
- `URO_DATA_DIR`, `URO_UPLOAD_DIR`, `URO_EXCUSTODY_DIR`, `URO_NEWS_CACHE_DIR` → temp dirs
- `URO_NEWS_OFFLINE=1` (no live news fetches)
- Copies of `reference.json` and `clients.json` in the temp data dir

The live demo state (ports 8000/5173, `data/uploads/`, `data/excustody/`) is **never touched**.

## After the Drill

Verify the live demo is untouched:

```bash
# Should report 48 clients / 58 portfolios (the baseline with SCEN-001 loaded)
curl http://127.0.0.1:8000/api/health

# Should contain only scen-001.json
ls data/uploads/

# Should be empty
ls data/excustody/
```
