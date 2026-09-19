# T1 — Regression harness

**Layer:** Internal (not a deliverable — but the thing that keeps the demo alive) · **Intelligence:** none ·
**Wave:** 1 (build early, extend continuously) · **Depends on:** `F5`, `R2`, `R3`, `R5`, `R4`

## Purpose

Run the whole pipeline headlessly across **all 47 clients** and check the invariants. This is the real test
suite: it catches the moment a change breaks a client you were not looking at, and it is what makes the
"unseen test client" drill safe.

## Inputs

- The pipeline entry point (call `R2`/`R3`/`R5`/`R4` directly in Python — no HTTP needed)
- A committed snapshot directory: `backend/tests/snapshots/{ClientRef}.json`

## Build

1. **Run all 47 clients**, write each `BriefingFacts` + `Briefing` to a snapshot file.
2. **Assert invariants** on every run:

   - All 47 complete with no exception.
   - Three sections present, with the brief's exact titles.
   - Four `questions` keys present and non-empty.
   - Every finding has non-empty `evidence[]` with `label`, `value`, `source`, `path`.
   - Every briefing block has non-empty `evidence_refs` resolving to a real finding.
   - At most 3 actions; each cites at least one `finding_ref`.
   - **No `IBAN`** appears anywhere in the output (serialise and regex the whole payload).
   - Total briefing word count within the target band (200–280).
   - **Determinism:** running twice produces byte-identical output for every client.
   - No finding claims performance attribution (guard the wording).

3. **Known-case assertions** — the clients with specific required behaviour:

   | Client | Must hold |
   |---|---|
   | `CASE-007` | rebalance action present; **no** illiquid action (property note) |
   | `CASE-028` | concentration finding; **zero** invented violations |
   | `CASE-027` | declares missing market data for its dominant position |
   | `CASE-029` | declares the missing risk profile |
   | `CASE-008` | completes; declares the dangling portfolio references |
   | `CASE-017` | preference conflict present |
   | `CASE-012` | FX exposure finding present |

4. **Diff against snapshots** to show what a change altered. Print a readable summary: clients changed,
   findings added/removed, actions changed.
5. Add a `--client CASE-007` flag for fast single-client iteration.

## Done when

- One command runs all 47 clients and prints a clear pass/fail with the failing assertions named.
- Deliberately breaking a renderer makes it fail loudly rather than silently degrading.
- The whole run takes seconds, not minutes — it will be run constantly.

## What the suite enforces today (built 2026-09-19)

`tests/` runs **110 tests + 1 skipped** (`--run-harness`). Per file:

| File | Tests | Covers |
|---|---|---|
| `test_f5_contracts.py` | 16 | load counts as literals, absent-vs-null handling, integrity as data, the hand-checked returns/SAA numbers, look-through units, `redact`, and an IBAN scan across every F2/F3/F4 response |
| `test_relevance.py` | 18 | **all 15 finding types fire** (concentration, allocation_drift, rule_violation, risk_alignment, preference_conflict, liquidity_event, performance_driver, open_proposal, fx_exposure, stale_data, missing_data, material_change, pending_task, reinvestment, sector_concentration), every draft surfaces, one note never speaks twice, cash is never an allocation drift, the trade window recomputed independently, determinism of findings |
| `test_briefing_contract.py` | 16 | **all 47 briefings**: three sections with the brief's titles, four answered questions, every block traceable, ≤5 action candidates each citing findings, the word band, declared gaps, no IBAN, no attribution wording, content determinism, and the language switch (numbers equal, words differ) |
| `test_risk_guard.py` | 5 | the overflowing `ContributionVolatility` is detected, withheld from the API, declared as a gap, and never claimed by R3's risk driver — across all portfolios |
| `test_client_upload.py` | 7 | the unseen-client drill |
| `test_excustody_binding.py` | 5 | the import→briefing path |
| `test_harness.py` | 2 (one skipped) | the 47-client snapshot drill and `--diff` |
| `test_candidates.py` | 12 | named buy/sell/switch candidates from draft proposals and recommendation-list members |
| `test_news_fixes.py` | 13 | German share-class preamble stripping, provider chain, age filter, biggest-holding-first ordering |
| `test_qa_fixes.py` | 4 | Q&A routing: currency from exposure rows, holiday-home refusal, violation questions route to `facts.violations` |
| `test_bugfix_regressions.py` | 8 | website-bug regressions from WEBSITE-BUGS.md |
| `test_metrics_returns.py` | 4 | returns computation from PerformanceHistory |

**15 finding types** are now in flight (the 14th, `sector_concentration`, was added 2026-09-19; a 15th, `esg_alignment`, is planned but not yet merged). The suite enforces that every type fires across the 47 clients.

No test touches the network: `conftest` sets `URO_NEWS_OFFLINE=1` (plus isolated `URO_UPLOAD_DIR` /
`URO_EXCUSTODY_DIR`), so market lookups declare themselves unavailable and the run is reproducible.
