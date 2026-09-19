# F6 — CRM context source

**Layer:** Frame (exists at URO as the bank's CRM) · **Intelligence:** low — deterministic extraction ·
**Wave:** 1 · **Depends on:** `F5` · **Consumed by:** `R2`, `R3`

## Purpose

Expose everything we know about the client that is *not* a number: advisor notes, interest tags and
personally overridden rules — and turn the notes into structured signals other components can use.

In real life this is the bank's CRM. Here the only source is `ClientNotes[]` and `Tags[]`, which is thin.
Everything extractable must be extracted, because this is what makes the briefing personal instead of a
spreadsheet.

## Inputs

- `clients.json` → `ClientNotes[]` (text + `CreatedByDateUTC`), `Tags[]`, `IndividualRuleOverrides[]`
- `reference.json` → `Tags[]` (all 19: 8 regions + 11 industries)

## Outputs — the contract (as built)

Each function takes the **client dict** (from F5), not a ref — passing a ref returns empty lists
silently, so always hand it the record:

```python
notes(client) -> [ {"index": int, "text": str, "date": str|None,
                    "duplicate_of": int|None, "source": str, "path": str} ]
distinct_notes(client) -> [ ...same rows, one per distinct text... ]
tags(client) -> { "region": [...], "industry": [...], "other": [...], "all": [...] }
overrides(client) -> [ {"rule_code": str, "description": str, "source": str, "path": str} ]
latest_activity(client) -> {"date", "source", "basis", "proposal_count", "note_count"}
liquidity_ratio(client) -> float | None
```

**Dedupe is `duplicate_of`, not a boolean**, and it is scoped per client: the repeats in this dataset are
*between* clients (153 notes, 53 distinct texts globally, **zero** clients repeat a text internally), so
in practice the field is always `null` on the delivered data. It stays because a client file with an
internal repeat must still be collapsible.

**The signal vocabulary lives in R3, not here.** `avoids_sector` / `liquidity_event` / `risk_attitude` /
`concentration_tolerance` are implemented as keyword rules inside `relevance.py`'s
`_preference_conflict`, `_liquidity_event` and `_concentration_tolerance`, because deciding that a note
*conflicts with a holding* is a judgement about the portfolio, and R3 is where judgements live. F6 stays
an extractor: notes, tags, overrides, recency, liquidity ratio.

## Build

1. Load and normalise through `F5`'s helpers — notes may be absent or null.
2. **Dedupe awareness:** 153 notes across 47 clients are only **53 distinct texts** — the pool repeats.
   Keep every occurrence and record which earlier note it repeats (`duplicate_of`).
3. Extract signals with explicit keyword rules (regex lists), not an LLM. Deterministic and testable.
4. Note the tension worth surfacing: a client can hold both an anti-fossil-fuel note and a conflicting
   holding — detecting that is `R3`'s job, not this component's. Here we only report what the notes say.
5. Do not summarise or paraphrase notes for display — quote them verbatim.

## Done when

- All 47 clients return a context object; clients with no notes return empty lists, not errors.
- `CASE-017` yields `avoids_sector` (fossil fuels) and `CASE-007` yields both `liquidity_event`
  (property within 12 months) and `income_need` (high-dividend focus).
- `CASE-001` yields `risk_attitude` ("unconcerned by short-term volatility") and a cash-reserve note.

## Do not

- Invent CRM fields that do not exist — there is no contacts list, no meeting log, no "last contacted"
  field anywhere in the data. Derive recency from note dates and proposals if the UI needs it.
- Treat a repeated note as new information from a different client conversation.
