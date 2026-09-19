# R1 — Trigger

**Layer:** Product (brief requirement 1 of 6: *"Trigger the briefing"*) · **Intelligence:** none ·
**Wave:** 3 · **Depends on:** `F1`, `F3`, `R2` · **Consumed by:** `R6`

## Purpose

The advisor's entry point: a clear **Generate Briefing** action inside the mocked interface, the call to
the backend, and honest progress feedback while it works.

The brief's own words: *"The intended workflow begins with a simple advisor action, such as clicking a
Generate Briefing button within the client or portfolio view."*

## Inputs

- A client reference (`CASE-007`) and optionally a portfolio number
- `POST /api/briefing` → `{facts, briefing}`

## Build

1. **Placement:** a primary button on the client detail screen (`F3`), and on the portfolio view (`F4`)
   where it pre-scopes to that portfolio. Label it in German, matching the UI language.
2. **States — all four must exist:**
   - idle → button
   - running → the button disables and shows real stage progress, not a dead spinner
   - success → navigates to the briefing (`R6`)
   - failure → a legible error, and the app stays usable
3. **Report real stages**, because the pipeline genuinely has them and it makes the demo feel alive:
   *collecting client data · analysing portfolio · checking rules · retrieving market context ·
   composing briefing*.
4. The pipeline takes a few seconds; do not fake a delay, and do not hide it behind a generic spinner.
5. Pass through any provenance the backend returns so `R6` can display it.
6. Preserve the client context across the navigation — the briefing screen must know which client it is
   showing, and support going back.

## Done when

- Clicking Generate Briefing from `CASE-007` produces a briefing and lands on `R6`.
- Clicking it for `CASE-008` (dirty data) completes and shows declared gaps rather than an error.
- Killing the backend produces a readable error message, not a blank screen.

## Do not

- Block the whole UI while briefing runs.
- Show a progress percentage you cannot actually compute.
- Place the trigger somewhere the advisor would not naturally look — the brief says *"a clear entry
  point"*.
