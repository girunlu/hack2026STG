# URO Advisor Pro — Design System (v2, audit-corrected)

> Reverse-engineered from 3x-zoomed screenshot crops. Colors, typography, spacing, glyphs, states.

---

## 1. Color Palette

### Brand / Primary
| Token | Hex (approx) | Usage |
|-------|-------------|-------|
| `--primary` | `#4A90D9` | Top header bar bg; active filter button bg; active pagination page bg; solid action buttons ("Fondssplitting deaktivieren", edit pencil); SAA bar fill (Liqu/Obl) |
| `--primary-text` | `#5B9BD5` | Active nav item text+icon; active tab text; links in tables ("Beratung vom …", client names); "Nächste »" |
| `--primary-light` | `#E8F0FE` | Table row hover |

### Logo colors (from uro-*.svg, exact)
| Token | Hex | Usage |
|-------|-----|-------|
| logo text (dark variant) | `#F4F2EF` | `uro-dark.svg` wordmark — use on the blue header |
| logo text (light variant) | `#12100E` | `uro-light.svg` wordmark — use on white/light bg |
| logo mark orange | `#FF6B00` | ring mark segment 1 (both variants) |
| logo mark peach | `#FFA463` | ring mark segment 2 (both variants) |

### Neutrals
| Token | Hex (approx) | Usage |
|-------|-------------|-------|
| `--bg-page` | `#F5F6F8` | Page + meta band background |
| `--bg-card` | `#FFFFFF` | Cards, table container |
| `--bg-row-alt` | `#F7F8FA` | Alternating table rows |
| `--bg-nav` | `#F4F6F8` | Secondary nav bar |
| `--bg-total-row` | `#D9D9D9` | Positions "Total" row band |
| `--bg-btn-inactive` | `#C4C8CC` | Inactive portfolio filter buttons (gray fill, dark text) |
| `--border` | `#D0D4D8` | Table borders, input borders, nav cell dividers |
| `--track` | `#C9CED6` | SAA progress-bar track |
| `--text-primary` | `#1A1A1A` | Headings, values |
| `--text-secondary` | `#55595E` | Labels, metadata |
| `--text-muted` | `#9AA0A6` | Placeholders, disabled ("« Vorherige") |

### Semantic / Badges
| Token | Hex (approx) | Usage |
|-------|-------------|-------|
| `--danger` | `#E8564A` | Red badge pills (nav counts 114/21/4); red ×-circle indicator |
| `--warning` | `#F5C33B` | Yellow !-triangle indicator + button badges |
| `--badge-dark` | `#3B4045` | Inactive filter-tab badge pills (white digits) |
| `--badge-gray` | `#9AA0A6` | Zero-count badge pills (white digits) |
| `--success` | `#8CC63F` | Green Aktion text "→ 3.63%" |

### SAA / chart category colors (measured from bars)
| Category | Hex |
|----------|-----|
| Liqu. / Geldmarkt | `#4A90D9` |
| Obligationen | `#4A90D9` |
| Aktien | `#45B4E6` |
| Immobilien | `#45D0C5` |
| Übrige Anlagen | `#57D9A3` |
| SAA alert widget bg | `#E8564A` (red, white donut) |

---

## 2. Typography

- **Family:** system sans stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- **Scale:** 10px widget titles · 11–12px table cells/headers/labels · 13px body/descriptions · 14px card titles/buttons · 15–16px bold names/greetings · 18–20px bold CHF totals · 24–28px donut center value
- **Weights:** 400 default · 600 subheads/active · 700 headings, totals, "Total" row

---

## 3. Spacing / Layout / Radius / Shadow

| Element | Value |
|---------|-------|
| Header bar height | ~48px |
| Secondary nav height | ~40px (cells with 1px vertical dividers) |
| Meta band height | ~56px (two-line) / ~40px (one-line) |
| Table row height | ~36px |
| Portfolio card | ~340×180px, radius 8px, shadow `0 1px 3px rgba(0,0,0,.12)` |
| Sidebar widget | ~120×100px, radius 4px, 1px border |
| Content max width | ~1400px centered, 24px side padding |
| Spacing scale | 4 / 8 / 12 / 16 / 24 / 32 |
| Radii | 2px cells · 4px buttons/inputs/badges(pill=999px) · 8px cards |

Badge pills: height ~16px, padding 0 6px, radius 999px, font 10–11px white.

---

## 4. Indicator Glyphs (exact shapes)

| Glyph | Shape | SVG |
|-------|-------|-----|
| Rule violation | Filled red circle with white × inside | `<svg viewBox="0 0 12 12" width="12" height="12"><circle cx="6" cy="6" r="6" fill="#E8564A"/><path d="M3.8 3.8 8.2 8.2 M8.2 3.8 3.8 8.2" stroke="#fff" stroke-width="1.4"/></svg>` |
| Warning | Filled yellow triangle with white ! inside | `<svg viewBox="0 0 12 11" width="12" height="11"><polygon points="6,0 12,11 0,11" fill="#F5C33B"/><rect x="5.4" y="3" width="1.2" height="4" fill="#fff"/><rect x="5.4" y="8" width="1.2" height="1.2" fill="#fff"/></svg>` |
| Collapse (expanded group) | Square outline with minus | lucide `SquareMinus` 14px |
| Carousel dots | 8px circles: active `--primary`, inactive `#D0D4D8` | CSS |

---

## 5. Interactive / State Styles

| Element | Style |
|---------|-------|
| Nav item default | dark text+icon, cell with 1px right border |
| Nav item active | blue text+icon (`--primary-text`) |
| Filter tab active | blue text + 2px blue underline + blue badge pill |
| Filter tab inactive | dark text + charcoal badge pill |
| Portfolio button active | blue fill, white text/icon |
| Portfolio button inactive | gray fill `--bg-btn-inactive`, dark text/icon |
| Table row hover | `--primary-light` |
| Table row alt | `--bg-row-alt` |
| Link | `--primary-text`, underline on hover |
| Status text (Vorgeschlagen/Entwurf) | plain dark text — NO color distinction |
| Pagination current | blue fill, white digit |
| Pagination disabled (« Vorherige on p1) | `--text-muted` |
| Solid blue button | `--primary` bg, white text, radius 4px |
| SAA negative Aktion | plain dark text (not red) |
| Positions Aktion | green `--success` with leading "→" |

---

## 6. Chart Specs

- **Donut (card):** 80px, ring 8px, blue; center = CHF value.
- **Donut (SAA center):** ~200px, 5 concentric rings (category colors), ring 8px, gap 8px; center two lines: bold value + small "CHF".
- **Gauge:** 180° arc, 6px, blue; percent below.
- **SAA progress bar:** height ~8px, radius 2px; track `--track` full width; fill = category color, width ≈ portfolio% scaled so 60% ≈ full.
- **Mini bar chart (widgets):** 5–7 blue bars, no axes.
- **Line (Performance/Ziel):** thin blue polyline, optional ↑ prefix.
- **Scatter (Risiko/Rendite):** few blue dots.

---

## 7. Language & Formats

- All UI text German; do not translate.
- Numbers: Swiss format — apostrophe thousands separator, period decimal (`52'618'933.52`).
- Dates: `DD.MM.YYYY`.
- Percents in SAA/positions: one or two decimals with `%` (`16.5%`, `1.55%`).
