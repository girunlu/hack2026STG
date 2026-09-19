# R5 — Next best actions

**Layer:** Product (brief requirement 5 of 6: *"Recommend next best actions"*) · **Intelligence:** high ·
**Wave:** 2 · **Depends on:** `R3` · **Consumed by:** `R4`, `R6`

## Purpose

Turn findings into concrete things the advisor could actually say or do during the call. The brief:

> *"The assistant proposes concrete and relevant actions that the advisor could consider during or after
> the client conversation."*

## Design decision — candidates are rules, wording is optional LLM

Generate the **candidate actions deterministically** from findings. Only the *phrasing* may use an LLM.
This keeps actions valid without an API key, and keeps them stable enough to test.

```python
candidates(findings)  -> list[Action]      # deterministic, no LLM
phrase(actions, facts) -> list[Action]     # optional LLM polish, falls back to raw text
```

## Action mapping

| Finding type | Candidate action |
|---|---|
| `rule_violation` | Resolve the specific breach before or during the call — cite the rule and the actual vs limit values |
| `allocation_drift` | Rebalance toward the agreed target; quantify the gap |
| `concentration` | Reduce the dominant position / diversify; quantify the weight |
| `preference_conflict` | Propose switching out of the holding that contradicts a standing client preference |
| `liquidity_event` | Confirm the cash need and its timing; keep suitable liquidity |
| `fx_exposure` | Address the currency concentration |
| `open_proposal` | Follow up on the pending or draft proposal |
| `performance_driver` | Explain the movement — is it isolated or market-wide? |
| `missing_data` | Obtain the missing input (e.g. a risk profile) |

## The constraint engine — this is what makes actions credible

Every candidate must be checked against the other findings before it is emitted:

- A `liquidity_event` finding **suppresses or reorders** any action implying illiquidity. Mary Poppins
  may need cash within 12 months — a proposal that locks money up is *wrong*, however good the allocation
  argument.
- A `preference_conflict` finding **suppresses** actions that add to the conflicting exposure.
- `concentration_tolerance` in the notes **softens** a reduce-concentration action — the client has
  explicitly accepted that risk; say so rather than pushing against a stated preference.
- A violation that is an `Error` outranks a merely underweight allocation.
- Never recommend a security the data does not contain, and never name a specific instrument unless it
  appears in the client's own positions or the recommendation list.

Emit at most **three** actions, highest priority first. The brief says surface what matters, not
everything.

## Output shape

```jsonc
{ "id": "a1", "priority": 1,
  "action": "Rebalance toward the agreed 75% equity target",
  "rationale": "Shares are 56.7% against a 75% target (30–100 range).",
  "finding_refs": ["f2"],
  "evidence": [ { "label": "…", "value": 0.567, "source": "…", "path": "…" } ],
  "suppressed_by": null }
```

`suppressed_by` records when a constraint removed or demoted an otherwise sensible action — useful for the
jury, and it proves the constraint engine is real.

## Done when

- `CASE-007` yields a rebalance action, a violation action, and does **not** propose anything illiquid.
- `CASE-028` yields a concentration action and nothing else — no invented violations.
- `CASE-017` yields a preference-driven switch, sourced from the note, which no rule engine reports.
- Every action cites at least one `finding_ref` and carries evidence.

## Do not

- Produce advice-shaped filler (*"review the portfolio regularly"*).
- Recommend a trade the data cannot support.
- Present an action that contradicts a client's stated preference without flagging the tension.
- Let the LLM add an action of its own. It may only reword the deterministic list.
