# F2 — Client overview screen

**Layer:** Frame (exists at URO as the client list) · **Intelligence:** none · **Wave:** 1
**Depends on:** `F1` (shell), `F5` (data) · **Consumed by:** — (entry point to `F3`)

## Purpose

The advisor's home screen: every client in one table, filterable to the ones that need attention. This is
where an advisor would notice *who to call* — and therefore where the briefing story naturally begins.

## Inputs

- `GET /api/clients` (`F5`-backed). Use a fixture if the backend is not ready yet.

## Build

1. Sortable table, columns exactly as in `Client_Advisor_DB.png`:
   `Kundennr.` · `Name` · `Geburtstag` · `Letzte Profilierung` ·
   `Zuletzt geändert` · `Letzte Beratung`
2. Dates render as `DD.MM.YYYY`.
3. **`Strasse / Nr.` and `PLZ / Ort` are empty for every client** in the source data. The columns were removed from the dashboard (WEBSITE-BUGS.md #14) — they are no longer rendered.
4. Above the table, the filter tabs from the screenshot — these map onto real fields, so wire the ones
   that can actually be computed:
   - `01 - Liquidity > 10%` — cash weight above 10%
   - `02 - Maturities` — holdings with a near `MaturityDateUtc`
   - `03 - Last Consultation > 12 Months` — from latest proposal / note date
   - `04 - Rule Violations (urgent)` — clients with any `SuitabilityViolations` of severity `Error`
   - `05 - Birthdays` — upcoming `Birthday`
   - `Beratungen` — clients with at least one consultation
   - `Warnungen` — clients with warning-level violations
   Unsupported tabs must not be faked: show a real count or hide the tab.

   **Where the violations come from.** The severities are the case data's own, not ours: every client
   carries `SuitabilityViolations`, each with `Severity` (`Error` or `Warning`), `RuleCode`,
   `RuleDescription` and a `ViolationPath` holding the engine's numbers. The case data holds **96
   Error and 84 Warning** records over 48 clients, from 50 distinct rule codes, so the bank's rule
   engine decides what a violation is and how urgent it is; `_severity_counts` only counts the two
   severities (`app/api/clients.py`), and F3 prints the violation's own description and the path's own
   values rather than re-deriving either. What *we* decide are the check-style tabs — Liquidity > 10%,
   Maturities (`MATURITY_WINDOW_DAYS`), Last Consultation > 12 Months, Birthdays
   (`BIRTHDAY_WINDOW_DAYS`) — thresholds we chose over provider fields.
   **`Beratungen` cannot discriminate on the case data**: every one of the 48 clients has a
   consultation date or a note, so its count equals the book total and selecting it leaves the list
   unchanged (`#/?tab=beratungen`). It is a real filter, not a dead control — `01 - Liquidity > 10%`
   cuts the list to 13 rows — and the tab is highlighted and written to the URL when selected.
5. Row count and pagination like the screenshot (`Resultate pro Seite`). Clicking a row opens `F3`.
6. Show the advisor's book total in the header (the screenshot shows `CHF 52'618'933.52` — compute ours
   from the 47 clients, do not copy that figure; it belongs to a different dataset).
7. **Dashboard tab in the URL** — clicking a filter tab writes `#/?tab=<id>` to the address bar, so refresh and share preserve the selected tab (WEBSITE-BUGS.md N5).
8. **Only opted-in columns sort** — sortable columns toggle the ▲ arrow and actually reorder
   (WEBSITE-BUGS.md #14 fixed). The violation and warning cells are **not** columns: `DataTable` draws
   them from `showIndicators` + `indicators(row)`, and they carry the `Rule violation` / `Warning`
   aria-labels on their header cells. Declaring them in `columns` *as well* put four indicator cells in
   every row — each icon twice, and the surplus cells pushed every value one slot (20px) left of its
   header: the client number printed under an empty slot, the name under `Kundennr.`, the birthday
   under `Name`, and `Letzte Beratung` stayed empty. The cell also has to stay a table cell:
   `display: inline-flex` on `<td class="uro-table__indicator">` took the cell out of the table layout
   and collapsed the two indicator columns onto each other, which produced the same one-slot shift
   even after the duplicate columns were gone. Both closed; re-measured in the browser, all six data
   columns now sit exactly under their headers on every row.
9. **No row checkboxes.** The prototype has no bulk action, so `showCheckboxes` is off: the box
   selected nothing, and its click bubbled into the row handler and navigated to the client instead
   (measured `#/` → `#/client/CASE-022`, tick lost).

## Done when

- All 47 clients appear with correct Swiss-formatted dates and numbers.
- At least the `04 - Rule Violations (urgent)` tab returns a correct, non-zero count.
- Clicking a row routes to the client detail screen.

## Do not

- Copy figures, names or client numbers from the screenshots — they are UI reference only and appear
  nowhere in the case data (the screenshots' client `41839-29` does not exist in `clients.json`).
- Invent addresses, phone numbers, or a "last contacted" field.
