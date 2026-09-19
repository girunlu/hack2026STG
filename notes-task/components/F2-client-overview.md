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
5. Row count and pagination like the screenshot (`Resultate pro Seite`). Clicking a row opens `F3`.
6. Show the advisor's book total in the header (the screenshot shows `CHF 52'618'933.52` — compute ours
   from the 47 clients, do not copy that figure; it belongs to a different dataset).
7. **Dashboard tab in the URL** — clicking a filter tab writes `#/?tab=<id>` to the address bar, so refresh and share preserve the selected tab (WEBSITE-BUGS.md N5).
8. **Only opted-in columns sort** — the violation and warning indicator columns are not sortable; sortable columns toggle the ▲ arrow and actually reorder (WEBSITE-BUGS.md #14 fixed).

## Done when

- All 47 clients appear with correct Swiss-formatted dates and numbers.
- At least the `04 - Rule Violations (urgent)` tab returns a correct, non-zero count.
- Clicking a row routes to the client detail screen.

## Do not

- Copy figures, names or client numbers from the screenshots — they are UI reference only and appear
  nowhere in the case data (the screenshots' client `41839-29` does not exist in `clients.json`).
- Invent addresses, phone numbers, or a "last contacted" field.
