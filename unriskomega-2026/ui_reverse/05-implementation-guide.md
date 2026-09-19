# URO Advisor Pro — Implementation Guide

> Step-by-step build order, tech decisions, and file structure. A cold-start agent can follow this document alone to rebuild the entire mock UI.

---

## 1. Tech Stack Decision

**Recommended: React + TypeScript + Vite**

| Concern | Choice | Why |
|---------|--------|-----|
| Framework | React 18+ | Component model maps 1:1 to the component table |
| Language | TypeScript | Interfaces from `04-data-models.md` drop in directly |
| Build | Vite | Fast HMR, zero-config for a prototype |
| Styling | CSS Modules or Tailwind | Tailwind recommended for speed; all colors/tokens in `02-design-system.md` |
| Charts | Custom SVG | Donuts and gauges are simple enough — no chart library needed. Keeps bundle small. |
| Icons | `lucide-react` | Matches the line-icon style in screenshots. 1 icon per component. |
| Routing | React state (no router) | Only 3 screens, simple parent-child navigation. No need for react-router. |
| Data | Static JSON files | Mock data from `04-data-models.md`. No API needed. |

**Alternative: Plain HTML/CSS/JS** — viable if the builder prefers zero dependencies. All components are static; no framework needed. But React makes the table/card/tab patterns much cleaner.

---

## 2. Project Structure

```
uro-advisor-mock/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx                    # Root: manages screen state, renders current screen
│   ├── types.ts                   # All interfaces from 04-data-models.md
│   ├── data/
│   │   ├── clients.ts             # dashboardClients array
│   │   ├── tanja-bauer.ts         # tanjaBauer + tanjaPortfolios + beratungen
│   │   └── portfolio-analysis.ts  # saaEntries, sidebarMetrics, positions
│   ├── utils/
│   │   └── format.ts              # formatCHF(), formatDate()
│   ├── components/
│   │   ├── Header.tsx             # G-01: top blue bar
│   │   ├── SecondaryNav.tsx       # G-02: nav bar (props: items, badges, activeItem, showBack)
│   │   ├── MetaBand.tsx           # G-03: label/value pairs band (screens 2, 3) + welcome row (screen 1)
│   │   ├── DataTable.tsx          # Reusable sortable table (D1-05, D2-09, D3-08)
│   │   ├── Pagination.tsx         # D1-06: page buttons + results-per-page
│   │   ├── PortfolioCard.tsx      # D2-04: card with donut + gauge
│   │   ├── DonutChart.tsx         # SVG donut (single + multi-ring)
│   │   ├── GaugeChart.tsx         # SVG semi-circle gauge
│   │   ├── MetricsSidebar.tsx     # D3-06: 3-col grid of 15 widgets
│   │   ├── MetricWidget.tsx       # Single widget (donut/gauge/bar/line/map/grid/icon/text)
│   │   ├── SearchBox.tsx          # D1-03: search input with icon
│   │   ├── StatusIndicator.tsx    # Red ×-circle + yellow !-triangle glyphs
│   │   ├── ProgressBar.tsx        # SAA horizontal track+fill bar under each row
│   │   └── SAATable.tsx           # D3-04: SAA allocation table + progress bars
│   ├── screens/
│   │   ├── DashboardScreen.tsx    # Screen 1
│   │   ├── ClientScreen.tsx       # Screen 2
│   │   └── PortfolioScreen.tsx    # Screen 3
│   └── styles/
│       └── tokens.css             # CSS custom properties from 02-design-system.md
├── public/
│   └── logos/
│       ├── uro-light.svg          # Copied from ../assets/logos/
│       └── uro-dark.svg
└── README.md
```

---

## 3. Build Order (do in this sequence)

### Phase 1: Foundation
1. **Scaffold Vite + React + TS project**
2. **Create `tokens.css`** — all CSS custom properties from `02-design-system.md`
3. **Create `types.ts`** — all interfaces from `04-data-models.md`
4. **Create `utils/format.ts`** — `formatCHF()`, `formatDate()`
5. **Create `Header.tsx`** — blue bar, URO logo (use `uro-dark.svg`: off-white wordmark + orange ring mark), search icon, "Hans Muster" dropdown
6. **Create `SecondaryNav.tsx`** — light bar with 1px cell dividers; icon+label items; ACTIVE item = blue text/icon; badge pills (red = urgent count, gray = zero); back arrow `←` on screens 2–3; hamburger right

> **Checkpoint:** Open browser. Should see blue header + gray nav bar on white page.

### Phase 2: Dashboard (Screen 1)
7. **Create `data/clients.ts`** — dashboardClients array + dashboardSummary
8. **Create `FilterTabs.tsx`** — horizontal scrollable tabs with badge counts
9. **Create `DataTable.tsx`** — generic sortable table component. Props: columns, rows, onRowClick, sortConfig. Handles: checkboxes, red ×-circle + yellow !-triangle indicator columns, blue link cells, alternating row colors, sort arrows on headers, optional per-row trash icon
10. **Create `Pagination.tsx`** — `« Vorherige` (disabled state) + page buttons + `Nächste »` + results-per-page dropdown
11. **Create `SearchBox.tsx`** — input with magnifying glass icon
12. **Create `DashboardScreen.tsx`** — compose: Header → SecondaryNav → welcome row → FilterTabs → DataTable → Pagination
13. **Create `App.tsx`** — state machine: renders DashboardScreen by default, click client name → ClientScreen

> **Checkpoint:** Dashboard renders with 10 rows, tabs, pagination. Click a name → navigates.

### Phase 3: Client Detail (Screen 2)
14. **Create `data/tanja-bauer.ts`** — client + portfolios + beratungen
15. **Create `DonutChart.tsx`** — SVG donut. Props: size, strokeWidth, segments[{value, color}], centerText
16. **Create `GaugeChart.tsx`** — SVG semi-circle. Props: size, strokeWidth, percent, color
17. **Create `PortfolioCard.tsx`** — card with icon, ID, warning triangle, title, donut, gauge, CHF value, percent
18. **Create `ClientScreen.tsx`** — compose: Header → SecondaryNav → client header → portfolio tabs → card carousel → Beratungen section (DataTable + toolbar) → Pagination
19. **Wire navigation:** Dashboard client name click → ClientScreen with client data. Portfolio card click → PortfolioScreen.

> **Checkpoint:** Client screen renders with 3 cards and beratungen table. Card click navigates.

### Phase 4: Portfolio Analyse (Screen 3)
20. **Create `data/portfolio-analysis.ts`** — SAA entries, sidebar metrics, positions
21. **Create `SAATable.tsx`** — centered heading "Strategische Asset Allokation"; columns category/Min./Soll/Max./Portfolio/Aktion (right-aligned); UNDER each row a horizontal progress bar (gray track + category-color fill, width ≈ portfolio% scaled so 60% = full). Negative Aktion = plain dark text, NOT red
22. **Create `MetricWidget.tsx`** — renders different chart types based on `type` prop. For bar/line: simple SVG. For map: globe icon. For grid: grid icon. For icon: number list.
23. **Create `MetricsSidebar.tsx`** — 3-column CSS grid of MetricWidgets
24. **Create `PortfolioScreen.tsx`** — two-column layout: left (SAA section + donut + Positionsliste), right (MetricsSidebar). Positions table with expandable groups.
25. **Create `MetaBand.tsx` usage:** static label/value pairs (Portfolio / Anlagedienstleistung / Strategie) with vertical dividers + CHF right — NOT tabs. "Anlagetipp:" is an inline bold label, no callout box

> **Checkpoint:** All 3 screens fully rendered and navigable.

### Phase 5: Polish
26. **Hover states** — table row hover highlight, link underlines, button hovers
27. **Carousel dots** — dot indicators below portfolio cards
28. **Table toolbar** — edit button, dropdowns, search in beratungen section
29. **Expandable positions** — checkbox + category, indented sub-rows
30. **Responsive sanity** — ensure no horizontal overflow at 1400px

---

## 4. Key Implementation Details

### DataTable Component (most complex reusable piece)
```
Props:
  columns: { key: string; label: string; sortable?: boolean; width?: string; render?: (row) => ReactNode }[]
  rows: any[]
  onRowClick?: (row) => void
  showCheckboxes?: boolean
  showIndicators?: boolean    // red ×-circle + yellow !-triangle columns
  sortConfig?: { key: string; direction: "asc" | "desc" }
  onSort?: (key: string) => void
  pageSize?: number
  currentPage?: number
  onPageChange?: (page: number) => void
```

The table MUST support:
- Alternating row colors (white / `#F7F8FA`)
- Row hover → `#E8F0FE`
- Sort arrows on every column header (up/down, active column highlighted)
- Checkbox column (optional)
- Red ×-circle + yellow !-triangle indicators (optional, per-row booleans)
- Blue link cells (name columns)
- Trash icon on last column (optional, per-row boolean — absent on some rows)

### DonutChart (SVG)
```
- viewBox="0 0 100 100"
- Center at (50, 50)
- Radius: 40 (outer), strokeWidth: 8
- Each segment: <circle> with stroke-dasharray/stroke-dashoffset
- Rotate so first segment starts at top (-90deg)
- Multi-ring: multiple <circle> elements with decreasing radius
- Center text: <text> at (50, 50), textAnchor="middle", dominantBaseline="central"
```

### GaugeChart (SVG)
```
- viewBox="0 0 100 60"
- Center at (50, 55)
- Radius: 40, strokeWidth: 6
- Arc from 180deg to 0deg (bottom-left to bottom-right, going up)
- stroke-dasharray = circumference * percent / 100
- Color: #4A90D9
- Value text below arc
```

### Navigation State (in App.tsx)
```typescript
const [screen, setScreen] = useState<"dashboard" | "client" | "portfolio">("dashboard");
const [selectedClient, setSelectedClient] = useState<Client | null>(null);
const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio | null>(null);

// Dashboard → Client: click name in table
// Client → Portfolio: click card
// Back: breadcrumb or nav items
```

---

## 5. CSS Custom Properties (tokens.css)

Copy ALL values from `02-design-system.md` Section 1-4 into `:root {}` block. This is the single source of truth for colors, spacing, radii, shadows.

```css
:root {
  /* Brand */
  --primary: #4A90D9;          /* header bar, active buttons, solid buttons, SAA fill 1-2 */
  --primary-text: #5B9BD5;     /* active nav/tab text, links */
  --primary-light: #E8F0FE;    /* row hover */

  /* Neutrals */
  --bg-page: #F5F6F8;
  --bg-card: #FFFFFF;
  --bg-row-alt: #F7F8FA;
  --bg-nav: #F4F6F8;
  --bg-total-row: #D9D9D9;
  --bg-btn-inactive: #C4C8CC;
  --border: #D0D4D8;
  --track: #C9CED6;
  --text-primary: #1A1A1A;
  --text-secondary: #55595E;
  --text-muted: #9AA0A6;

  /* Semantic / badges */
  --danger: #E8564A;
  --warning: #F5C33B;
  --badge-dark: #3B4045;
  --badge-gray: #9AA0A6;
  --success: #8CC63F;

  /* SAA / chart categories */
  --chart-liquidity: #4A90D9;
  --chart-bonds: #4A90D9;
  --chart-stocks: #45B4E6;
  --chart-realestate: #45D0C5;
  --chart-other: #57D9A3;
  --chart-alert: #E8564A;

  /* Typography */
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  /* Radii */
  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 8px;
  --radius-pill: 999px;

  /* Shadows */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
  --shadow-header: 0 1px 2px rgba(0,0,0,0.1);
}
```

---

## 6. What NOT to Build

- No backend / API — all data is static mock
- No authentication — "Hans Muster" is hardcoded
- No real chart library — SVG only
- No mobile responsive — desktop only (1400px)
- No animations beyond hover states
- No real sorting logic — sort arrows are visual only (or basic client-side sort)
- No real pagination — show first page, buttons are visual

---

## 7. Acceptance Criteria

The mock is complete when:

1. All 3 screens render pixel-faithfully at 1400px width
2. Navigation works: Dashboard → Client → Portfolio (via clicks)
3. All German text matches screenshots exactly
4. Colors match the design system (within ~5% hex tolerance)
5. Tables have correct columns, indicators, alternating rows, sort arrows
6. Portfolio cards show donut + gauge charts
7. SAA table shows horizontal progress bars under rows; negative Aktion values are plain dark text
8. Metrics sidebar shows all 15 widgets with correct values
9. Pagination controls visible on all table screens
10. URO logo appears in header (use `uro-dark.svg` — off-white wordmark + orange ring mark)
