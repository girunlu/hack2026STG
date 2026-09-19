# F7 — Document intray

**Layer:** Frame (exists at URO as the custody document store) · **Intelligence:** parsing only ·
**Wave:** 1 · **Depends on:** — · **Consumed by:** `B1`

## Purpose

Make the ten provided quarterly reports available as documents, and provide the text extraction that
`B1` turns into an importable portfolio. In real life these arrive from another custodian; here they sit
in `unriskomega-2026/side-challenge/`.

These are the *"sample ex-custody portfolio reports for the relevant bonus challenge"* the brief mentions.

## Inputs

- `unriskomega-2026/side-challenge/Quartalsreporting_Q4_2025_*.pdf` — 10 files

## What the documents are

- All **8 pages, ~25 KB, with a clean text layer** — `pypdf` and `pdfminer` are both installed. No OCR.
- Branded **"Privatbank Helvetia AG"**, titled *Vermögensausweis & Performancereporting*.
- Fixed template; only values and mandate differ. Page map:

| Page | Content |
|---|---|
| 1 | Cover KPI card |
| 2 | `Performance Übersicht` |
| 3 | `Performancedetails` |
| 4 | `Vermögensstruktur … Währungen` |
| 5 | `Grafische Portfoliostruktur` |
| 6–7 | `Detailpositionen` — the holdings ledger |
| 8 | `Transaktionen` |

## Build

1. `list_reports()` → the 10 files with name, size, page count, and a friendly client name extracted from the filename.
2. `_extract_pages(path)` → per-page text via `pypdf`. Confirmed working; expect a harmless
   `incorrect startxref pointer` warning from `pypdf` — ignore it, do not treat it as failure.
3. `parse_report(path)` → the full parsed document: cover KPIs (page 1), performance overview (pages 2–3), asset-class × currency cross-table (page 4), graphical structure (page 5), holdings ledger from pages 6–7, and transactions (page 8). The holdings ledger columns:
   `Whg` · `Stück` · `Nominal` · `Bezeichnung` · `Valor` · `ISIN` · `IBAN` · `Einstand` · `Marktkurs` ·
   `Kurs-Datum` · `CHF` · `%-Anteil`.
4. Numbers are **Swiss-formatted**: `2'049'658` (apostrophe separator), percentages `5.20 %`,
   dates `31.12.2025`. Parse accordingly via `parse_swiss_int`, `parse_swiss_float`, `parse_percent`.
5. **Strip `IBAN`** from the parsed result before it leaves this module. The `_is_iban()` helper detects IBAN-shaped tokens and they are excluded from position data.
6. Return `None` explicitly when a field is not present rather than defaulting to zero.
7. `parse_default_or(file)` → convenience wrapper for the API layer: resolves the filename (or the first sorted report) and parses it.

## Done when

- All 10 PDFs list and extract their text.
- `extract_positions` returns a non-empty, ISIN-keyed holdings list for each of the 10 files.
- Numeric fields parse to floats correctly (spot-check a total against the printed page total).

## Do not

- Attempt OCR — every page has a real text layer.
- Treat the `startxref` warning as an error.
- Pass raw text downstream. Only structured rows leave this module.
- Leak `IBAN` into any return value, log, or error message.
