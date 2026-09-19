# B2 — Follow-up Q&A

**Layer:** Bonus (brief: *"Interactive Follow-Up Assistant"*) · **Intelligence:** high · **Wave:** 4
**Depends on:** `R2`, `R3`, `R5` · **Consumed by:** — (sits alongside `R6`)

## Purpose

Answer the advisor's follow-up questions from the information already collected — grounded, evidence-backed,
and honest when the answer is not available.

The brief's example questions:

> *What is the client's total semiconductor exposure? · Has the client previously raised concerns about
> volatility? · Which positions contribute most to the current risk? · How would a proposed rebalancing
> affect the portfolio allocation? · Which open proposal is most relevant to this conversation?*

## Inputs

The `BriefingFacts` bundle — the same evidence `R4` and `R6` use. **Not** the raw JSON, and **not** the LLM's
memory.

## Two answer paths

**1. Deterministic answers for structured questions.** Most of the brief's examples are computable, and
computing them is better than generating them:

| Question shape | How to answer |
|---|---|
| Total exposure to a sector/region/currency | Sum weights of positions whose `SAA_*IndustryName` etc. matches — the same join `R3` already performs |
| Which positions drive risk | Rank by `ContributionVolatility` (sums to portfolio volatility — verified) |
| Effect of a rebalancing | Recompute the allocation with the proposed weights; show before/after per category |
| Which proposal matters most | Rank by status then date: drafts and pending items over closed ones |
| Prior concerns about volatility | Search `F6` notes for `risk_attitude` signals, quote them verbatim |

These need no key and must work without one.

**2. Free-form answers** — optional, LLM-rendered from `BriefingFacts` only.

**3. The analysis digest — what the platform holds when the question matches no section.** A question the
router cannot place ("what are the strong parts of this investment case?", "is the client happy with the
portfolio?") is answered with the client's own analysis: the most urgent findings and the next actions,
named as the briefing names them, under a plain statement that no section answers the question directly.
Never empty, and never the open web — a generic article about how to build an investment case reads as an
answer that missed the point. The scope is declared in `unavailable` as *"the question itself is not
covered by the bank's data"*; the classifier's own state is not something to tell an advisor.

**Which questions belong on the web** is decided by frame, not by whether the keywords matched. A
question is out of frame when it is an instrument question the client's data cannot answer, or when it
names a proper noun the client's context does not carry (`_unknown_entities`: "is NVIDIA worth
investing?" — NVIDIA appears nowhere in this client's data, so the bank cannot answer it). Everything
else stays in frame: `_answer_web` runs only for those, only after the model has had the client's context
(an instrument question reaches the web when the model *declines* it), and never when no key is configured
— without one, the routed answer stays in charge. A public answer carries no bank evidence: its rows are
cleared, because the sources are its provenance.

## Rules

- **Answer only from `BriefingFacts`.** If the answer is not there, say so explicitly and name what is
  missing. The brief: *"The answers should remain grounded in the available data and clearly indicate when
  the information required for an answer is unavailable."*
- **Return evidence with every answer** — the same `evidence[]` shape, so the UI can show the working.
- **No number may be computed by the LLM.** If a question needs arithmetic, a deterministic function does
  the arithmetic and the LLM only phrases the result.
- **Quote notes verbatim** when answering about client preferences; do not paraphrase them into opinion.
- Some questions have no answer in this dataset — for example anything requiring performance attribution.
  Refuse plainly: *"The data does not contain position-level performance history."*

## The intent router (as built, 2026-09-19)

`_classify()` is only the fallback: a question is first checked against the data's own vocabulary and
against the brief's own example questions, because "true but unresponsive" is a failure mode.

| Question shape | Routed to | Basis |
|---|---|---|
| Names a sector/region/currency **and** asks for an exposure ("total semiconductor exposure") | `_answer_exposure` | `metrics.exposure(..., split_funds=True)`; the vocabulary is the data's industry/country/currency groups plus a **declared** synonym map (semiconductors → Information Technology, since the data carries 12 GICS sectors and no sub-industry). The mapping is stated in the answer. Currency questions now answer from real exposure rows, not just findings |
| Risk **plus** a position/contribution word ("which positions drive the risk?") | `_answer_risk_contribution` | `metrics.risk_contributions` (cleaned series), top 3 by share of volatility, evidence per position |
| Asks what the client said/wants/avoids | `_answer_notes` | notes quoted verbatim; if no note's own words match, R3's note-derived findings supply the note they cite; otherwise the notes are listed and the gap declared |
| Proposal + open/relevant/pending | `_answer_proposal_followup` | newest `Entwurf` (or the newest closed one, saying so); an undated draft is reported as undated, never with a placeholder date |
| Rebalancing *effect* | `_answer_allocation` (SAA branch) | the largest actual-vs-target gaps, i.e. what a rebalancing would actually move |
| Rule violations ("which rule violations are open?") | `_answer_rules` | routes to `facts.violations`, not proposals. The word "open" appears in both PROPOSAL_KEYWORDS and PROPOSAL_FOLLOWUP_KEYWORDS, so RULE_KEYWORDS is checked first |
| Questions about unanswerable topics (e.g. "the private equity allocation of the client's holiday home") | refused | `_is_unsupported()` detects questions that combine asset-class words with non-portfolio subjects and refuses rather than answering confidently from the wrong context |
| Everything else | the original keyword families | unchanged |

**In flight:** instrument-candidate answers (e.g. "which semiconductor stocks could I buy?") will route to `facts.instrument_candidates` once the R5 action and R4 block that name instruments are merged. Not yet documented as built.

All five example questions in `task_def.txt` are covered by tests
(`test_briefing_contract.py::test_brief_example_questions_are_answered_or_refused`), each asserting either
a grounded answer with evidence or an explicit refusal naming what is missing.

## Done when

- Each of the five example questions in the brief returns a grounded answer **or** an explicit, specific
  refusal.
- Every answer displays its evidence.
- A question about a client with missing data (`CASE-029`, no risk profile) states that limitation.
- With no LLM key, path 1 still answers the structured questions correctly.

## Do not

- Answer from general market knowledge.
- Invent a number to be helpful.
- Say *"I don't know"* without naming what is missing and where it would come from.
