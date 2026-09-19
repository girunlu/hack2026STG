# R6 — Briefing presentation

**Layer:** Product (brief requirement 6 of 6: *"Present the result clearly"*) · **Intelligence:** none ·
**Wave:** 3 · **Depends on:** `R4`, `F1` · **Consumed by:** `B2`, `B3`

## Purpose

Render the briefing so it can genuinely be absorbed in about 60 seconds by an advisor under time
pressure. This screen is what the jury looks at most, and the traceability on it is the strongest
argument that the tool is trustworthy.

## Inputs

The briefing object (`PROJECT.md` §5.3), plus the `facts` it was built from — the traceability needs both.

## Layout

1. **Header** — client name and reference, `data_as_of`, and the provenance line: sources used, and which
   parts are mock (the house view) versus live (news) versus simulated (the portfolio snapshot).
2. **Three sections**, in the brief's order, with the brief's titles:
   *Recent Portfolio Development* · *Portfolio Health Check* · *Portfolio Outlook & Next Best Actions*.
3. **Four-question strip** — the compact `what_happened` / `situation` / `next` / `should_do` answers, so
   the advisor's four questions are visibly answered.
4. **Actions block** — the `R5` actions with priority, rationale and the finding they came from.
5. **Unavailable / gaps** — a clearly styled list. Missing data must be *visible*, not silently absent.

## Readability rules

- Lead each block with a bold half-sentence: *"**Portfolio up 15.15% over 12 months**, driven by equities."*
- One idea per bullet. No paragraph longer than two lines.
- Show the numbers Swiss-formatted: `1'234.56`, `5.20 %`, dates `DD.MM.YYYY`.
- Total target **200–280 words** — that is ~60 seconds. Display the estimated read time if useful, but only
  if it is computed honestly from the text.
- Visually separate **portfolio facts** from **external market context** — the brief requires the
  distinction to be visible.
- Severity drives colour: violation/`high` findings stand out, but never more than a few things compete
  for attention. If everything is highlighted, nothing is.

## Traceability — the differentiating feature

Every claim carries its evidence. Render each block with a subtle affordance (icon or dotted underline);
clicking reveals the `evidence[]` entries: the label, the value, the source file and the field path.

A juror must be able to point at any sentence and ask *"where did that come from?"* and get an answer in
one click. Nothing else you build will be as persuasive.

**And the trace must lead somewhere.** A slice the advisor cannot act on is a dead end — *"13 rule
violations"* is useful only if the next click shows *which* thirteen. Every evidence row therefore
carries the data path it came from, and `src/frontend/src/lib/evidenceTarget.ts` turns that path into a
destination: `SuitabilityViolations`/`RuleViolation` → the client's violations, `SecurityPositions`/
`ContributionVolatility`/`MarketValue` → the positions table, `StrategicAssetAllocation`/`AssetClass` →
the SAA panel, `ClientNotes` → the notes, a finding's own type (`rule_violation`, `allocation_drift`,
`concentration`, `performance_driver`) when the row *is* a finding, an ISIN → the market screen, a
`news:` ref → the article. The mapping follows the data model, so a new screen is one entry, not a new
list to maintain; a row with no destination stays plain text rather than pretending to be a link.

Rows are laid out so the panel reads as one list: line one is the slice (label left, value right), line
two is where it came from, truncated rather than wrapped — a news ref is a full URL, and letting it wrap
made one row 170px tall beside rows of 60px. Measured after the change: 49px for value rows against 91px
for a finding row with a long value, and clicking the violation row on `CASE-012` lands on
`#/client/CASE-012` scrolled to *"13 Regelverstösse"*.

## Done when

- `CASE-007` renders three sections, four answers, actions, and a provenance line.
- Every block's trace affordance resolves to real evidence entries.
- `CASE-027` visibly states *"no market data available"* for its dominant position.
- `CASE-029` visibly states that the risk profile is unavailable.
- The whole screen fits one typical viewport without scrolling on a laptop.

## Do not

- Hide gaps to make the screen look complete.
- Display an `IBAN` anywhere.
- Shade or truncate evidence — the trace panel shows the actual values.
- Add a chart the data does not support.
