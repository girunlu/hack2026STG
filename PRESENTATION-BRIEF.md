# Presentation brief — "From Ping to Pitch" (UnRiskOmega hackathon)

**What this file is:** a complete input for an AI presentation generator (Claude / ChatGPT / Gamma /
python-pptx). Everything needed to build the deck is here. Nothing else has to be read.

**What to produce:** a **2–3 minute** slide deck (16:9), ~8 slides, plus optional appendix slides.
Short spoken script included verbatim — the team may read it as-is.

**The angle the whole deck must serve:** *the challenges were the hard part, not the features.* Every
slide says what the problem was and how we solved it, in plain language — a reader who knows nothing
about wealth management must still follow it.

---

## 1. Rules for the deck generator

| Rule | Value |
|---|---|
| Length | 8 slides, tuned to **2:30**. To cut to 2:00, see the note under the timing map in §3 |
| Words on a slide | ≤ 5 bullets, ≤ 9 words per bullet. A slide is a cue card, not a report |
| Language | Plain English. If a finance word is unavoidable, put the plain meaning in the same line |
| Tone | Calm, concrete, honest. No hype, no "revolutionary", no emoji |
| Structure | Slide title = a claim or a question, not a label ("The data is incomplete. We never fill it in.") |
| Numbers | Only numbers from §6 of this file. Never round one up to sound better |
| Look | Clean, white background, one accent blue `#4A90D9`, one alert red `#E8564A`, one dark grey `#1A1A1A`. Big type, generous white space. No stock photos. One simple diagram on slide 3 max |
| Not allowed | Emoji, clip-art, dense tables on slides, screenshots of code |

---

## 2. The one-sentence pitch

> A wealth advisor gets a call in five minutes. One button turns eight scattered systems into a
> client briefing that reads in about a minute — every sentence traceable to the bank's own data,
> and nothing invented.

---

## 3. Timing map

| # | Slide | Seconds | One message |
|---|---|---|---|
| 1 | Title | 10 | What we built, in one line |
| 2 | The 5-minute problem | 20 | Preparation is slow, the information is spread out |
| 3 | One button, one minute | 20 | What the advisor actually gets |
| 4 | Challenge: the data is incomplete | 20 | We declare gaps instead of filling them |
| 5 | Challenge: too much information | 20 | We rank and cut, so the advisor sees 3 things, not 30 |
| 6 | Challenge: news that is relevant and free | 20 | Filtered to real holdings; AI labels each headline |
| 7 | Challenge: an AI you can trust | 20 | The model never touches a number |
| 8 | Bonuses, proof, close | 25 | Other banks' PDFs, follow-up chat, tested — and what production adds |
| | **Total** | **~2:35** | |

**For a hard 2:00:** keep slides 1–5 and 8, drop 6 and 7 (market news and AI safety) — but slide 7 is
the strongest answer to a judge's question, so keep it if there is any flex. The full script in §5 is
**427 words**, i.e. 2:20 at a brisk pace and 2:50 at a calm one.

---

## 4. Slide-by-slide

### Slide 1 — Title (10 s)
**On slide**
- Title: **From Ping to Pitch**
- Subtitle: An AI briefing assistant for wealth advisors
- Footer: UnRiskOmega · START Global × Swiss AI Weeks 2026

**Say:** "A client calls. The advisor has a few minutes. We built the tool that gets them ready."

---

### Slide 2 — The 5-minute problem (20 s)
**On slide**
- Advisor gets a call with almost no warning
- To prepare: portfolio, risk profile, notes, open offers, rule checks, market news, bank view
- That is eight systems — and 20 to 30 minutes of reading
- The information exists. It is just spread out

**Say:** "Everything an advisor needs already exists somewhere in the bank. Portfolio numbers in one
system, client notes in the CRM, the bank's market opinion in a PDF, news somewhere else. Finding it
and turning it into one story takes longer than the call itself."

**Visual:** eight small boxes scattered, with one tired person in the middle.

---

### Slide 3 — One button, one minute (20 s)
**On slide**
- **Generate Briefing** button, in the client view and the portfolio view
- Three sections: what happened · health check · what next
- Four answers an advisor actually asks for
- ~220 words, about one minute of reading
- Every sentence shows where it came from

**Say:** "The advisor clicks one button. About a minute later they have three sections: how the
portfolio moved, what needs attention, and what to do next. Every sentence has an evidence link — the
advisor can see the exact data behind it."

**Visual:** simple diagram — `Button → collect → decide what matters → write → briefing`. Five boxes,
one line. This is the only diagram in the deck.

---

### Slide 4 — Challenge: the data is incomplete (20 s)
**On slide**
- Missing risk profiles, broken references, no purchase prices
- Our rule: **never invent a number**
- Gaps are shown to the advisor, not hidden
- So "we cannot say" is a valid, visible answer

**Say:** "Real bank exports are imperfect. Some clients have no risk profile, some references point to
nothing, and there are no purchase prices — so we cannot honestly say *why* a position made money. We
chose to say that out loud. Every briefing declares what it could not determine."

---

### Slide 5 — Challenge: too much information (20 s)
**On slide**
- A report with everything in it is useless under time pressure
- The engine scores and ranks every observation
- Only the important ones reach the page; the rest are counted
- Client notes override generic advice

**Say:** "Giving an advisor thirty metrics is not helping them. Our engine looks at sixteen kinds of
observation — rule breaches, risk, one-sided bets, idle cash — scores them, and keeps the few that
matter for this client. What was left out is stated too. And client notes override everything: if a
client wrote that they avoid a sector, we do not recommend it."

---

### Slide 6 — Challenge: market news that actually matters (20 s)
**On slide**
- Only the client's real holdings are searched — nothing generic
- Ranks holdings by size, looks up the biggest first
- Free sources break, so three providers with fallbacks
- AI labels each headline: good/bad/neutral, and how much it matters
- No coverage for a holding? We say so, we do not pad it

**Say:** "A general market summary is useless. We look for news about the things this client actually
owns — biggest position first. Free news feeds are unreliable, so we fall back between three of them.
And the AI reads each headline and labels it: is this good or bad for a holder, and would it change a
decision. When there is no coverage — for example the portfolio only holds funds — we say that
instead of filling the space."

---

### Slide 7 — Challenge: an AI you can trust (20 s)
**On slide**
- The AI never calculates a number
- Numbers come from the bank's data, always
- The AI may reword a sentence or label a headline — nothing else
- If a rewrite changes a figure, we throw the rewrite away
- No key configured? The system says so and runs anyway

**Say:** "The interesting engineering problem is not calling a model, it is making a model safe in a
bank. In our design the AI cannot produce a number. It can only reword a sentence we already built, or
label a headline. If its rewrite contains a figure the original did not have, we discard it. And if no
model is configured, the briefing still works — it just reads a little more mechanically."

---

### Slide 8 — Bonuses, proof, and what production adds (25 s)
**On slide**
- Client statements from **other banks**: upload a PDF, it becomes a portfolio (10 statements tested)
- **Follow-up chat**: ask the briefing a question; answers carry evidence, or say "not available"
- Tested end to end: **184 automatic checks**, an unseen-client drill across 8 client types
- Production would connect: licensed market data, the real CRM, the bank's own CIO publications, an approved in-house model

**Say:** "Two extras: an advisor can upload a PDF statement from another bank, and it becomes a normal
portfolio in the system — we tested ten real statements. And they can ask the briefing follow-up
questions, with evidence behind each answer. In production this connects to licensed market data, the
live CRM and the bank's own research, but the product story does not change."

---

## 5. Spoken script (read this; ~2:30 at a normal pace)

> **1 · Title.** A client calls. The advisor has a few minutes. We built the thing that gets them ready.
>
> **2 · Problem.** Everything an advisor needs already exists inside the bank — portfolio numbers, the
> client's notes, the bank's market opinion, the news. It is spread across about eight systems, and
> turning it into one story takes twenty to thirty minutes. The call does not wait.
>
> **3 · What we built.** One button, in the client and portfolio view. A minute later: three sections —
> how the portfolio moved, what needs attention, what to do next — written the way an advisor speaks,
> with the source of every sentence one click away.
>
> **4 · Data.** Real exports are imperfect. Some clients have no risk profile, some references are
> broken, and there are no purchase prices at all — so nobody can honestly say *why* a position made
> money. Our rule was to never invent a number. Gaps are shown, not hidden.
>
> **5 · Prioritise.** A page with everything on it helps nobody. The engine scores sixteen kinds of
> observation and keeps the few that matter for this client, and it tells you what it left out. Client
> notes beat generic advice: if the client said they avoid a sector, we do not suggest it.
>
> **6 · Market.** A general market summary is worthless. We search news for what this client actually
> owns, biggest position first, across three free providers because any one of them breaks. The AI then
> labels each headline — good or bad for a holder, and does it matter. If there is no coverage for a
> holding, we say so rather than padding it.
>
> **7 · Trust.** The hard part of AI in a bank is not calling a model — it is making it safe. In our
> design the AI cannot produce a number. It can reword a sentence we already built, or label a headline.
> If a rewrite introduces a figure the original did not have, we throw the rewrite away.
>
> **8 · Close.** Two bonuses: advisors can upload a PDF from another bank and it becomes a portfolio,
> and they can ask the briefing follow-up questions that stay grounded in the data. It is covered by
> about 184 automatic checks and survives a client it has never seen. In production it would connect to
> licensed market data, the live CRM and the bank's own research — the product stays the same.

---

## 6. Facts that are safe to say (and where they come from)

| Fact | Value | Source |
|---|---|---|
| Clients / portfolios loaded | 48 clients, 58 portfolios, 504 securities | live `GET /api/health` |
| Briefing length | ~210–230 words, ≈1 minute to read | measured across all clients |
| Pipeline stages | 7, each timed and shown to the user (collect → analyse → rules → market → bank view → actions → compose) | `POST /api/briefing` |
| Typical pipeline time | under ~3 seconds warm, most of it the news fetch | measured |
| Observation types | 16, e.g. rule breach, concentration, idle cash, stale data | engine output |
| Rule violations in the data | 180, taken from the bank's engine and explained, never re-computed | provided data |
| Traceability | every sentence resolves to a data path, e.g. `clients[CASE-028].Portfolios[CASE-028-01].SecurityPositions[0].PortfolioValuePercentage` | evidence index |
| Gaps declared | every single client declares at least one thing it could not determine | measured, both languages |
| House view | a real public CIO outlook (UBS, dated 10.12.2025), 28 positions, labelled **mock** in the payload | `data/house_view.json` |
| News | keyless free feeds, three providers, filtered to holdings ≥2%, cached on disk | `external/news.py` |
| AI model | DeepSeek `deepseek-chat`, live and verified: it labels headlines (sentiment, materiality, why) and may reword prose | live check today |
| Ex-custody import | 10 PDF statements parsed; one lands at CHF 2'049'658.00 across 21 positions, reconciling to the statement's own total | import path |
| Automatic checks | 184 passing (1 skipped), plus an unseen-client drill: 11 checks, 8 client archetypes | `pytest -q`, `tools/drill.py` |
| Example scenario client | `SCEN-001` "Lena Vogt" — the brief's own example: 62% in one semiconductor stock | dataset |

**Demo numbers if you show a live screen** (client `CASE-007`, Mary Poppins): return +15.15% over 12
months, +7.67% over 3; shares at 56.7% against a 75% target; volatility 12.64% against a 12.00% limit.

**Re-verify before the pitch** (30 seconds, do it the morning of):
```
curl -s localhost:8000/api/health          # clients, portfolios, llm_available
cd src/backend && python -m pytest -q      # the check count
python tools/drill.py                      # the unseen-client drill
```
If a number moved, change the slide — do not round it.

---

## 7. Do NOT say (each of these would be a false claim)

1. That the prototype runs inside the live URO system. The brief forbids it; it is a mock-up shell.
2. That the AI writes the briefing or does the analysis. The model rewords sentences and labels
   headlines. Every figure comes from a deterministic engine.
3. That we can explain *why* a position gained or lost money. The data has no purchase prices and no
   position history. We report how much risk a holding contributes, and we say that is what it is.
4. That we re-check the bank's rule violations. We explain the violation the bank's own engine
   reported; re-deriving it would disagree with that engine on roughly a third of portfolios.
5. That the briefing is exactly 60 seconds. Say "about a minute" — English runs ~67 s, German ~59 s.
6. That we predict markets or tell clients what to buy on our own judgement. Names come only from the
   bank's own proposals and recommendation lists, and client preferences can rule a name out.
7. That the production integrations exist. They are a description of what would be connected.
8. In a live demo: do not put the ex-custody import screen next to the currency-exposure screen. The
   imported statement contains holdings the bank's master data does not classify, so the two screens
   quote different USD shares. Show the import result on its own.

---

## 8. Glossary — plain meanings, for the presenting team

Say the plain version on stage, not the term.

| Term | What it means |
|---|---|
| Wealth advisor / wealth manager | The banker who looks after a client's invested money |
| Portfolio | The client's basket of investments |
| Position / holding | One thing inside that basket |
| Asset class | The type of investment: shares, bonds, cash, property |
| Strategic Asset Allocation (SAA) | The long-term target mix agreed with the client, e.g. "75% shares" |
| Deviation / drift | How far today's mix has moved from that target |
| Suitability / investment rule | The bank's own guardrail; a "violation" means the portfolio is outside a limit |
| Risk profile | How much up and down the client can accept — set by the bank |
| Volatility | How much the value swings. A measure of risk, not of return |
| Concentration | Too much money in one thing: one share, one sector, one currency |
| House view / CIO view | The bank's official opinion on markets ("we prefer shares this year") |
| Rebalancing | Buying and selling to bring the mix back to the target |
| Proposal | An offer the bank made to the client, not always accepted |
| Ex-custody | Assets the client holds at another bank |
| ISIN | The international ID number of a security |
| Finding | One thing our engine decided deserves the advisor's attention |
| Evidence reference | The exact spot in the data behind a sentence |

---

## 9. Optional appendix slides (only if there is time or a question)

- **A1 — How it decides.** The seven pipeline stages with a one-line job each; the observation types
  that fire; the rule that a drop is always disclosed.
- **A2 — Architecture.** Mocked advisor UI (React) → one API → deterministic engine → three external
  inputs (news, CIO view, uploaded PDFs). Two sentences per box, no code.
- **A3 — The example scenario.** `SCEN-001` from the brief: 62% in one semiconductor name, client
  sensitive to risk and planning a property purchase. The briefing ties the single-stock fall to the
  specific position, not to a general market story.
- **A4 — What we refused to fake.** Missing purchase prices, unclassifiable imported holdings, a rule
  engine we do not own, a client the dataset does not carry. Four lines, one message: honesty was a
  design decision, not a limitation.
- **A5 — What is mocked vs real.** Real: portfolio data (provider export), live market news, the
  portfolio maths. Mocked: the bank's CIO view (declared in the payload), the URO interface, the
  production integrations.
