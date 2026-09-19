# F4 — Portfolio & positions screen

**Layer:** Frame (exists at URO as portfolio analytics) · **Intelligence:** none · **Wave:** 1
**Depends on:** `F1`, `F5` · **Consumed by:** `R1`, `R6`, `B1`

## Purpose

The analytical view of one portfolio: what it holds, how that compares to what was agreed, and the
current risk picture. This is the screen the advisor most often has open when the phone rings, and it is
the visual reference for the briefing's *Portfolio Health Check*.

## Inputs

- `GET /api/clients/{ref}/portfolios/{nr}`
- `F5` metrics: `saa_deviation`, `concentration`, `fx_exposure`, `lookthrough`, `returns`

## Build

1. **Allocation table** — reproduction of `Portfolio_DB.png`'s SAA panel:
   columns `Min.` · `Soll` · `Max.` · `Portfolio` · `Aktion`, one row per asset-class category.
   - `Min.` / `Soll` / `Max.` come from `StrategicAssetAllocations[].Mappings` (`MinPercentage`,
     `TargetPercentage`, `MaxPercentage` — **fractions 0–1**)
   - `Portfolio` is the actual weight, computed by summing positions grouped by
     `Securities[].SAA_AssetClassName`
   - `Aktion` is the difference (actual − target), shown signed in green/red as in the screenshot
   - Categories are only 5: `Bonds`, `Liquidity`, `Real estate`, `Shares`, `Specialties andCommodities`
   - **Cash accounts carry no asset class.** Map `AccountPositions` to `Liquidity` deliberately
   - If the SAA has no `AssetClass` rows (5 of 16), show the panel as *"Keine Strategie"* rather than an
     empty or misleading table
2. **Positions table** (`Positionsliste`) — `Position` · `Kennung` · `Whg` · `PRC` · `Qt./Nom.` ·
   `Preis / Einstand` · `Wert in CHF` · `PW` · `Erfolg` · `Risikobeitrag` · `Nachhaltigkeit` · `Regeln`.
   Show a `Total` row. Percentages render as `PW`, e.g. `1.55%`.
3. **Metric rail** — the sidebar of the screenshot. Render what the data supports and **omit the rest**:
   supported: SAA, Risiko/Rendite, Product Risk (PRC), Länder, Branchen, Währungen, Fälligkeiten,
   Performance, Nachhaltigkeit, Restriktionen (backed by the override/rule/violation counts),
   Positionsliste. Not supported by the data at all: `Szenarien`, `Emittentenrisiko`. A widget is
   **never emitted with a null value** — if its inputs are missing (no ESG profile, no
   volatility/expected return, no SAA) it simply does not appear. Titles and sub-lines are localised by
   `rail_widgets(client, portfolio, lang)`, and the SAA widget's centre carries the largest
   actual-vs-target deviation rather than a dash.
4. **Risk figures are guarded.** Position rows carry `risk_contribution` / `marginal_risk`, plus
   `risk_figure_dropped` + `risk_figure_reason` when the source value cannot be true (one int64
   overflow in `CASE-041-01`). The row then shows `—` and the portfolio's `data_gaps` says why.
5. **Fondssplitting toggle** — a `Fondssplitting deaktivieren` style toggle: on = allocate funds' underlying holdings by `FundUnbundlingMappings`, off = treat each fund as one line. Implement the toggle against a real computation.
6. Foreign-currency positions show their own currency; totals always in the portfolio currency.
7. **Compact amount formatting** — donut centres and rail widgets use `formatCompactAmount`: EN `905.5k` / DE `905.5 Tsd.` (not `905.5T`, which reads as *trillion* in English). Localised labels throughout; portfolio currency replaces any `{currency}` placeholder (WEBSITE-BUGS.md N6 fixed).

## Done when

- `CASE-007-01` shows shares ≈ 56.7% against a 75% target, giving a visible negative `Aktion`.
- `CASE-028-01` shows 95.9% in a single line without distorting the layout.
- A portfolio whose SAA has no asset-class targets renders "Keine Strategie", not zeros.

## Do not

- Show suitability violations as though this screen computed them — `R3` reports them from the data.
- Present unsupported sidebar metrics as empty gauges; omit them.
