# X2 — House / CIO view

**Layer:** External (internal CIO publication in real life) · **Intelligence:** medium — matching ·
**Wave:** 1 · **Depends on:** `F5` · **Consumed by:** `R2`, `R3`, `R5`

## Purpose

Supply the bank's own investment opinion — what it currently favours and avoids — and relate it to each
client's actual exposures. This is what turns a fact into advice:

- Without it: *"You are 56% shares, your target is 75%."*
- With it: *"You are under your equity target — **and our house view is positive on equities**, so the
  gap is worth closing."*

## Why a mock is correct here

The brief explicitly sanctions this. `task_def.txt` lines 168–173 are a section titled *"External
Information Sources"*:

> *"Teams should also incorporate a sample strategic or tactical investment view from a bank. Publicly
> available investment reports, market outlooks or CIO publications from established financial
> institutions may be used as **mock inputs**."*

The real CIO view is confidential and is never provided. Any team treating this as a missing input is
misreading the brief.

## Build

1. **Pick one public source** — a quarterly outlook / house view from an established bank. Record the
   publisher, the document title and its date in the file itself.
2. **Convert it to a structured document** — `backend/app/external/data/house_view.json`:

```jsonc
{
  "source": "UBS CIO Global Wealth Management — «Market Outlook / Jahresrückblick 2025 und Ausblick 2026» (veröffentlicht Dezember 2025)",
  "source_url": "https://www.ubs.com/ch/de/wealth-management/chief-investment-office/market-outlook.html",
  "title": "UBS CIO Market Outlook 2026 — Marktausblick",
  "as_of": "2025-12-10",
  "mock": true,
  "disclaimer": "Mock-Eingabe zu Prototyp-Zwecken. Nicht als Anlageberatung zu verstehen. Die tatsächliche CIO-Sicht der Bank ist vertraulich und wird hier nicht abgebildet.",
  "stances": [
    { "dimension": "AssetClass", "category": "Shares",   "stance": "overweight",  "note": "…" },
    { "dimension": "CurrencyGroup", "category": "US-Dollar", "stance": "neutral", "note": "…" },
    { "dimension": "CountryGroup", "category": "North America", "stance": "…", "note": "…" },
    { "dimension": "Industry", "category": "Industrials", "stance": "…", "note": "…" }
  ]
}
```

   The file contains **28 stances** across the four SAA dimensions (AssetClass, CurrencyGroup, CountryGroup, Industry).
   `dimension` values must be one of the four `StrategicAssetAllocations[].Mappings[].Dimension` values,
   and `category` must match the **SAA vocabulary** — the same strings holdings are classified with.
3. **Match against the portfolio** — for each stance, find the client's actual weight in that category
   and the SAA target, and emit a `relation`:
   - For asset classes (which have SAA targets): `portfolio overweight` · `portfolio underweight` · `aligned` — these compare the portfolio's actual weight against **its own SAA target**, not the bank's stance.
   - For other dimensions (currency, country, industry — which lack SAA targets): `stance aligned` · `stance contrary` · `no target` — these compare the portfolio's positioning against the bank's directional view.
   Use `Securities[].SAA_AssetClassName` / `SAA_CurrencyGroupName` / `SAA_CountryGroupName` /
   `SAA_IndustryName`, matched to the `Mappings[].Category` of the same dimension.
4. Every match carries evidence: the actual weight, the target (when available), and the stance being compared.
5. **Declare it as mock everywhere it appears**, including in the briefing's provenance line. The final
   presentation must state *"which elements use mock data"* — that is the intended answer, not an
   admission. The `mock: true` flag and German disclaimer travel with every API response.

## Done when

- The structured house view loads and validates against the four SAA dimensions.
- For `CASE-007` the matcher produces a real relation (e.g. shares underweight against the stance).
- The mock disclaimer travels with the data into the API response and the briefing.

## Do not

- Scrape vast amounts of content — one credible document, structured properly, is the deliverable.
- Invent a house view without a real published source behind it; cite what you based it on.
- Leave a stance's `dimension` or `category` outside the SAA vocabulary — the match will silently fail.
- Present the view as UnRiskOmega's or the jury's bank's actual opinion.
