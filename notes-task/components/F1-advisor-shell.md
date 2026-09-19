# F1 — Advisor workspace shell

**Layer:** Frame (exists at URO as Advisor Pro) · **Intelligence:** none · **Wave:** 1
**Depends on:** — · **Consumed by:** `F2`, `F3`, `F4`, `R1`, `R6`

## Purpose

The mocked URO Advisor Pro chrome that everything else renders inside: header, navigation, layout
container, brand tokens and routing. In real life this already exists — we rebuild a convincing lookalike
so the demo is legible.

**The prototype is never implemented inside the live URO environment.**

## Inputs

- `unriskomega-2026/core-case/GUI-screenshots/` — three reference screenshots (see below)
- `unriskomega-2026/assets/logos/` — `uro-light.svg` / `uro-dark.svg` + partner marks

## Reference screenshots

| File | Resolution | What to lift from it |
|---|---|---|
| `Client_Advisor_DB.png` | 3422×963 | header, logo placement, user chip, nav tabs |
| `Client_DB.png` | 3413×1234 | client tabs row (`Alle Portfolios`, `Eigene Portfolios`, `Fremdbanken`, `Konsolidierung`, `Beziehungen`) |
| `Portfolio_DB.png` | 3413×1273 | sub-header (portfolio, service, strategy), right-hand metric rail |

## Build

1. **Sample the palette from the PNGs programmatically** — no stylesheet or token file was provided.
   Extract the background greys, the blue accent, the red violation/badge colour, and the muted text grey.
   Write them into a single theme file; every component uses those tokens, no ad-hoc colours.
2. Layout: fixed header (logo left, language switcher and user chip right) + horizontal nav + content area with a max width.
3. Router with routes for: advisor dashboard (`#/`), client detail (`#/client/{ref}`), portfolio view (`#/client/{ref}/portfolio/{nr}`), fremdbanken panel (`#/client/{ref}/fremdbanken`), briefing (`#/client/{ref}/briefing`), and creative briefing (`#/client/{ref}/creative`). All routes are hash-based for static hosting.
4. UI text is **bilingual — English by default, German on request** (`EN | DE` switch in the header,
   `?lang=de` on the API). The reference screenshots are German, which is why the vocabulary below is
   German and why the German mode is the visually faithful one: `Beratermappe`, `Notizen`, `Analyse`,
   `Kundeninformation`, `Portfolio`, `Kundenberater-Dashboard`, `Beratungen`, `Positionsliste`,
   `Fremdbanken`, `Konsolidierung`, `Beziehungen`. The three briefing section titles keep the brief's
   English wording in both languages.
5. Header shows the advisor identity (`Hans Muster` in the screenshots) and, on client screens, that
   client's total. Currency format: `CHF 456'456.98` — Swiss thousands separator (`'`), not a comma.
6. Provide light **and** dark handling using the `*-light` / `*-dark` logo pairs.
7. **Client-scoped badges** — when viewing a client, the nav shows badge counts for that client's notes and violations (not the global counts). The `ClientBadges` component publishes these via `ShellContext`.
8. **Error boundary** — the root wraps the app in an `ErrorBoundary` component that catches render crashes and shows a localized error panel instead of blanking the screen (WEBSITE-BUGS.md #1 fixed).

## Done when

- A shell renders with header, nav and routed content area, styled from sampled tokens.
- Light and dark both look intentional; the correct logo variant loads in each.
- Layout survives 1366 px width without horizontal scrolling (judges' screens are rarely 4K).

## Do not

- Invent a design system beyond what the screenshots show. Copy what is there.
- Hard-code colours inside components — all from the theme file.
- Use the URO logo in a way that suggests this is a real UnRiskOmega product; it is a mock for a
  hackathon demonstration.
