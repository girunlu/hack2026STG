# URO Advisor Pro — Component Inventory (v2, audit-corrected)

> Complete component table extracted from 3 screenshots at 3x zoom. Every UI element needed to rebuild the mock interface.
> v2 corrections: nav labels/badges, tab counts, indicator glyphs, pagination label, status styling, SAA bar geometry, meta-band vs tabs.

---

## 1. Global Chrome (all screens)

| ID | Component | Description |
|----|-----------|-------------|
| G-01 | **Top Header Bar** | Full-width, solid blue (`#4A90D9` approx). Left: URO logo (off-white text + orange ring mark, use `uro-dark.svg`). Right: search icon, user name "Hans Muster" with dropdown chevron |
| G-02 | **Secondary Nav Bar** | Light bar (`#F4F6F8`) below header, cells separated by thin vertical borders. Left: page/client title. Right: nav items, each = icon + label; the ACTIVE item is blue text+icon (no pill/underline); some items carry a badge pill (red = urgent count, gray = zero count); far right: back arrow `←` (screens 2, 3 only) + hamburger `☰` |
| G-03 | **Meta Band** | Light gray band under the nav. Screen 1: welcome row (see D1-01). Screens 2–3: client name row + label/value metadata pairs (see D2-01, D3-01) with the CHF total right-aligned |

### Per-screen nav items (exact)
| Screen | Items left→right (badge) | Active |
|--------|--------------------------|--------|
| 1 Dashboard | Beratermappe, Kundenliste, Regelverletzungen (114 red), Warnungen (21 red), ☰ | Kundenliste |
| 2 Client | Beratermappe, Notizen (0 gray), Vermögen, Regelverletzungen (4 red), Kundeninformation, ←, ☰ | Vermögen |
| 3 Portfolio | Telefonberatung, Beratermappe, Notizen (0 gray), Analyse, Kundeninformation, Portfolio, ←, ☰ | Analyse |

---

## 2. Screen 1 — Kundenberater-Dashboard (Client Advisor Home)

| ID | Component | Description |
|----|-----------|-------------|
| D1-01 | **Welcome / Summary Row** | Inside meta band. Left: "Willkommen zurück, Hans Muster" (bold) then a small gray line: `Pendente Beratungen: 215 | Restriktionen | Warnungen: 21` — pipe-separated; **Restriktionen has NO value** (blank). Right: `CHF 52'618'933.52` bold ~20px |
| D1-02 | **Section Title** | "Meine Kunden" — bold, left-aligned, inside white card |
| D1-03 | **Filter Tab Bar** | Horizontal row of text tabs, each = label + badge pill. ACTIVE tab: blue text + blue 2px underline + BLUE badge pill. Inactive: dark text + DARK-CHARCOAL badge pill (white digits). Right end: `+` square button. Exact tabs: Kunden (45, active), Neukunden (6), Beratungen (215), 01 - Liquidity > 10% (112), 02 - Maturities (0), 03 - Last Consultation > 12 Months (191), 04 - Rule Violations (urgent) (28), 05 - Birthdays (13), Neu (146), Neu (146), Testsuche (5), Neu (146), Neu (146) |
| D1-04 | **Search Box** | Right of tab bar: magnifying-glass icon + "Suche" placeholder, bordered input |
| D1-05 | **Data Table** | Full-width sortable table. Columns: (checkbox), (red ×-circle), (yellow !-triangle), Kundennr., Name, Strasse / Nr., PLZ / Ort, Geburtstag, Letzte Profilierung, Zuletzt geändert, Letzte Beratung. Headers 12px with sort arrows. Name column = blue links. Strasse/PLZ columns are EMPTY in the screenshot |
| D1-06 | **Row Indicators** | Red = filled circle with white × inside (rule violation). Yellow = filled triangle with white ! inside (warning). Independent per row; a row may have both, one, or none |
| D1-07 | **Pagination** | Bottom: `« Vorherige` (gray, disabled on page 1) · page buttons 1 (blue active) 2 3 4 5 · `Nächste »` (blue link). Far right: "Resultate pro Seite" + dropdown |

---

## 3. Screen 2 — Einzelner Kunde (Single Client: Tanja Bauer)

| ID | Component | Description |
|----|-----------|-------------|
| D2-01 | **Client Meta Band** | Row 1: "Tanja Bauer (41839-29)" bold left; `CHF 1'497'989.49` bold right. Row 2 (gray): two label/value pairs separated by vertical border: `Kundentyp / Natürliche Person`, `Kundenprofil / Ausgeglichen` (small gray label above dark value) |
| D2-02 | **Portfolio Filter Buttons** | Row of filled buttons with icon + label. ACTIVE = blue fill, white text. INACTIVE = medium-gray fill (`#C4C8CC`), dark text. Yellow !-triangle badge on: Alle Portfolios, Eigene Portfolios, Fremdbanken (not on Konsolidierung/Beziehungen). Order: Alle Portfolios (active), Eigene Portfolios, Fremdbanken, Konsolidierung, Beziehungen |
| D2-03 | **Portfolio Cards Carousel** | Horizontal row, 3 cards visible. 2 dot indicators below (first active blue, second gray). Right chevron `›` for next page |
| D2-04 | **Portfolio Card** | White card, subtle shadow. Top-left: icon (person outline for own portfolios, bank/building outline for external) + portfolio ID bold. Top-right: yellow !-triangle (card 1 only). Title line: `<name> | <strategy> (CHF)` gray 12px. Middle: donut chart + gauge chart side by side. Bottom: CHF value bold + percent gray |
| D2-05 | **Donut Chart (Card)** | Blue donut ring; center shows CHF value |
| D2-06 | **Gauge Chart (Card)** | Blue semi-circle gauge; percent below |
| D2-07 | **Beratungen Section Title** | "Beratungen" bold heading |
| D2-08 | **Table Toolbar** | Right-aligned: blue square edit/pencil button, "Beratungsart" dropdown, "Status" dropdown, search box |
| D2-09 | **Beratungen Table** | Columns: (checkbox), (red ×-circle), (yellow !-triangle), Anlagedienstleistung, Container, Beratungsart, Beratung (blue link), Nr., Status, Geändert durch, Letzte Änderung, (trash icon on SOME rows only: rows 3,4,5,8,9,10; absent on 1,2,6,7) |
| D2-10 | **Status Values** | "Vorgeschlagen" and "Entwurf" are BOTH plain dark text (no color difference, not links) |
| D2-11 | **Pagination** | `« Vorherige` · 1 (active) 2 3 4 5 … 16 · `Nächste »` · "Resultate pro Seite" dropdown |

---

## 4. Screen 3 — Portfolio Analyse (Portfolio Analysis)

| ID | Component | Description |
|----|-----------|-------------|
| D3-01 | **Portfolio Meta Band** | NOT tabs. Gray band with three static label/value pairs separated by vertical borders: `Portfolio / 15.02996`, `Anlagedienstleistung / Anlageberatung Portfolio`, `Strategie / Rendite`. Right: `CHF 456'456.98` bold |
| D3-02 | **SAA Section Header** | Pie icon + "SAA" bold; right side: settings gear icon + fullscreen icon |
| D3-03 | **SAA Description** | German paragraph (see 04-data-models for exact text). Then same paragraph flow: `Anlagetipp:` as **inline bold label** followed by regular text on the same line — NOT a boxed callout |
| D3-04 | **SAA Table** | Centered sub-heading "Strategische Asset Allokation". Columns: category name (left), Min., Soll, Max., Portfolio, Aktion (right-aligned). Rows: Liqu. / Geldmarkt, Obligationen, Aktien, Immobilien, Übrige Anlagen. UNDER EACH ROW: a horizontal progress bar = light-gray track full width + colored fill whose width ≈ portfolio% (scale: ~60% = full). Fill colors: Liqu `#4A90D9`, Obligationen `#4A90D9`, Aktien `#45B4E6`, Immobilien `#45D0C5`, Übrige `#57D9A3`. Negative Aktion values are plain dark text (NOT red) |
| D3-05 | **Donut Chart (Center)** | Large multi-ring donut (5 concentric rings, category colors). Center text two lines: `456.5T` bold + `CHF` small |
| D3-06 | **Metrics Sidebar (Right)** | 3-column grid, 5 rows, 15 widgets. See detail table below |
| D3-07 | **Positionsliste Section** | Heading with collapse chevron + "Positionsliste". Right: SOLID blue button "Fondssplitting deaktivieren" (one word, no hyphen) |
| D3-08 | **Positions Table** | Columns: Position, Kennung, Whg, PRC, Qt./Nom., Preis / Einstand, "Wert in CHF / Marchzins" (ONE column, two-line header), Aktion, PW, Erfolg, Risikobeitrag, Nachhaltigkeit, Regeln, Info. First body row = "Total" on gray band, bold value. Then expandable group rows with minus-square collapse icons, indented child rows |
| D3-09 | **Aktion Cell** | Green text with leading arrow: `→ 3.63%` |

---

## 5. Metrics Sidebar Detail (D3-06)

| # | Title | Visual | Value | Sub |
|---|-------|--------|-------|-----|
| 1 | SAA | White donut on RED bg (alert state) | — | — |
| 2 | Suitability | Blue gauge | 12% | — |
| 3 | Risiko / Rendite | Dot/scatter plot | 12% Risiko | 4.3% Rendite |
| 4 | Szenarien | Bar chart | -30.5% | Globale Finanzkrise |
| 5 | Product Risk | Donut | 57.3% | PRC-L |
| 6 | Länder | World map | 65.4% | Nordamerika |
| 7 | Branchen | Donut | 20% | Zyklischer Konsum |
| 8 | Währungen | Donut | 44% | US-Dollar (USD) |
| 9 | Fälligkeiten | Bar chart | 100% | Nicht klassifiziert |
| 10 | Restriktionen | 3 icon+number rows | 1 / 5 / 0 | — |
| 11 | Performance | Line chart with ↑ | 13.1% | — |
| 12 | Nachhaltigkeit | Donut | Nachhaltig | 0 ESG-Rating |
| 13 | Zielerreichung | Target icon + line | — | — |
| 14 | Emittentenrisiko | Donut | 100% | Ausgeschlossen |
| 15 | Positionsliste | Grid icon | 13 Positionen | — |

---

## 6. Reusable Component Summary

| Component | Used In |
|-----------|---------|
| Top Header Bar (G-01) | All 3 screens |
| Secondary Nav Bar w/ badges + active-blue (G-02) | All 3 screens |
| Meta Band (label/value pairs) | Screens 2, 3 |
| Data Table with sort + indicators | D1-05, D2-09, D3-08 |
| Filter Tabs with badge pills | D1-03 |
| Filled Filter Buttons (blue active / gray inactive) | D2-02 |
| Pagination (« Vorherige / Nächste ») | D1-07, D2-11 |
| Portfolio Card | D2-04 |
| Donut Chart | D2-05, D3-05, sidebar |
| Gauge / Semi-circle Chart | D2-06, sidebar |
| Horizontal Progress Bar (SAA) | D3-04 |
| Metrics Sidebar Widget | D3-06 (15 instances) |
| Search Box | D1-04, D2-08 |
| Dropdown Select | D1-07, D2-08, D2-11 |
| Indicator glyphs (red ×-circle, yellow !-triangle) | D1-06, D2-09, D2-02 |
| Expandable Table Rows (minus-square) | D3-08 |
