# B1 — Ex-custody import

**Layer:** Bonus (brief: *"Ex-Custody Portfolio Import"*) · **Intelligence:** parsing + classification ·
**Wave:** 4 · **Depends on:** `F7`, `F5`, `F4` · **Consumed by:** `R2`

## Purpose

Let the advisor upload a portfolio statement from another custodian, turn it into a working portfolio, and
have it behave like any other portfolio — including inside the briefing.

The brief's requirements:

> *Extract the portfolio positions · Identify weights and currencies · Assign positions to the appropriate
> asset classes · Create a virtual portfolio · Label it clearly as an ex-custody portfolio · Include it in
> the portfolio analysis and 60-second briefing*

> *The virtual portfolio should behave like a portfolio already available in URO Advisor Pro.*

## Inputs

- `F7` — parsed positions from one of the 10 `side-challenge/` PDFs
- An advisor-chosen target client to attach it to

## Build

1. **Upload endpoint** `POST /api/import/ex-custody` (JSON body with `file` and `client_ref`).
2. **Parse** via `F7`. Positions come from the `Detailpositionen` pages: `Whg` (currency), `Stück`,
   `Nominal`, `Bezeichnung`, `Valor`, `ISIN`, `Einstand`, `Marktkurs`, `Kurs-Datum`, `CHF`, `%-Anteil`.
3. **Resolve each ISIN** against `reference.json` `Securities`:
   - **Matched** → take `SAA_AssetClassName`, `SAA_CurrencyGroupName`, industry and country from our own
     master data. This is the correct route.
   - **Unmatched** → the instrument is outside our universe (it is another bank's book). Keep the position,
     classify it by whatever the document states, and mark it `unclassified`. **Never guess an asset class
     and never drop the position silently.**
4. **Verify against the document.** Page 4 prints the report's own asset-class × currency table. Compare
   your computed allocation with the printed one and surface the difference. If the numbers disagree
   materially, say so — this cross-check is exactly what "real-life standard" means, and finding a
   discrepancy is more impressive than hiding one.
5. **Build the virtual portfolio** with the same shape as a real one (`F5`'s dataset contract) so that
   `R2`, `R3`, `F4` and `R6` need no special-casing.
6. **Label it unmistakably** — name it as an ex-custody / Fremdbanken portfolio and carry a
   `provenance: "ex_custody"` flag everywhere it appears, **including in the briefing text**. As built:
   the R2 portfolio block carries `is_external: true` + `provenance: "ex_custody"`, and its
   `data_gaps` state in words that the portfolio came from a third-party statement (so the label
   reaches the briefing's rendered text, not just the payload).
7. **Refuse a duplicate.** Importing the same statement twice for one client returns **409** with a structured error (`code: "already_imported"`, `portfolio_nr`, `source_file`, `message`) — a doubled import would count the same assets twice in the analysis and the briefing. Deleting the existing import and re-importing is the supported path.
8. **ImportResponse carries two shapes.** `portfolio` is the F5 projection (PascalCase: `PortfolioNr`, `SecurityPositions`, `AccountPositions`, `DataGaps`) so R2/R3/R6 treat it like any other portfolio. `report` is the parsed statement in its own snake_case view model (KPIs, positions, transactions, currency structure, data-quality notes) so the Fremdbanken panel can render the document's own structure. Both are returned in the same response.
9. It must appear on the client's screen in the `Fremdbanken` position (`F4`), alongside the client's own portfolios.

## Done when

- Each of the 10 PDFs imports without error and yields a populated virtual portfolio.
- The imported portfolio shows up in the client's portfolio list, marked ex-custody.
- `POST /api/briefing` for a client with an imported portfolio includes it and says so.
- The document cross-check (step 4) runs and reports its result.

## Do not

- Publish, log or render any `IBAN` from the statement.
- Claim an ex-custody holding is ours — the label must always be visible.
- Silently drop unmatched instruments.
- Pretend the imported weights are authoritative when the document's own totals disagree.
