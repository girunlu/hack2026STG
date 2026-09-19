# R3 — Relevance engine

**Layer:** Product (brief requirement 3 of 6: *"Identify what matters"*) · **Intelligence:** **core** ·
**Wave:** 1 · **Depends on:** `F5`, `F6`, `X1`, `X2` (via `R2`) · **Consumed by:** `R4`, `R5`, `R6`, `T1`

## Purpose

Decide which observations deserve the advisor's attention, and prove each one. This is the most important
component in the project — the brief's own measure of success:

> *"The assistant should prioritize the most important findings instead of listing every available metric."*

The hard part is not showing data. It is choosing **two to four things that matter for this particular
client**.

## Outputs

`findings[]` — the contract in `PROJECT.md` §5.2. Every finding carries:

- `type` — from the fixed enum (§5.4)
- `severity` — `high` | `medium` | `low`
- `score` — a number used for ranking
- `title`, `detail` — short and specific, no filler
- `evidence[]` — **at least one entry**, each with `label`, `value`, `source`, `path`

## Extractors to build

| Extractor | `type` | What it looks for |
|---|---|---|
| Performance trajectory | `performance_driver` | Portfolio-level moves from `PerformanceHistory`: biggest month, last 3m/12m, drawdowns |
| Risk contribution | `performance_driver` | Which positions dominate `ContributionVolatility`, read through `metrics.risk_contributions()` — the cleaned series. The raw field is **not** trustworthy on its own: `CASE-041-01` carries an int64-overflow sentinel (and 3 portfolios have a volatility with an all-zero series), so the driver skips a portfolio with no usable series instead of claiming a share |
| Concentration | `concentration` | Top position weight, and HHI. Four clients hold ~95% in one stock |
| Allocation drift | `allocation_drift` | Actual vs `Mappings` min/target/max, via `SAA_*` fields |
| Rule violations | `rule_violation` | Reported **as given**, explained via `ViolationPath[]` |
| Risk alignment | `risk_alignment` | `Portfolio.Volatility` vs `RiskProfile.MaxVola` — **as context only**, see below |
| Preference conflict | `preference_conflict` | A `F6` note against an actual holding (fossil fuels vs Neste) |
| Liquidity event | `liquidity_event` | Upcoming cash need from notes, weighted against holding liquidity |
| FX exposure | `fx_exposure` | Currency concentration |
| Open proposals | `open_proposal` | Drafts and pending items, by age |
| Staleness | `stale_data` | Old `FactoryDateUtc`, old last interaction |
| Missing data | `missing_data` | Anything in `R2`'s `gaps[]` |

## Two hard constraints

**1. You cannot compute performance attribution.** The data has no position cost basis and no position
history — there is no way to know which holding drove last quarter's return. **Never claim it.**
What you *can* say truthfully:
- portfolio-level trajectory from `PerformanceHistory` (real, monthly, 2021-10 → 2026-07)
- **risk** contribution from `ContributionVolatility` (real, sums to portfolio volatility)
- weights and concentration (real)
Say "risk contribution", never "performance contribution".

**2. Violations are display-only.** Recomputing "maximum volatility" disagrees with the ground truth on
15 of 46 portfolios. Explain a violation using its `ViolationPath[]` (`LeftValue` vs `RightValue`).
Use `RiskProfile.MaxVola` as *context* — never to declare a violation yourself.

## Ranking

Build a deterministic `score`:

1. **Severity by type** — an `Error`-level rule violation or >80% concentration outranks a mild drift.
2. **Magnitude** — how far outside the target/limit, normalised.
3. **Age** — recent movement and stale data both matter; ignore nothing dated.
4. **Client-specific weighting** — a `liquidity_event` note raises the rank of anything implying an
   illiquid action; `risk_attitude: risk-averse` raises risk findings; `concentration_tolerance` lowers
   a concentration finding's rank (the client explicitly accepts it).
5. Emit the ranked list, but let `R4` select the top few. Keep the cut-off configurable so it can be tuned
   without touching extractors.

## Done when

- `CASE-007` ranks the max-volatility violation and the equity-target drift highly, and produces an
  `liquidity_event` finding from the property note.
- `CASE-028` produces a `concentration` finding (95.9% VZ Holding) and **no** invented problems — it has
  zero violations and zero proposals.
- `CASE-017` produces a `preference_conflict` finding that the rule engine does not report.
- `CASE-027` and `CASE-029` produce `missing_data` findings instead of crashing.
- Two different clients never produce identical finding sets.

## Do not

- Emit a finding with empty `evidence`.
- Claim performance attribution (see above).
- Declare a violation the data does not already declare.
- Use an LLM to rank. Ranking is deterministic code — it must be testable and stable.
