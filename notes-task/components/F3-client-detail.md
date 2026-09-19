# F3 — Client detail screen

**Layer:** Frame (exists at URO as the client record) · **Intelligence:** none · **Wave:** 1
**Depends on:** `F1`, `F5`, `F6` · **Consumed by:** `R1` (the trigger button lives here), `R6`

## Purpose

Everything about one client on one screen: their portfolios, their past advisory sessions, and what we
know about them personally. **This is where the advisor notices a call is coming and clicks Generate
Briefing** — so `R1`'s entry point belongs on this screen.

## Inputs

- `GET /api/clients/{ref}`
- `F6` context (notes, tags, overrides)

## Build

1. Header: `Name (ClientRef)`, plus `Kundentyp` and `Kundenprofil` — as in `Client_DB.png`.
2. **Portfolio cards** — one per portfolio: portfolio number, name, strategy, a small allocation donut,
   the value, and a risk figure. The screenshot shows three cards including a foreign-bank one labelled
   `ZKB`; that third slot is where an imported ex-custody portfolio (`B1`) appears. See `F4`.
3. **`Beratungen` table** — the client's proposals/sessions. Columns from the screenshot:
   `Anlagedienstleistung` · `Container` · `Beratungsart` · `Beratung` · `Nr.` · `Status` ·
   `Geändert durch` · `Letzte Änderung`.
   - Map `Beratungsart` from `AdvisoryTypeName` (`Investment proposal`, `Depot meeting`)
   - Map `Status` from `ProposalStatusName` — the values are **German**: `Final`, `Abgelehnt`, `Entwurf`
   - Only 3 advisory types and 3 statuses exist; do not invent more
4. **Notes and tags panel** — quote notes verbatim with their dates; render `Region` and `Industry` tags
   as distinct chip styles. Collapse duplicates (`F6` flags them).
5. A prominent **Generate Briefing** action (`R1`). Where a portfolio is in focus, scope the briefing to it.
6. Status chips must carry meaning: `Entwurf` (draft) vs `Final` vs `Abgelehnt` (rejected) should be
   visually distinct, and a rejected proposal should not read as an open one.
7. **Violations show `rule_description`** (localized), not a hardcoded German field or raw C# field names (WEBSITE-BUGS.md #3, #11 fixed). The violation card renders the rule's description in the current language, plus the rule code and portfolio label.
8. **Correct plurals** — "1 error rule violation" is gone; the UI renders "1 Regelverstoss" / "1 rule violation" with proper singular/plural handling (WEBSITE-BUGS.md #11 fixed).
9. **Errors and warnings are separate groups, not one list.** The section carried a single heading over
   every violation of both severities, so a warning sat between two urgent errors and severity was
   carried only by a colour. It now renders the errors first under `{count} rule violations` /
   `{count} Regelverstösse` and the warnings second under `{count} warnings` / `{count} Warnungen`
   (`client.violationsCount` / `client.warningsCount`, ICU plurals), each group only when it has rows,
   and the empty case keeps a single `No rule violations.` / `Keine Regelverletzungen.` line. The
   section keeps the id `#client-violations` on one element — the shell nav's `Regelverletzungen`
   button and the dashboard's skipped tabs scroll to it, so splitting the anchor would break them.
   The nav's own count remains the client's total (errors + warnings).


- `CASE-007` renders: one portfolio, **seven** proposals (all `Final`, the newest ending with
  `Follow-up from prior meeting`), five notes including the property-purchase note, three tags. (This
  spec previously said six; the record holds seven.)
- `CASE-008` renders its dangling `Portfolio 210525` as `(unknown)` in English / `(unbekannt)` in German,
  driven by `portfolio_known: false`, and its 12 violations as `dangling_violations: 12` — never a crash.
- The header's `Own portfolios (n)` counts only portfolios **without** `is_external`; imported ex-custody
  portfolios appear in the same grid with a bank icon and are counted on the `External banks` button.
- `CASE-028` renders with **zero** proposals and **zero** violations without breaking the layout.
- The Generate Briefing button is reachable and passes the client reference onward.

## Do not

- Show `IBAN` values anywhere. `AccountPositions[].IBAN` is **real** data — strip it at the API boundary.
- Present `Abgelehnt` proposals as open or pending.
