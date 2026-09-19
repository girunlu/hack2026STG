# B3 — Creative briefing format

**Layer:** Bonus (brief: *"Creative Briefing Format"*) · **Intelligence:** none · **Wave:** 4
**Depends on:** `R6` · **Consumed by:** —

## Purpose

An original presentation of the same briefing that helps the advisor absorb it faster.

The brief:

> *Explore an original format that helps the advisor absorb the briefing quickly. Possible formats include:
> a structured visual briefing card, a conversational interface, a voice briefing, prioritized alerts and
> action cards, or a combination of text and data visualization. The format should improve usability and
> remain appropriate for a professional wealth-management environment.*

## Inputs

The briefing object (`PROJECT.md` §5.3) — unchanged. This is an alternative **rendering** of `R6`, not a
second briefing engine.

## Build

**As built (2026-09-19):** Three-act storyline with timeline spine. The implementation chose a structured visual briefing card with a timeline showing the seven pipeline stages (collect, analyse, rules, market, house_view, actions, compose). Each stage shows its status (pending/running/done/error) and elapsed time. The briefing renders the same three sections and actions as R6, with evidence expandable inline. Optimised for print and 60-second reading.

A workable design:

- A timeline spine showing the seven pipeline stages with real elapsed time (not a fabricated animation)
- The three briefing sections rendered as cards, ordered by finding severity
- Expandable evidence inline — click a finding to reveal its `evidence[]` array
- Print-optimised layout with proper page breaks
- The 60-second constraint still applies. A prettier 3-minute briefing is a worse briefing.

Other acceptable choices, if the team prefers: a conversational walkthrough, or a short voice summary
generated from the same text (state which voice/API, and that it is synthetic).

## Done when

- The format renders the same three sections and the same actions as `R6` — no new or different content.
- It is reachable from `R6` (a toggle), not a separate app. Route: `#/client/{ref}/creative`.
- A reviewer can still get from any claim to its evidence (expandable inline).
- It is appropriate for a professional wealth-management context — no gamification, no cartoon styling.
- The timeline shows real stage progression with elapsed time, not a fabricated animation.

## Do not

- Reorder by anything other than the real priority score.
- Introduce facts, numbers or actions that `R6` does not have.
- Sacrifice traceability for looks.
- Use animation that delays the advisor. The whole point is speed.
