# URO Advisor Pro — UI Reverse-Engineering Package (v2, audited)

> Complete specification to rebuild the URO Advisor Pro mock interface from screenshots.
> **No images required.** All visual information is encoded in the documents below.
> v2 = independently audited against 3x-zoomed screenshot crops; see `07-audit-report.md` for the 43 corrections.

---

## Read order for a cold builder

| # | File | Purpose |
|---|------|---------|
| 1 | [`01-component-table.md`](./01-component-table.md) | Every UI component, exact nav items/badges/tabs per screen |
| 2 | [`02-design-system.md`](./02-design-system.md) | Colors (measured), typography, spacing, indicator glyphs, states, chart specs |
| 3 | [`03-page-specs.md`](./03-page-specs.md) | Per-screen ASCII blueprints + exact row data |
| 4 | [`04-data-models.md`](./04-data-models.md) | TypeScript interfaces + exact mock data (verified values) |
| 5 | [`05-implementation-guide.md`](./05-implementation-guide.md) | Tech stack, file tree, 30-step build order, tokens.css, acceptance criteria |
| 6 | [`06-asset-manifest.md`](./06-asset-manifest.md) | Logo variants + exact colors, lucide icon map, indicator SVGs |
| 7 | [`07-audit-report.md`](./07-audit-report.md) | What was wrong in v1, what is verified now, residual uncertainties |

`_audit_crops/` holds zoomed screenshot crops used during verification — **not needed for building**.

---

## What's in the mock

3 German desktop screens (~1400px):

1. **Kundenberater-Dashboard** — welcome band, 13 filter tabs with badge pills, 10-row sortable client table with ×-circle/!-triangle indicators, pagination.
2. **Einzelner Kunde (Tanja Bauer)** — meta band, 5 gray/blue portfolio filter buttons, 3-card carousel (donut+gauge), Beratungen table (10 rows).
3. **Portfolio Analyse** — meta band, SAA section (description + Anlagetipp + allocation table with progress bars + multi-ring donut), 15-widget metrics sidebar, expandable Positionsliste.

Navigation: Dashboard →(name link)→ Client →(card click)→ Portfolio; back via `←` in nav.

---

## Source material

- Screenshots: `../core-case/GUI-screenshots/` (3 PNGs)
- Logos: `../assets/logos/uro-{light,dark}.svg`
- Real data schema: `../core-case/portfolio-data/clients.json`, `reference.json`
- Constraint: mocked URO Advisor Pro interface, not the live system
