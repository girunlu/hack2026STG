# X1 — Market news service

**Layer:** External (licensed feed in real life) · **Intelligence:** medium — relevance linkage ·
**Wave:** 1 · **Depends on:** `F5` · **Consumed by:** `R2`, `R3`

## Purpose

Fetch current market news for the instruments a client actually holds, and attach it to those
instruments. The brief is explicit that an unfiltered market summary is worthless:

> *"The market information should be filtered according to its relevance to the client's actual
> holdings and portfolio exposures. A general market summary without a clear connection to the portfolio
> provides limited value."*

This module does the **first-pass linkage**. Deciding whether an item *matters for this client* is `R3`.

## Inputs

- Held securities from `F5` — real ISINs, names, `SAA_IndustryName`, `CountryName`, `Currency`

## Build

1. **Query resolution — no tickers, and no symbol table.** The data gives bank-style German instrument
   names, which are not what a news search expects. `_clean_query_name()` strips the instrument-type
   preamble and share-class noise, then the ISIN is the fallback when nothing meaningful survives:
   - preambles are matched as **phrases, longest first**, because the German share-class preamble is
     several tokens long (`"Na. u. Inh. Ti.-Aktie ASML Holding NV"` → `ASML Holding NV`). A
     single-token compare cannot see a four-token phrase — that bug cost ASML 4 of its 5 headlines
     (`REVIEW.md` §4.13); 13 master rows carried it;
   - only a **leading** preamble is stripped, never a substring: `Stanserhorn-Bahn-Aktiengesellschaft`
     keeps its name;
   - share-class and currency tokens (`-A-`, `CHF`, `acc`, `dist`, …) are dropped wherever they appear.
2. **Provider chain: Bing News RSS → Google News RSS → Yahoo Finance RSS** (the source the brief names
   is the last fallback). Verified from this network: Google's RSS returns HTTP 200 with an **empty
   body** for every query and Yahoo returns 0 items for `VZN.SW`, so a single-provider design would
   have looked verified while returning nothing. 6 s timeout per provider, 0.4 s politeness delay,
   a disk cache with a 6 h TTL (cache-primary inside it, so repeat briefings are stable and fast), and
   a wall-clock deadline for the whole batch — spent budget declares the remaining holdings
   unavailable instead of stalling the briefing.
3. **Link each item** to what it touches:
   - `linked_security_ids` — a headline about VZ Holding links to that security
   - `linked_sectors` — an industry-level headline links via `SAA_IndustryName`
   - `linked_currencies` — via `CurrencyGroupName` / position currency
   - `relevant_because` — one sentence, e.g. *"Client holds 95.9% VZ Holding."*
4. **Unresolvable instruments are reported, not guessed.** `SpaceX Aktie` (`US84615Q1031`) is a private
   company with no public price or news. It must appear as *"no market data available"*, never as an
   invented headline. This is a feature, not a gap.
5. **Failure must never break the briefing.** If the fetch fails, return an empty list plus a reason;
   the briefing still renders, with market context declared unavailable.
6. **Order by the holding, not by the clock.** Items come back biggest-position-first, newest within
   one position (`_item_weight`). R4 renders the first items, so a date-only sort handed SCEN-001's
   lead market line to an 18% position while the 62% one waited below it. Both sort passes are stable,
   so the order stays deterministic for the harness.
7. **Age filter.** Items older than 365 days are dropped; a security whose every item was dropped is
   declared unavailable *"no coverage in the last 12 months"* rather than silently empty.

## Provenance warning — read this

The portfolio data is a **simulated snapshot dated 2026-09-03** (`data_as_of`; the performance series
ends 2026-07-01). Live news comes from the real current date. The two timelines do not match.

Therefore every news item must carry its own `published` date and a provenance note, and the UI must not
imply the news is contemporaneous with the portfolio snapshot. Say so plainly in the briefing's
provenance line — mixing simulated and real data silently is the kind of thing a judge will catch.

## Done when

- For `CASE-028` (95.9% VZ Holding) at least one real, current headline is returned and linked.
- For `CASE-027` the private line (`SpaceX Aktie`, `US84615Q1031`, `SecurityId -900001`) is an explicit
  *"private instrument without public market data"* — while its two **listed** holdings still return real
  headlines. It is a per-line refusal, not a silent one, and not a whole-client refusal.
- A network failure produces an empty list plus a reason, and the caller does not crash.

## Do not

- Emit general market summaries as though they were client-relevant.
- Invent a headline, a price, or a date.
- Let a news failure fail the briefing.
- Add a hard dependency on a third-party key — that would make the demo fragile.
