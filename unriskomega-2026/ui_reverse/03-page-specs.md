# URO Advisor Pro — Page Layout Specifications (v2, audit-corrected)

> Blueprint per screen. ASCII diagrams + positioning. All values verified against zoomed crops.

---

## Screen 1: Kundenberater-Dashboard

```
┌──────────────────────────────────────────────────────────────────────┐
│ [blue bar] (URO logo dark-svg)            🔍        Hans Muster ▾    │
├──────────────────────────────────────────────────────────────────────┤
│ Kundenberater-Dashboard │ 💼 Beratermappe │ 👥 Kundenliste(blue) │   │
│                         │ ⛔ Regelverletzungen (114) │ ⚠ Warnungen (21) │ ☰ │
──────────────────────────────────────────────────────────────────────┤
│ Willkommen zurück, Hans Muster                CHF 52'618'933.52      │
│ Pendente Beratungen: 215 | Restriktionen | Warnungen: 21             │
├──────────────────────────────────────────────────────────────────────┤
│ Meine Kunden                                                         │
│ [Kunden 45*][Neukunden 6][Beratungen 215][01-Liq>10% 112]            │
│ [02-Maturities 0][03-LastConsult>12M 191][04-RuleViol 28]            │
│ [05-Birthdays 13][Neu 146][Neu 146][Testsuche 5][Neu 146][Neu 146][+]│  🔍 Suche
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │☑ │⛔││Kundennr.│Name│Strasse/Nr.│PLZ/Ort│Geburtstag│Profilierung││ │
│ │  │  │  │67123-42 │Phillipp Abend │        │        │12.11.1964 ││ │
│ │  │⛔││209692-80│Mandy Baer     │        │        │04.01.1993 ││ │
│ │  │⛔││215129-14│Lucas Bauer    │        │        │14.08.1988 ││ │
│ │  │⛔││41839-29 │Tanja Bauer    │        │        │22.02.1936 ││ │
│ │  │  │  │176264-82│Bauer AG       │        │        │25.02.1978 ││ │
│ │  │⛔│  │29341-61 │Christian Bergmann│     │        │24.06.1989 ││ │
│ │  │⛔││236075-29│Tom Biermann   │        │        │13.08.1976 ││ │
│ │  │  │⚠│15103-68 │Ulrike Bohm    │        │        │03.06.1934 ││ │
│ │  │  │  │53143-87 │Stephanie Drescher│     │        │10.07.1967 ││ │
│ │  │  │  │127929-74│Karolin Ebersbacher│    │        │08.12.1960 ││ │
│ └──────────────────────────────────────────────────────────────────┘ │
│  « Vorherige  [1] 2 3 4 5  Nächste »            Resultate pro Seite ▾│
└──────────────────────────────────────────────────────────────────────┘
```

Notes:
- Nav row: title left; nav cells right with 1px vertical dividers; active = Kundenliste blue; red badge pills 114 / 21.
- Welcome band: stats line pipe-separated; **Restriktionen has no value**.
- Tab badges: charcoal pills, white digits; active tab (Kunden) blue text + blue underline + blue pill.
- Strasse / Nr. and PLZ / Ort columns are EMPTY in the source.
- Remaining columns per row (Profilierung | Geändert | Beratung):
  1. 19.04.2024 | 24.08.2026 | 24.08.2026
  2. 27.10.2020 | 14.08.2026 | 14.08.2026
  3. 08.05.2026 | 19.08.2026 | 19.08.2026
  4. 25.08.2026 | 10.09.2026 | 10.09.2026
  5. 21.06.2024 | 21.06.2024 | (blank)
  6. 23.04.2024 | 30.06.2025 | 23.04.2024
  7. 17.07.2024 | 07.07.2025 | 07.07.2025
  8. 23.06.2020 | 03.07.2025 | (blank)
  9. 17.07.2026 | 17.07.2026 | 17.07.2026
  10. 01.11.2024 | 20.12.2024 | 20.12.2024

---

## Screen 2: Einzelner Kunde (Tanja Bauer)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [blue header bar]                                                    │
├──────────────────────────────────────────────────────────────────────┤
│ Tanja Bauer (41839-29) │ 💼 Beratermappe │  Notizen (0) │           │
│                        │ 🥧 Vermögen(blue) │ ⛔ Regelverletzungen (4) │ │
│                        │ 👤 Kundeninformation │ ← │ ☰                │
├──────────────────────────────────────────────────────────────────────┤
│ Kundentyp            │ Kundenprofil                    CHF 1'497'989.49
│ Natürliche Person    │ Ausgeglichen                                  │
├──────────────────────────────────────────────────────────────────────┤
│ [Alle Portfolios*⚠][Eigene Portfolios⚠][Fremdbanken⚠][Konsolidierung][Beziehungen]
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                │
│ │👤 15.02996  ⚠ │ │👤 42.249999   │ │🏦 ZKB         │            ›   │
│ │Anlageberatung │ │Verwaltungsdepot│ │Anlageberatung │                │
│ │Portfolio |    │ │URO-Ausgewogen │ │Fokus | Keine  │                │
│ │Rendite (CHF)  │ │Standard (CHF) │ │Strategie (CHF)│                │
│ │ (donut)(gauge)│ │ (donut)(gauge)│ │ (donut)(gauge)│                │
│ │CHF 456'457 12%│ │CHF 1'041'533 8%│ │CHF 951    17% │                │
│ └───────────────┘ └───────────────┘ └───────────────┘                │
│                        ● ○                                           │
├──────────────────────────────────────────────────────────────────────┤
│ Beratungen                          [✏️blue] [Beratungsart ▾][Status ▾] 🔍
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │☑ ⛔ ⚠ Anlagedienstleistung│Container│Beratungsart│Beratung│Nr.│…  │ │
│ │   … 10 rows (see 04-data-models) …                               │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│  « Vorherige [1] 2 3 4 5 … 16 Nächste »        Resultate pro Seite ▾ │
└──────────────────────────────────────────────────────────────────────┘
```

Notes:
- Meta band: two label/value pairs with vertical divider; CHF right.
- Filter buttons: active blue fill; inactive GRAY fill; ⚠ badge on first three.
- Cards: person icon (own) / bank icon (ZKB); ⚠ only on card 1; 2 carousel dots.
- Beratungen: status column plain dark text; trash icon only rows 3,4,5,8,9,10.

---

## Screen 3: Portfolio Analyse

```
┌──────────────────────────────────────────────────────────────────────┐
│ [blue header bar]                                                    │
├──────────────────────────────────────────────────────────────────────┤
│ Tanja Bauer (41839-29) │ ☎ Telefonberatung │ 💼 Beratermappe │        │
│                        │ 🗒 Notizen (0) │ 🥧 Analyse(blue) │          │
│                        │ 👤 Kundeninformation │ ⓘ Portfolio │ ← │ ☰   │
├──────────────────────────────────────────────────────────────────────┤
│ Portfolio   │ Anlagedienstleistung      │ Strategie      CHF 456'456.98
│ 15.02996    │ Anlageberatung Portfolio  │ Rendite                    │
├───────────────────────────────────────────┬──────────────────────────┤
│ 🥧 SAA                            ⚙  ⛶   │ [3×5 widget grid]        │
│ Die Strategische Asset Allokation zeigt   │ SAA(red)│Suitab│Risiko/ │
│ die Aufteilung des Portfolios nach …      │ 12%     │12%   │Rendite │
│ … Diversifikation festlegt. Um eine …     │ Szenar  │ProdR │Länder  │
│ Anlagetipp: <regular text same line>      │ Branch  │Währ  │Fällig  │
│                                           │ Restr   │Perf  │Nachh   │
│      Strategische Asset Allokation        │ Ziel    │Emitt │PosList │
│  Liqu. / Geldmarkt  0.0% 5.0% 15.0% 1.5% 3.5%                        │
│  ▓▓░░░░░░░░░░░░░░░░░░ (blue ~3%)                                     │
│  Obligationen      35.0% 45.0% 55.0% 16.5% 28.5%                     │
│  ▓▓▓▓▓▓▓░░░░░░░░░░░ (blue ~28%)                                      │
│  Aktien            15.0% 25.0% 35.0% 59.1% -34.1%                    │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ (cyan ~100%)                                     │
│  Immobilien         0.0% 7.5% 17.5% 4.9% 2.6%                         │
│  ▓▓░░░░░░░░░░░░░░░░ (teal ~8%)                                       │
│  Übrige Anlagen     7.5% 17.5% 27.5% 18.0% -0.5%                     │
│  ▓▓▓▓░░░░░░░░░░░░░░ (green ~30%)                                     │
│            ( ( multi-ring donut ) )                                  │
│              456.5T                                                  │
│               CHF                                                    │
├───────────────────────────────────────────┴──────────────────────────┤
│ ⌄ Positionsliste                          [Fondssplitting deaktivieren]
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Total                                            456'456.98      │ │  ← gray band, bold
│ │ ⊟ Liqu. / Geldmarkt                              7'058.13  → 3.63%  1.55%
│ │   ⊟ Liquide Mittel                               7'058.13            1.55%
│ └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

Notes:
- Meta band = STATIC label/value pairs (Portfolio / Anlagedienstleistung / Strategie), NOT tabs.
- SAA bars: horizontal track+fill UNDER each row; negative Aktion plain dark.
- "Anlagetipp:" inline bold, no box.
- Positions header "Wert in CHF / Marchzins" = ONE column, two-line header.
- Aktion green "→ 3.63%"; PW "1.55%"; Total row gray band.
- Split button: solid blue, label exactly "Fondssplitting deaktivieren".

---

## Navigation Flow

```
Screen 1 ──click Name link──▶ Screen 2 ──click portfolio card──▶ Screen 3
   ▲                              │                                    │
   └──────────────────────────────┴────────────── ← back arrow ────────┘
```

## Responsive

Desktop-only (~1400px content). Tab bar and card row overflow horizontally. No mobile layout.
