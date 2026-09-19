# R2 — Context assembly

**Layer:** Product (brief requirement 2 of 6: *"Collect the relevant data"*) · **Intelligence:** none ·
**Wave:** 2 · **Depends on:** `F5`, `F6`, `X1`, `X2`, `B1` · **Consumed by:** `R3`, `R4`

## Purpose

Gather everything the briefing needs into one normalised object, before any judgement is made. It is the
single place that knows which sources exist — and, just as importantly, which ones are missing.

The brief's own words: *"The solution combines available client, portfolio, security, CRM, market-news
and house-view information."*

## Inputs

All four brief inputs, plus the orchestrator role for the whole pipeline:

- `F5` — client, portfolios, positions, securities, SAA targets, risk profile
- `F6` — notes, tags, overrides
- `X1` — market news, already linked to instruments
- `X2` — house view, already matched to exposures

## Outputs

```python
assemble(client_ref, portfolio_nr=None) -> {
  "client": {...},            # from F5 + F6
  "portfolios": [...],        # in scope
  "positions": [...],         # securities + accounts, with resolved security data
  "saa": {...},               # target allocation for the portfolio(s) in scope
  "violations": [...],        # reported as-is, never recomputed
  "proposals": [...],         # including status and dates
  "notes": [...], "tags": [...], "signals": [...],   # from F6
  "news": [...],              # from X1, may be empty
  "house_view": {...},        # from X2
  "gaps": [...],              # everything missing, explicitly declared
  "provenance": {...}         # sources, dates, which parts are mock
}
```

## Build

1. **Orchestrate the pipeline** for `POST /api/briefing`: assemble → `R3` → `R5` → `R4` → return.
2. **Declare gaps, never fill them.** If a risk profile is null (`CASE-029`–`CASE-032`), if
   `PerformanceYTD` is missing (all 57), if a security has no price (`SpaceX Aktie`), or if news failed
   to load — each goes into `gaps[]` with a reason. `R4` then states them in the briefing.
3. **Carry provenance** describing each source and its as-of date, including the fact that `X2` is a mock
   and that news is live while the portfolio is a simulated snapshot. The presentation must declare
   *"which elements use mock data"*.
4. Include **all** portfolios for a client when none is specified; a briefing may legitimately cover
   several. `CASE-028` has one, `CASE-001` has one, others have more.
5. Attach unresolved references from `F5.integrity_report()` that touch this client — `CASE-008`'s
   phantom portfolio IDs — as gaps, not as errors.
6. Keep this component free of judgement. No severity, no ranking, no wording. If you find yourself
   deciding what *matters*, that belongs in `R3`.

## Done when

- `assemble("CASE-007")` returns every key populated, with `gaps` empty except the known
  `PerformanceYTD` absence.
- `assemble("CASE-029")` reports the missing risk profile in `gaps`.
- `assemble("CASE-008")` reports the dangling portfolio references in `gaps` and completes.
- Works with the news service down — `news: []` plus a gap.

## Do not

- Compute figures here; take them from `F5`.
- Recompute or validate violations.
- Silently drop an input that failed to load.
