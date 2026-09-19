# URO Advisor Pro — Audit Report (external verification of this package)

> The v1 package was re-verified line-by-line against the source screenshots by an independent pass.
> Method: (a) vision-submodel OCR of full screenshots, (b) direct read of full screenshots, (c) **3x LANCZOS-upscaled crops of every disputed region** (tie-breaker, highest fidelity), (d) SVG source inspection for logos.
> Where (a) and (b) disagreed, (c) decided. All corrections below are applied to files 01–06 (now v2).
> Crop evidence retained in `_audit_crops/` (not needed for building).

---

## 1. Errors found in v1 and corrected in v2

### Screen 1 — Dashboard
| # | Item | v1 (wrong) | v2 (verified) |
|---|------|-----------|---------------|
| 1 | Nav item 2 label | "Kundendatei" | **Kundenliste** (active, blue) |
| 2 | Regelverletzungen badge | 21 / 104 | **114** |
| 3 | Tab badge "Kunden" | 107 | **45** (active tab, blue pill) |
| 4 | Tab badge "Neukunden" | 0 | **6** |
| 5 | Tab badge "01 - Liquidity > 10%" | 102 | **112** |
| 6 | Tab badge "02 - Maturities" | 6 | **0** |
| 7 | Tab badge "03 - Last Consultation…" | 109 | **191** |
| 8 | Tab badge "04 - Rule Violations" | 21 | **28** |
| 9 | Tab badges "Neu" / "Testsuche" | 106 / 3 | **146 / 5** |
| 10 | Badge pill style | gray circle | **charcoal pill, white digits; active tab = blue pill** |
| 11 | Welcome stat "Restriktionen" | value 21 | **no value (blank)** |
| 12 | Pagination left label | "Seitennr.:" | **« Vorherige** (disabled) |
| 13 | Row 1 indicators | red+yellow | **none** |
| 14 | Row 1 name | "Philipp Abend" | **"Phillipp Abend"** |
| 15 | Row 2 indicators | red only | **red + yellow** |
| 16 | Row 3 ref / name | 215129-34 / Lucia | **215129-14 / Lucas Bauer** |
| 17 | Row 3 indicators | yellow only | **red + yellow** |
| 18 | Row 4 indicators | none | **red + yellow** |
| 19 | Row 5 profiling / consultation | 2026-06-21 / 2026-06-21 | **2024-06-21 / blank** |
| 20 | Row 6 last-changed | 2024-04-23 | **2025-06-30** |
| 21 | Row 8 indicators / dates | none / 2025-03-07 both | **yellow only / changed 2025-07-03, consultation blank** |
| 22 | Red indicator glyph | plain dot | **filled circle with white ×** |
| 23 | Yellow indicator glyph | plain triangle | **triangle with white !** |
| 24 | Address columns | unspecified | **empty in source** |

### Screen 2 — Client
| # | Item | v1 (wrong) | v2 (verified) |
|---|------|-----------|---------------|
| 25 | Nav badges/active | unspecified / — | **Notizen gray 0; Vermögen active; Regelverletzungen red 4; back arrow** |
| 26 | Inactive portfolio buttons | white + border | **gray fill `#C4C8CC`** |
| 27 | Warning badge on buttons | unspecified | **on Alle Portfolios, Eigene Portfolios, Fremdbanken only** |
| 28 | Card 3 icon | person | **bank/building** |
| 29 | Beratung Nr middle segment | 349514251 | **349514351** |
| 30 | Status styling | Vorgeschlagen = blue link | **both statuses plain dark text** |
| 31 | Trash icon | rows 3–10 | **rows 3,4,5,8,9,10 only** |

### Screen 3 — Portfolio
| # | Item | v1 (wrong) | v2 (verified) |
|---|------|-----------|---------------|
| 32 | Band under client name | clickable tabs | **static label/value pairs (Portfolio / Anlagedienstleistung / Strategie)** |
| 33 | Nav badges/active | unspecified | **Notizen gray 0; Analyse active; back arrow** |
| 34 | SAA color marks | vertical chips before names | **horizontal progress bars UNDER each row (gray track + colored fill)** |
| 35 | SAA negative Aktion | red | **plain dark text** |
| 36 | "Anlagetipp:" | boxed callout | **inline bold label, same line** |
| 37 | Split button label | "Fonds-Splitting deaktivieren" | **"Fondssplitting deaktivieren"** (solid blue) |
| 38 | Positions Aktion value | 3.679 | **→ 3.63% (green)** |
| 39 | Positions PW value | 1.5% | **1.55%** |
| 40 | "Wert in CHF / Marchzins" | ambiguous | **one column, two-line header** |
| 41 | Widget types | gauge/line guesses | **Risiko/Rendite = scatter; Performance = line+↑; Zielerreichung = target icon** |

### Assets
| # | Item | v1 (wrong) | v2 (verified) |
|---|------|-----------|---------------|
| 42 | Header logo file | uro-light.svg | **uro-dark.svg** (wordmark `#F4F2EF`); uro-light.svg wordmark is `#12100E` (light bg only) |
| 43 | Logo description | "white geometric mark" | **ring mark orange `#FF6B00` + peach `#FFA463`** (from SVG source) |

---

## 2. Residual uncertainties (unresolvable from pixels — builder guidance)

1. **SAA description tail** — paragraph truncates at the right edge of the screenshot after "…Branchenallokation darzustelle". v2 includes the verified prefix; complete the sentence plausibly in German.
2. **Anlagetipp sentence** — not legible at source resolution; write a plausible German advisory sentence after the bold inline label.
3. **Positions rows 4–13** — screenshot cuts off after "Liquide Mittel"; fabricate 10 more rows consistent with `reference.json` securities so the "13 Positionen" widget stays truthful.
4. **Exact hex values** — measured from compressed PNGs; treat as ±3 tolerance. Structural geometry and all text/values are exact.
5. **Sort-arrow direction per column** — arrows present on all headers; default state unspecified. Render inactive `ChevronsUpDown` everywhere.

---

## 3. Cross-file consistency check (v2)

- Component IDs (G-*, D1-*, D2-*, D3-*, M-*) referenced consistently in 01 ↔ 03 ↔ 05. ✔
- Tab/badge/nav counts identical in 01 and 04. ✔
- Color tokens identical in 02 and 05 (`tokens.css` block). ✔
- Indicator SVGs identical in 02 and 06. ✔
- Logo guidance identical in 02, 05, 06 (uro-dark.svg on header). ✔
- Data values (rows, Nr., dates, SAA, widgets) identical in 01, 03, 04. ✔
- Navigation flow and AppState identical in 03, 04, 05. ✔
