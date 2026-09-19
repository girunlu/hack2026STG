# F5 — Data access layer

**Layer:** Frame (exists at URO as its database/API) · **Intelligence:** none · **Wave:** 0
**Depends on:** — (nothing)
**Consumed by:** `F2`, `F3`, `F4`, `F6`, `R2`, `R3`, `B1`, `T1`

## Purpose

The single place that touches raw JSON. It loads the two provided files, normalises the data, builds
every join, and exposes derived metrics. No other component may parse JSON or index into it directly.

This is **wave 0**. Nothing else should be built before it, because it freezes the contracts.

## Inputs

- `unriskomega-2026/core-case/portfolio-data/clients.json` — 47 clients
- `unriskomega-2026/core-case/portfolio-data/reference.json` — 12 collections
- Later: portfolios ingested by `B1` (ex-custody), added to the same runtime store

## Outputs — the contract

Python API in `backend/app/domain/`:

```python
# ingest.py — normalisation helpers, used everywhere
opt(obj, key)        # value or None; missing and null treated identically
listof(obj, key)     # list; missing / null / wrong type -> []
num(obj, key, d=0.0) # float, never None
intnum(obj, key, d=0) # int, never None
text(obj, key, d="") # str, never None
flag(obj, key, d=False) # bool, never None
day(value)           # ISO date or timestamp -> YYYY-MM-DD, else None
as_date(value)       # ISO date or timestamp -> datetime.date, else None
redact(obj)          # recursively drop IBAN-bearing keys

# index.py — joins
load()                        # -> Dataset (once, at startup)
ds.clients                    # list of client dicts (normalised)
ds.client(ref)                # by ClientRef, e.g. "CASE-007"
ds.security(security_id)      # -> dict | None
ds.securities_by_isin(isin)   # -> list[dict]; every master row with this ISIN in file order ([] when unknown)
ds.security_by_isin(isin)     # -> dict | None; first row in file order (index-backed)
ds.saa(id) / ds.risk_profile(id) / ds.rule(rule_code)
ds.portfolio(client_ref, portfolio_nr)
ds.portfolios_of(client_ref)  # -> list[dict]; all portfolios for a client
ds.portfolio_ids_of(client_ref) # -> set[int]; portfolio ids for integrity checks
ds.portfolio_by_id(portfolio_id) # -> dict | None; lookup by id
ds.fund_mappings(security_id) # -> list[dict]; look-through rows for a fund
ds.recommendation_lists(security_id) # -> list[str]; names of lists the security belongs to
ds.in_recommendation_list(security_id) # -> bool; whether the security is a member of any list
ds.recommendation_pool(saa_asset_class) # -> list[dict]; recommendation-list members in that SAA class
ds.currency_group(currency)   # -> str; currency group (CHF/EUR/USD mapped; others → "Andere")
ds.data_as_of()               # -> str | None; newest date in the data
ds.integrity_report()         # dangling refs + missing profiles, as data not exceptions

# metrics.py — derived values
returns(portfolio)            # {"return_12m_pct": float|None, "return_3m_pct": float|None, ...}
concentration(portfolio)      # {"top_weight": 0.959, "top_security": "...", "hhi": 0.92}
fx_exposure(portfolio)        # {"USD": 0.822, ...} by position currency
saa_deviation(portfolio)      # per dimension; returns [] when the SAA has no rows for it
lookthrough(security_id)      # fund breakdown aggregated by dimension (Weights are 0-100 -> /100)
risk_contributions(portfolio) # {"available", "reason", "volatility", "sum", "rows", "dropped"}
                              # rows are cleaned: a contribution that cannot be true (one int64
                              # overflow in the case data) lands in `dropped` with its reason, and
                              # `available` is False when the series is simply not populated
exposures(portfolio, lang)    # rows carry a stable `category` key plus a localised `label`
maturity_buckets(portfolio, as_of, lang)   # same: stable bucket keys, localised labels
```

## Measured facts (as built, 2026-09-19)

- **48 clients / 58 portfolios** (47 shipped + `SCEN-001` demo client from `data/uploads/scen-001.json`)
- **504 securities**, **275 held ISINs**, **48'101 fund mappings**, **703 positions**
- **180 suitability violations** (display-only, never recomputed — `PROJECT.md` §7 rule 5)
- **206 proposals**: 125 `Final` / 76 `Abgelehnt` / 5 `Entwurf`
- **153 notes** (53 distinct texts globally; zero clients repeat a text internally)
- **19-tag vocabulary**: 8 regions + 11 industries
- **54 rule rows / 53 distinct codes**
- **5 risk profiles**, **16 SAAs** (SAA 96 has no usable targets → `CASE-038-01` "Keine Strategie")
- **1 recommendation list**: Id 9, "Recommendation list free assets", **232 members**; 403 rows carry the looser `Securities[].InRecommendationList` flag (12 duplicated ISINs, of which 9 disagree on the flag — membership is the stricter source)
- **4 clients without a risk profile** (`CASE-029`–`CASE-032`)
- **28 dangling portfolio refs** (`CASE-008` 13, `CASE-038` 15)
- `data_as_of` **2026-09-03** (performance series ends 2026-07-01)

## As built

The original spec listed only the core joins (`security`, `saa`, `risk_profile`, `rule`, `portfolio`). As built, the Dataset class exposes **15 additional lookup methods** to support named-instrument candidates (R5), recommendation-list filtering, and integrity checks:

- `securities_by_isin(isin)` → list of all master rows with that ISIN (one ISIN can be several share classes)
- `security_by_isin(isin)` → first row in file order (index-backed, O(1))
- `portfolios_of(client_ref)` → all portfolios for a client
- `portfolio_ids_of(client_ref)` → set of portfolio ids (for integrity checks)
- `portfolio_by_id(portfolio_id)` → lookup by id
- `fund_mappings(security_id)` → look-through rows for a fund
- `recommendation_lists(security_id)` → names of lists the security belongs to
- `in_recommendation_list(security_id)` → bool membership check
- `recommendation_pool(saa_asset_class)` → recommendation-list members in that SAA class
- `currency_group(currency)` → currency group mapping (CHF/EUR/USD hardcoded; others → "Andere")
- `data_as_of()` → newest date in the data

The `integrity_report()` now returns a richer structure: `dangling_portfolio_refs` (with `client_ref`, `kind`, `portfolio_id`, `rule_code`, `severity`, `reason`), `clients_without_risk_profile`, `portfolios_without_positions`, `notes_total`, `notes_distinct`, `known_data_typos`, and `counts` (clients, portfolios, securities, fund_mappings).

The `load()` function now accepts a `force` parameter to reload the dataset (used after imports/uploads). It also calls `cache.invalidate()` to drop any cached derivations.

## Build

1. Load once at startup; keep in memory. The files are 3.4 MB and 14.6 MB — loading per request is waste.
2. Build dictionary indexes: `sec_id -> security`, `saa_id -> saa`, `risk_profile_id -> profile`,
   `rule_code -> rule`, `fund_id -> [unbundling rows]`.
3. Implement the three helpers first; everything else depends on them.
4. Derived metrics recompute **from `PerformanceHistory`**, never from `PerformanceYTD` (null on all 57).
5. `saa_deviation` must return an empty result for the 5 of 16 SAAs with no `AssetClass` rows — never raise.
6. `lookthrough` groups `FundUnbundlingMappings` by the dimension asked for and divides `Weight` by 100.

## Done when

- All 47 clients and 57 portfolios load with no exception.
- The 8 portfolios with an **absent** `SecurityPositions` key and the 44 **null**
  `IndividualRuleOverrides` both behave as empty, not as errors.
- `integrity_report()` lists `CASE-008`'s dangling portfolio IDs and the four null risk profiles
  (`CASE-029`–`CASE-032`) **as data**.
- `returns()` matches hand-calculation on `CASE-007`: +15.15% (12m), +7.67% (3m).

## Do not

- Recompute or validate suitability violations — see `PROJECT.md` §7 rule 5. They are display-only.
- Read raw JSON from any other module.
- Return collections that are `None`; always `[]`.
- Drop or transform `IBAN` values into logs — strip them.
