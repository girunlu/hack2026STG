# R4 — Storyline composer

**Layer:** Product (brief requirement 4 of 6: *"Create a coherent storyline"*) · **Intelligence:** high ·
**Wave:** 2 · **Depends on:** `R2`, `R3`, `R5` · **Consumed by:** `R6`, `B2`, `B3`

## Purpose

Turn ranked findings, market context and the house view into one connected story — not three separate
summaries glued together. The brief:

> *"The output should connect portfolio facts, market context and client information instead of presenting
> unrelated summaries from different sources."*

## Outputs

The briefing object in `PROJECT.md` §5.3 — three sections and four answers.

## The three sections (fixed titles)

1. **Recent Portfolio Development** — how it developed and what drove it
2. **Portfolio Health Check** — current state, issues requiring attention
3. **Portfolio Outlook & Next Best Actions** — relate to market and house view; concrete next steps

## The four questions (must be answerable)

`what_happened` · `situation` · `next` · `should_do`

These are the brief's framing. They map roughly onto the three sections but are not identical — section 3
covers both *"what could happen next"* and *"what should the advisor do"*. Populate `questions` explicitly
so the UI can show them as a compact strip without re-deriving anything.

## Two interchangeable renderers

```
R2 + R3 + R5  →  BriefingFacts   (deterministic)
                     ↓
            R4 renderer (a) template   ← build this first, needs no key
                        (b) LLM       ← drop-in replacement, needs a key
```

Both implement one function:

```python
render(facts: BriefingFacts) -> Briefing
```

`(a)` **template** — sentence templates filled from findings and evidence. Deterministic, testable,
no key. This is the version you demo unless a key arrives.

`(b)` **LLM** — pass the `BriefingFacts` as structured context with a prompt that requires: three
sections, four answers, no new facts, no numbers not present in the input, and an explicit statement of
anything unavailable. **Validate the output** against the same schema and fall back to `(a)` if it fails.

Swapping renderers must change **nothing** upstream.

## Build

1. Order the story by importance: the highest-scoring finding leads, not the chronologically first.
2. **Connect, don't list.** A sentence should link facts across sources — portfolio move + client note +
   market context + house view — rather than presenting one bullet per source.
3. **Every block carries `evidence_refs`.** A block with no evidence reference is a bug.
4. **Declare gaps.** Anything in `facts.meta.unavailable` or a portfolio's `data_gaps` gets stated plainly
   in the relevant section: *"risk profile unavailable"*, *"no market data for this position"*.
5. **Distinguish fact from context.** The brief requires it:
   *"Distinguish portfolio facts from external market context."* Label which sentences are portfolio
   facts and which come from news or the house view.
6. **Cite the house view as mock**, and include a provenance line: sources, as-of dates, and that the
   portfolio snapshot is simulated while news is live.
7. Target roughly 200–280 words total — that is what reads in ~60 seconds. Measure, don't guess.

## Done when

- `render(facts)` for `CASE-007` yields all three sections plus all four answers, every block evidencing.
- `CASE-027` (no price data) and `CASE-029` (no risk profile) state the gap explicitly.
- `CASE-028` (concentration only) does not invent violations or allocation drift to fill space.
- Renderer `(b)` produces the same schema as `(a)`; invalid LLM output falls back cleanly.

## Do not

- Let the LLM compute, round or infer a number. All figures come from `BriefingFacts` verbatim.
- Write generic filler — *"markets are volatile"*, *"diversification is important"*. The brief forbids
  *"generic or unsupported statements"*.
- Produce an observation with no action implication in the final section.
