# STATUS.md — brief compliance, measured state, open items

**Single source of truth for "where the project stands", as of 2026-09-19.** It supersedes and replaces
three files that were deleted the same day: `REVIEW.md` (audit log + open backlog), `WEBSITE-BUGS.md`
(31-item defect report and its fix table) and `PRESENTATION-PACK.md` (deck brief). Everything still true
from those documents is here; everything they listed as open is either closed below or in §4.

> **Provenance for existing citations.** Code comments, tests and `notes-task/components/*.md` cite
> `WEBSITE-BUGS.md #N` and `REVIEW.md §N`. Those files no longer exist. Mapping: `WEBSITE-BUGS.md` items
> 1–17 and N1–N8 are all **closed** (§5 lists the ones that mattered structurally); `REVIEW.md` §4
> discrepancies, §9 coverage tables, §11 in-frame backlog and §12.3 drill defects are all **closed**;
> `REVIEW.md` §5 (arbitrary-instrument question) survives as §4.4 below; `REVIEW.md` §8 (how the data was
> generated) survives as §6 below.

Reproduce every number in this file:

```
cd src/backend && python -m pytest -q                    # 220 passed, 1 skipped
cd src/backend && python -m tests.test_harness --out /tmp/x \
  && python -m tests.test_harness --diff tests/snapshots /tmp/x     # clean
cd src/frontend && npm run typecheck && npm run build    # both clean
python tools/drill.py                                    # 11 PASS / 0 FAIL (isolated backend, port 8001)
```

---

## 1. Measured state

| | |
|---|---|
| Dataset (live) | **48 clients / 58 portfolios** — the 47 shipped plus `SCEN-001` "Lena Vogt" (the brief's Example Scenario) from `data/uploads/scen-001.json`; `data/excustody/` empty; `data_as_of` 2026-09-03 |
| Backend suite | **220 passed, 1 skipped** (the skip is the opt-in `--run-harness` drill); offline, deterministic |
| Snapshot baseline | 49 files (48 clients + `_summary`); `--diff` against a fresh run **clean** |
| Frontend | `tsc --noEmit` clean; `vite build` clean (dist 298.36 kB / gzip 85.01 kB, incl. 72 KB self-hosted Inter) |
| Findings | **636** across 48 clients; **all 16 enum types fire** — `rule_violation` 153, `missing_data` 78, `allocation_drift` 77, `preference_conflict` 51, `stale_data` 48, `risk_alignment` 47, `performance_driver` 45, `pending_task` 31, `esg_alignment` 19, `concentration` 17, `reinvestment` 16, `fx_exposure` 16, `sector_concentration` 15, `material_change` 14, `open_proposal` 5, `liquidity_event` 4 |
| Honesty gates | 48/48 declare ≥1 `meta.unavailable` · 0 unfilled `{placeholder}` strings · 0 raw catalogue keys · 0 unresolvable `evidence_refs` — each swept over all 48 clients × EN and DE |
| Length | EN min 208 / median **224** / max 231 words, read 62 / 67 / **69 s**, none above 69 s · DE min 182 / median 195 / max 209 words, read 55 / 59 / 63 s, none above the 210-word budget |
| Named instruments | data for **19 of the 47** shipped clients (4 from the five `Entwurf` proposals, 16 from recommendation-list members in an underweight SAA class); an `instrument_candidate` action renders for **18 of 48** |
| Market news | German share-class preambles stripped as phrases (13 master rows, 0 regressions) · items ordered biggest-holding-first, newest within one holding · the top item renders in **section 1** and section 3 takes the next *different* issuer · `SCEN-001` (62% ASML) now leads with ASML and gets 5 live on-topic headlines where the dirty query returned 1 generic one |
| Deck | `presentation/UNRISKOMEGA-briefing-assistant.pptx`, 12 slides, regenerated from `make_deck.py`, no empty slide and no placeholder |

Demo clients, measured (words / read s / findings / actions / instrument actions):

| Client | w | s | f | a | ia | note |
|---|---|---|---|---|---|---|
| `CASE-007` Mary Poppins | 211 | 63 | 12 | 5 | 1 | buys Swisscom + Nestlé for the Shares gap; Exxon, TotalEnergies and Equinor are excluded by her fossil-fuel note **and the exclusion is reported with the note path** |
| `CASE-028` Charles Foster Kane | 210 | 63 | 7 | 5 | 0 | sector concentration Financials 95.85% |
| `CASE-027` Buzz Lightyear | 229 | 69 | 9 | 5 | 0 | Industrials 97.9%; the private `SpaceX Aktie` line's news refusal declared, its two listed holdings still covered |
| `CASE-016` | 231 | 69 | 12 | 5 | 0 | the dataset's only ESG floor breach (3.10 vs 5.714), rendered at `high` |
| `CASE-041` | 229 | 69 | 20 | 5 | 1 | the withheld `ContributionVolatility` declared; the impossible figure appears nowhere |
| `CASE-045` | 224 | 67 | 10 | 5 | 1 | the draft's switch: exit Novartis 41.0%, cut BB Biotech 22.0%→2.9%, build 19 new lines |
| `CASE-008` / `CASE-029` | 226 / 227 | 68 | 19 / 13 | 4 | 0 | dirty refs and a missing risk profile: complete, declared, no crash |
| `CASE-034` | 208 | 62 | 9 | 4 | 0 | its draft moves nothing by ≥1 pp, so it names nothing — correct, not a gap |
| `SCEN-001` Lena Vogt | 223 | 67 | 10 | 5 | 0 | section-1 market block tied to the 62% ASML position |

---

## 2. Compliance with `task_def.md`, requirement by requirement

Modality matters: the brief's §1/§2 bullets are *"Relevant information **may include**"* (permissive),
§3 is *"The output **should**"* (normative), the action list is *"Possible next best actions **include**"*
(permissive), the Minimum Product Requirements are *"**must**"* (hard), and the Example Scenario is *"The
assistant **should** … explain"* (normative).

| Brief line | Requirement | Modality | Status |
|---|---|---|---|
| L42 | simulate a feature inside URO Advisor Pro | should | ✅ mocked shell, palette measured from `ui_reverse/` |
| L44 | Generate Briefing button in the client **or** portfolio view | should | ✅ both → `#/client/{ref}/briefing` |
| L44/L55/L81 | readable in **~60 seconds** | **must** | ⚠️ **OPEN** (§4.2) — EN median 67 s, max 69 s; DE median 59 s |
| L48 | **AI-powered** briefing assistant | normative qualifier | ✅ **R4 `llm` renderer built** (§4.1) — DeepSeek, phrasing only; activates when `DEEPSEEK_API_KEY` is set, 400 naming the key otherwise |
| L50–53 | combine client/portfolio/position + CRM + market news + house view | should | ✅ all four, 7 measured stages |
| L59–64 | the four questions (column headed **"Required content"**) | normative | ✅ all four, each with its own resolvable evidence refs |
| L66 | possible actions incl. buy/sell/switch | may | ✅ 7/7 action kinds; instruments named for 19/47 |
| L68 | **NOT** inside live URO; mocked interface from the provided screenshots | must-not | ✅ never touches a bank system |
| L76–81 | the six Minimum Product Requirements | **must** | ✅ 6/6 |
| L89–93 | five advisor understandings incl. **likely client questions** | should | ✅ 5/5; `client_questions` 1–3 for 48/48 |
| L95 | objective: less prep time, more confidence, consistency | — | ◐ structurally supported, **not measured** (§4.5) |
| L101 | three core sections | should | ✅ exact three, stable ids, 48/48 |
| L109–113 | §1's five bullets | may | ✅ 4 of 5; L110 *"largest contribution"* is answered as **risk** contribution (§4.3) |
| L121–129 | §2's nine bullets | may | ✅ **9/9** — incl. sectors (new), pending tasks (derived + declared), reinvestment, tags |
| L131 | **prioritize** the most important findings instead of listing every metric | should | ✅ enforced by trim + disclosure — but in tension with 43/48 over budget (§4.2) |
| L139–144 | §3's six output rules | should | ✅ 6/6 (`relevant_because` carries the holding weight, `source_kind` separation, 0 unresolvable refs, gaps declared). **Every insight about one instrument now carries its ISIN** (§3) so the advisor can open that instrument's market results from the sentence |
| L148–154 | the seven possible next best actions | may | ✅ **7/7** |
| L169 | Workflow / *open client-specific tasks* provided as data | data claim | ✅ derived from notes and declared as derived — **the field does not exist in either file**; the provider's table is wrong |
| L189–191 | a practical news method, free sources, **filtered to actual holdings** | should | ✅ Bing → Google → Yahoo (keyless RSS), only positions ≥2%, funds declared unavailable rather than padded with generic news. **Advisor-facing market search added** (§3): an instrument from the security master returns its facts, coverage, bank view and book exposure — an unknown company is refused, never answered with a general market summary |
| L195–201 | incorporate a bank house/CIO view and **show how the portfolio relates to it** | should | ✅ 28 stances, `matches` compared against the portfolio's own SAA target, declared mock in its own payload |
| L203 | production data sources | deferred by the brief | ✅ documented as out of frame (§4.4) |
| L217 | what caused the portfolio decline | should | ◐ exact figures ✅ (−11.90% 12 m / −16.51% 3 m); causality is risk contribution only (§4.3) |
| **L218** | **whether the development is isolated or market-wide** | **should** | ❌ **OPEN** (§4.3) — closable from news we already fetch |
| L219–221 | why it matters / which risks / which actions | should | ✅ 3/3 |
| L223 | one combined briefing, not three separate summaries | should | ✅ one payload, `source_kind`-tagged, cross-linked |
| L235–244 | ex-custody: six "should" bullets, behaving like a native portfolio | bonus | ✅ 6/6 — verified live (CHF 2'049'658.00, 21 positions, 8 transactions), merged by `load_raw`. L233's *upload a PDF* is now a real upload (§3), not only the sample picker |
| L252–258 | follow-up Q&A: the five example questions, grounded, declaring unavailability | bonus | ✅ 5/5 re-verified against the live API, plus a declared web-search fallback for questions the data cannot answer (§3) |
| L262–272 | a creative briefing format | bonus | ✅ print one-pager |
| L278 | live demonstration | should | ◐ the app works end to end; **rehearsal not done** (§4.5) |
| L280–290 | a short deck covering the nine named points | should | ✅ 12 slides, all nine, regenerated today |
| L292 | a previously unseen test client | may | ✅ drilled: `tools/drill.py` 11 PASS / 0 FAIL, 8 archetypes incl. a deliberately broken client, UI + curl import paths |
| L294 | the presentation itself gets to the point | should | ✅ 12 slides, ≤7 bullets each |

**Bottom line: 3 open items** (§4.1–§4.3): §4.1 is **built and needs only a key** to be verified live, §4.2 is a product decision, §4.3's L218 is small and buildable. L217's causality stays a substitution (§4.3). Everything else the brief asks for is built and measured.

---

## 3. What shipped this session (the deltas a reader of the old docs will look for)

**Advisor market search (`GET /api/market/search`, screen `#/market?q=`).** The brief's news limb is
"filtered according to its relevance to the client's **actual holdings and portfolio exposures**"
(L189–191), so the search answers for instruments the bank's own data carries: the master row (type,
currency, classification, price, volatility, sustainability, **bank rating**, recommendation-list
membership), its other share classes/alternatives, live coverage from the same keyless X1 providers,
the CIO stances on that instrument's categories (labelled mock), and every position in the book
holding it with weight and value. `resolve()` matches ISIN → valor → name and reports *how* it matched.
**Out of scope by construction**: an unknown company is refused with a stated reason and **no provider
is asked** — a general web summary about a company the bank has no position in, no rating for and no
classification of is exactly the "general market summary without a clear connection to the portfolio"
the brief rules out (L203 defers that connection to production). Private instruments are refused with
the same reason the briefing path uses, so the two never disagree. Reachable from the header magnifier
(previously an inert button from the screenshot) and by deep link; EN/DE.

**R4 `llm` renderer (`app/external/llm.py`, DeepSeek).** §4.1's requirement, built as the second
interchangeable renderer §6 specifies: the template briefing is produced first and the LLM only
rewrites its sentences. Section ids, block kinds, evidence refs and the whole evidence index are never
sent; a rewritten sentence that contains a figure its source did not have is discarded and the template
wording stays (the number guard treats `5.59` and `559` as different figures, and reads `2'049'658` /
`1,234,567` / `1.234.567` as the same). No key → `POST /api/briefing` with `renderer:"llm"` returns
**400 naming `DEEPSEEK_API_KEY`**, never a silent fall-back; `/api/health` carries `llm_available` /
`llm_model` and the UI asks for the LLM only when the backend can run it. 25 s cap.

**News quality fixes (they apply to the briefing too).** Publisher names were lost for every Bing hit:
Bing wraps `<Source>` in a namespace whose URI is the *query URL itself*, so `findtext("source")` never
matched and every headline reported `bing.com` — now matched by local name, so the advisor sees
`Investing`, `Reuters`, `Bloomberg.com` where they used to see the search engine. Google's query is
URL-encoded like Bing's (an advisor-typed search can contain `&`). The news disk cache gained a
**schema version**: the cache is cache-primary for 6 h, so pre-fix entries would have kept the wrong
publisher for hours; entries written by an older schema are ignored and refreshed.

**Defect found by verification, not by the tests.** The market panel crashed the whole screen
(`ErrorBoundary`: "Cannot read properties of undefined") for any instrument the master does not carry,
because the unmatched branch of the payload omitted `recommendation_lists` — the *normal* case, since
the master was trimmed to what the case clients hold. Fixed on both sides: the payload now has one key
set for a hit and a miss, and the panel guards the read. `test_market_search.py` pins the shape.

**Import path re-verified end to end** for the brief's bonus challenge (PDF → `EXT-*` portfolio →
briefing): 10 of 10 provided statements parse, 21 statement lines → 19 securities + 2 cash accounts,
6 ISINs resolve and 13 do not, the position sum reconciles to the printed `Vermögen` (exact for 7 of 10,
±1–2 CHF rounding on 3), duplicate `(client, file)` → 409, unknown client → 404, delete → back to 58
portfolios. Two consequences worth knowing on stage are in §4.8.

**F4 layout: stacked, and measured twice.** The screen began as three grid columns, and a grid item
stretches to its row height by default, so the allocation chart rendered a 220px donut inside a
**280x1877px** box — the "1 wide, 5 tall" shape that prompted this. Moving the donut beside its table
fixed that but created the next problem: the metric rail took a 520px column, which left the positions
table — 12 columns, ~1000px of intrinsic width — only 816px, so it painted **198px over the rail's
cards**. A sidebar is simply the wrong structure for that table, so the layout is now stacked:

| | first | second | now |
|---|---|---|---|
| Page height (CASE-028-01) | 3516px | 2903px | **1492px** |
| Donut container | 280x1877 for a 220px chart | 220x200 | 220x200 |
| Metric rail | 260px, 11 stacked cards | 520px, 2 columns | **full-width strip, 7 per row** |
| Positions table | 997px in an 816px column | same, overlapping the rail | **1318px, no overlap** |

Allocation panel (with its donut) → the tile strip → the positions table at full width → exposures.
Verified across CASE-007/016/028 and SCEN-001: the table never exceeds its container, nothing overlaps,
no horizontal page overflow, and a vision pass on the result reports no overlap or clipping. Narrow
viewports stack to one column unchanged.

**A fabricated chart, found while measuring that.** The `scatter` widget fell back to
`[0.3, 0.5, 0.7, 0.4]` whenever its payload carried no series, so **every** portfolio drew four invented
points under a "Risk / Return" title — a chart that looked like data and was not. No portfolio in the
book has scatter or line rows (checked across CASE-007/016/028 and SCEN-001), so the fallback is gone,
the two real numbers render instead, and a widget with no visual no longer reserves the 40px meant for
one (the fixed `min-height: 100px` on every card went with it). `line` and `gauge` were already
rendering as empty cards; they now state their value and nothing else.

**The dashboard footer stopped leaking QA output.** The client list ended with
`Data quality: 28 references to unknown portfolios …, 4 clients without risk profile …` and a
`Data contract notes:` paragraph explaining that street/ZIP are absent and how `last_changed` and
`last_consultation` are derived. That is how the data was built and audited, not something an advisor
preparing a call can use, so it is gone; only **Data as of** remains. The four catalogue keys went with
it. The API still returns `integrity` and `notes` for tooling.

**What an upload actually changes (measured, CASE-028).** The imported statement is merged into the
client, so the analysis moves with it: portfolios 1 → 2 (`external_portfolios: 1`), briefing findings
**7 → 12**, a new finding type (`fx_exposure`: *"Portfolio EXT-028-01 holds 31.13% in USD"*), the
import's declared gaps (`missing_data` 1 → 5), market coverage **4 → 8 headlines** (the statement's
holdings are now queried too), and a new action *"Reduce currency risk: 31.13% in USD"*. A
portfolio-scoped briefing (`portfolio_nr=EXT-028-01`) covers only the imported statement — 7 findings,
177 words, its own name in the first block. Two things deliberately do **not** move: `client.aum` and
the dashboard's book total, which come from the client-level field in the source data — the imported
portfolio's own value (CHF 1'801'061) is listed on the client card and inside the briefing, but it is
not added to the headline figure. That is a money number and a multi-currency statement, so it is left
as a decision rather than changed silently (§4.9).

**The assistant now answers from the client's own analysis.** It used to be keyword routing with
templated sentences, and the model only appeared in the web fallback — so a follow-up answer carried no
client context and no idea what the platform is for. It now receives the analysis the screens already
show (client profile and tags, each portfolio's figures, the findings with their text, the derived
actions, compliance, the bank's own view, the headlines about the holdings, and the declared gaps)
under an advisor-facing persona: the assistant inside URO Advisor Pro, talking to a wealth manager
preparing for a client call. Measured on CASE-028 — *"What should I discuss with this client, and what
are the risks?"* now answers: *"effectively a single-stock position: 95.85% in VZ Holding AG, 95.85% in
Financials, volatility 22.0% against a 12.0% maximum for Anlageprofil 5 … a single corporate event
would move nearly the whole CHF 196,851 … the stale performance data (last point 2026-07-01 against
data as of 2026-09-03); no proposals on file and no candidate instruments"* — personalised, specialised,
and its own limits stated. The answer is labelled *Assistant answer (LLM) — grounded in this client's
data*, and the routed answer with its evidence remains the fallback (`answered_by` says which ran).

**Grounding is enforced, not requested.** A reply carrying a figure the context does not contain is
rejected and the routed answer stands. Three measurement-driven corrections were needed to make that
guard usable rather than merely strict: the platform stores fractions (`0.9585`) while a sentence says
`95.85 %`, so both units of a stored figure are accepted; prose puts punctuation after numbers
(`22.6037%.`), which used to invent the token `22.6037.`; and JSON renders `196851.0` where a sentence
says `196851`. Each was found by logging the rejected figures against a real answer, and each has a test.

**The public web is now the last resort, not the second.** The unclassified branch used to call the web
before the client's data had a chance, so *"how has this client's portfolio performed?"* was answered
from search results saying it could not know. The order is now context → routed answer → web, and the
classifier was taught that `performed` belongs to the performance family (it only matched
`performance`).

**Tests no longer call a paid model.** `.env` holds a real key on a developer machine, and with it every
QA and briefing test was hitting the API — the suite took 53 s, three tests failed on the model's
wording, and the run cost money. `conftest` now clears the key for the session exactly as it disables
the news network; the tests that need the LLM stub `_chat` and set a key themselves.

**The assistant is findable.** It was the third block in the briefing's right rail — below the
evidence panel and the pipeline timings, i.e. below the fold on a laptop, which is why nobody could
find it. It is now first in the rail and titled *"Assistant — ask about this client"*. Verified in the
browser: visible 309px from the top, and both answer paths work from the UI — a data question
(*"What is the concentration risk?"*) answers `95.85%` with the position and HHI as evidence (this is
the routing fix below), and *"Is NVIDIA worth investing?"* returns a `Web source — not bank data` chip,
a hedged summary, and its source links.

**The web source has a fallback.** Verified live: the DuckDuckGo Lite endpoint refused the connection on
one run (the assistant declared it and declined to answer, correctly), so the chain is now
web search → the same keyless news feeds the market layer uses, with one retry on the first. Only when
both decline does the answer become a stated refusal.

**PDF upload — the bonus challenge the way the brief describes it.** The panel offered only the ten
provided samples; the brief asks the advisor to *upload a portfolio statement from another custodian as
a PDF* (L233–244). `POST /api/import/ex-custody/upload` (multipart) now takes the file itself: it is
stored under `data/excustody/reports/` (gitignored, `URO_EXCUSTODY_REPORTS_DIR` override) under a
sanitised basename, parsed by the same reader and attached through the same path as the picker, so it
produces the identical `EXT-*` portfolio. Verified in the browser: a statement uploaded under the
advisor's own filename became `EXT-041-01` (20 positions, `is_external: true`), appeared in the client's
portfolio list and produced a 180-word briefing with the ex-custody declaration. Refusals are declared,
not swallowed: a damaged PDF → `unreadable_pdf` (and the stored file is deleted), a statement with no
readable positions → `no_positions` rather than an empty portfolio, a non-PDF → 400, an empty file → 400.
The picker's `file` parameter now rejects anything containing a path — it comes straight from a request.

**LLM, honestly reported.** Three things came out of running the key against the real API: the rephrase
pass now **declares what it did** (`llm.applied/changed_sentences/reason`; `renderer` stays `template`
when a pass changed nothing, instead of claiming an LLM run that rewrote no text) — measured on
CASE-028, DeepSeek returns the terse data-dense block set unchanged and rewrites plain prose, so the
declaration is the honest state rather than a bug; quoted headlines are **excluded** from the pass
because the model translated a German headline, which would misquote a source; and `.env` is now loaded
on first `app.*` import, so scripts and the drill see the same configuration as the server.

**Signals from the news.** `signals()` asks the model for a reading of exactly the retrieved headlines —
sentiment, materiality, and one sentence on what it implies for a holder. Guarded harder than the
rephrase pass: a `why` carrying a figure the headline lacks is dropped, an unusable reply is discarded,
and the block declares `applied/reason`. Live on ASML it correctly rated a bare ticker reference
`neutral/low` ("no substantive information") and a promotional "stable market position" `neutral/low`
("promotional, lacks specifics"). Rendered under each headline with an "LLM signals · deepseek-chat" chip.

**The chatbot can browse.** A question with no route in the client's data ("is NVIDIA worth investing?")
now runs a keyless DuckDuckGo Lite search and has the model summarise **only** those results: every
claim must be supported, figures are constrained to the retrieved snippets, the reply must name the
indexes it used, and any failure falls back to listing the sources rather than producing unsourced prose.
Answers carry `source_kind: "web"`, the URLs, and a "not bank data" label; data questions are untouched
(`source_kind: "data"`, no sources). Off by `URO_NEWS_OFFLINE`, so no test touches the network.

**A real chatbot routing bug, found while testing it.** Any question containing "risk" hijacked the
specific family — "What is the concentration risk?" was answered with portfolio volatility and
value-at-risk, a correct answer to a question nobody asked. The generic word is now tried last, the same
way `risk_contribution` is already tried first; "currency risk" → FX, "concentration risk" →
concentration, and a bare "what is the risk?" still answers about risk.

**Typography.** The UI ran on a bare system stack (Segoe UI at 11–13px on Windows). Inter is now
self-hosted from `public/fonts/` (three Latin weights, 72 KB, SIL OFL) with the system stack as the
fallback, so every machine renders the same and the demo needs no network. Verified in the browser:
`document.fonts` reports all three faces loaded and the body computes to Inter.

**Insight → market results, from the sentence.** A briefing block that is about one instrument carries
`security_id`/`isin`, and the UI renders a *Market results* control beside *Evidence* that opens
`#/market?q=<isin>` — the advisor never retypes a name. The instrument is copied off the block's own
finding (`_attach_instruments`, one pass after the trim), so `concentration`, `performance_driver` and
any future instrument-level finding are linked for free; a market block takes it from the headline it
quotes. Findings now carry `security_id`/`isin` (null when the finding is about the portfolio, a
currency or a rule), market items carry the instrument they are about, and blocks about the portfolio
stay untagged on purpose. An action that names *several* instruments is not linked — the choice would be
arbitrary. Verified live on CASE-028 (3 controls, click → `#/market?q=CH0528751586` → VZ Holding with
coverage and holders) and SCEN-001 (ASML + Qualcomm), in EN and DE, and on the print one-pager.
Presentational cost of the 60-second budget: **zero words**.

**Local `.env` (the optional LLM key).** `app/env.py` reads `.env` at the repository root into the
environment without ever overriding a real variable, called once at startup; `.env` is gitignored and
holds `DEEPSEEK_API_KEY` with a comment above each option. `src/README.md` documents it.

**Named instruments** — the brief's *"identifying securities to buy, sell or switch"*, previously 0/47.
  `domain/candidates.py` returns data (never prose): proposal moves from the five `Entwurf` drafts
  (a draft is a complete target portfolio, so a held line it omits is an exit) and recommendation-list
  members for an asset class below its SAA target, ranked by currency-group match then instrument
  volatility, ≤3 per class with every drop disclosed in `buy_pools`. A client preference rules names out
  and the exclusion is reported with the note that caused it.
- **`sector_concentration`** — top *classified* look-through industry at `SECTOR_HIGH` 0.50 /
  `SECTOR_MEDIUM` 0.30 (at 0.25 it fired for 19 of 48 clients and said nothing); `Nicht klassifiziert`
  excluded, unclassified share disclosed. 15 of 48 clients.
- **`esg_alignment`** — the portfolio's value-weighted `SustainabilityScore` against the bank's own
  `MinimumLevel`; an **observation, never a verdict** (the engine reports 0 violations of `Sustainable
  investments only`). Profiles whose floor is below 0.01 emit nothing, because a floor that renders as
  "0.0" is noise. One breach in the dataset: `CASE-016-01`, 3.10 vs 5.714, ranked `high` so it survives
  the trim.
- **Per-question evidence** — `briefing.questions` carries `what_happened_refs`, `situation_refs`,
  `next_refs`, `should_do_refs`, all resolvable; the UI renders one evidence control per answer.
- **Market context in section 1** — the top item (largest holding) now answers §1's *"relevant market
  events connected to recent portfolio movements"*; section 3 takes the next different issuer.
- **News query cleaning + ordering** — phrase-based preamble stripping and biggest-holding-first order.
- **Structural defects found and fixed while integrating** (several were introduced by the same wave that
  added the features): an `IndentationError` in `actions.py` that silently produced **zero actions for
  every client** while the suite stayed green — `facts.py` now re-raises programming errors from the
  actions stage instead of degrading, because unavailability is for the outside world, never for our own
  bugs; 34 unfilled `{category}`/`{diff}` placeholders reaching the advisor; a raw `question.sit_sector`
  key inside the situation answer; a section-3 market regression that dropped the block for **48/48**
  clients; the ESG block trimmed away on the only client where it fires; an ex-custody `PortfolioId`
  collision across clients (both `EXT-028-01` and `EXT-022-01` were 900000001, and
  `index.portfolio_by_id` resolves by id); a switch label that called an exit a buy; `tools/drill.py`
  reading the briefing payload one level too high so it reported every client as failed; and `SCEN-001`
  still typed `Professional client` although it is a private natural person.
- **Deleted**: `screens/briefing/BriefingTrigger.tsx` (dead — no importer; the real trigger is
  `ClientScreen`/`PortfolioScreen` `onBriefing` → `#/client/{ref}/briefing` → `BriefingScreen`).

---

## 4. Open items — the complete list

### 4.1 "AI-powered" (L48) — built, waiting on a key
The R4 `llm` renderer now exists (§3): `app/external/llm.py`, DeepSeek's OpenAI-compatible API,
phrasing only and guarded by a figure-preservation check. It is **off until a key exists** — set
`DEEPSEEK_API_KEY` (optionally `URO_LLM_MODEL`, `URO_LLM_BASE_URL`); `/api/health` then reports
`llm_available: true` and both briefing screens switch their `renderer` to `llm` automatically. Verified
without a key: the endpoint answers **400** with the exact variable to set, the template stays the
fallback, and `renderer:"llm"` never degrades silently. Verified with a stubbed model: a rewrite that
introduces a figure is rejected block by block, an unusable or fenced reply keeps the template, and the
evidence index is untouched. **What is still unverified is the live DeepSeek call itself** — that needs
the key, and until it arrives the deck must say the LLM pass is wired and one env var away.

### 4.2 The ~60-second contract (L44/L55/L81) — a product decision
43 of 48 EN briefings sit above `render.WORD_BUDGET` = 210 words (median 224, max read 69 s); DE is
inside. The overshoot is structural: the four answers are never trimmed and every section keeps one
traceable block. Accept 61–69 s as "approximately 60", or lower the budget to ~190 — **L131's
"prioritize … instead of listing every available metric" argues for lowering it**, since this wave added
three block kinds. Cost: one constant plus a re-measure; every extra drop is already disclosed via
`trimmed_blocks`. Do not widen a test band to make the number disappear.

### 4.3 Two Example-Scenario outputs (L217, L218)
- **L218 "isolated or market-wide" — open and closable in frame.** The brief names its own mechanism at
  L212: *"The **market-news input** indicates that the price movement followed a sector-wide reaction …
  rather than a broad market decline."* It never asks for an index or sector time series. We already fetch
  those headlines (`SCEN-001`: 4–5 ASML/semiconductor items) and report IT 80.0% sector concentration,
  but we never state the conclusion. Buildable with no new data source: classify each fetched headline as
  issuer/sector-specific vs broad-market (deterministic keyword sets, the `PREFERENCE_KEYWORDS` pattern)
  and state the balance — *"5 of 5 headlines for this client's holdings are issuer- or sector-specific,
  none is a broad-market story."* It must remain a statement **about the coverage retrieved**, never a
  market return we cannot compute, and a mixed or all-broad result must be reported as such.
- **L217 causality — not closable, keep substituting.** `SecurityPositions` carries
  `ContributionVolatility` / `MarginalContributionToRisk` but no per-position return, no cost basis and no
  position history; L170's own data table lists securities as *"type, currency, price, volatility,
  asset-class allocation"*. So we report **risk** contribution (it reconciles to portfolio volatility) and
  say so out loud. Faking a performance attribution is the one thing this project treats as fatal.

### 4.4 Out of frame — production, deliberately not built
An arbitrary-instrument question ("is NVIDIA investable for this client?") returns a clean refusal, which
is correct: NVIDIA has no master row (`US67066G1040` absent from 504 rows), every router is
client-scoped, news is gated on the bank's own `Shares` classification, and `SuitabilityRules` carries no
machine-evaluable thresholds (54 rows of `{Id, RuleCode, Description, Level, IsIndividual}`) — so no
verdict is computable even with a master row. L203 defers exactly this to production. Answer it live as:
*"not in this dataset; here is the client-relative half we can do; here is what production would connect."*
The same limit is why violations are display-only: re-deriving one rule from `RiskProfile.MaxVola`
disagrees with the engine's ground truth on **15 of 46 portfolios**.

### 4.5 Human checks — rehearsal, not code
The two-minute advisor role-play, the timing comparison against the brief's own "20–30 minutes" of manual
review, and a live unseen-client drill in front of an audience. Runbook: `notes-task/DEMO-SCRIPT.md`;
rehearsal: `python tools/drill.py`.

### 4.6 Documentation debt (small, known)
`PROJECT-OVERVIEW.md` §8.1 still shows pre-wave numbers (626 findings, "all 14 enum types", 124–225 words)
and §9/§10 still say "111 passed"; its §8.2 *"tags remain collected but unused"* row contradicts the closed
tags row in §12. `PROJECT.md` §11's harness row now says 178 and lists the two new test modules; the
market-search and LLM rows there are new this session (the earlier §11 harness count of 145 is gone).
`src/README.md`'s layout tree predates `domain/candidates.py`, `text.py`, `fields.py`, `cache.py`,
`domain/instrument_search.py` and `compose/search.py`; its endpoint table now lists
`GET /api/market/search`. The six `notes-task/components/R1`–`R6` specs
still describe the pre-wave design (R5's spec even names its own `candidates(findings)` function, which is
why the payload key is `instrument_candidates`); the F/X/B/T specs are current, and `X1-market-news.md` is
the reference for the expected depth — **it still documents the provider chain and the Yahoo tier as they
were written, not the publisher fix, the Google URL encoding or `fetch_for_query`**. `DEMO-SCRIPT.md`'s
per-stage millisecond timings were carried over rather than re-measured; its word counts and band are
measured.

### 4.7 Demo-day operations (two commands before the pitch)
- **Start the servers so they survive the session.** They died with an agent session twice on 2026-09-19.
  Launch detached/persisted, or from a plain shell outside the agent:
  `cd src/backend && python -m uvicorn app.main:app --port 8000` · `cd src/frontend && npm run dev`.
- **Re-warm the news cache — every entry is now cold.** The cache-schema bump (§3) makes entries written
  before the publisher fix unreachable, so *every* query refetches once (~1–2 s per instrument, inside the
  briefing's 8 s market budget). Run one briefing per demo client, and one market search per instrument
  you plan to show, before the pitch.
- `SCEN-001` is normally left loaded (it is the Example Scenario). For the shipped 47-client book: delete
  `data/uploads/scen-001.json` and `POST /api/dataset/reload`.
- **Check the demo state in one call before you present:** `GET /api/import/imported` must return
  `count: 0` and `GET /api/health` must report **58** portfolios. An imported `EXT-*` portfolio survives
  a dataset reload by design and attaches itself to a real client, so a stray one shows up as an extra
  portfolio in that client's list — a stray `EXT-008-01` was found in the working copy exactly this way.
  `tests/test_state_isolation.py` now fails loudly if a future test writes to it.

### 4.9 An imported portfolio is not in the client's headline AUM — your call
`client.aum` and the dashboard's book total come from the client-level field in the source data, so
attaching a statement of CHF 1'801'061 to a client whose own portfolio holds CHF 196'851 leaves both
figures unchanged; the imported portfolio's value appears on the client card and inside the briefing,
so nothing is hidden, but the headline ignores it. Summing imports into the client total means summing
a statement's value in its own default currency into a client figure, and the field is not always the
portfolio sum anyway (CASE-038: `aum` 1'619'901 vs portfolios 3'813'346, because 15 portfolio refs
dangle). **Option A**: leave it and disclose the split on the client card. **Option B**: sum native plus
imported and state the currency basis. Not changed without a decision.

### 4.8 Two things the ex-custody import shows on stage (know them before you demo it)
- **An imported portfolio is ~69% "not classified"** for exposure purposes, and the same portfolio then
  reports **two different USD figures on two screens**: the briefing's currency finding says `44.89%`
  (positions' own currency, `metrics.fx_exposure`, which matches the statement's page-4 table) while F4's
  exposure block and the follow-up Q&A say `5.59%` and put `69.03%` in *Nicht klassifiziert*
  (`metrics.exposures`, which classifies through the master row a position does not have). Cause: the
  master was trimmed to the ISINs the 47 shipped clients hold, so 13 of the statement's 19 securities have
  no `SecurityId`. **Do not put both screens side by side in the demo** until the exposure path falls back
  to the position's own currency; the honest line is the one §4.4 gives — *here is the client-relative half
  we can compute, here is what production would connect*.
- **Deletion exists as HTTP only**: `DELETE /api/import/imported/{nr}?client_ref=<ref>` (the query
  parameter is required); nothing in the UI removes an imported portfolio.

---

## 5. Closed and verified — the defects that shaped the current invariants

Kept as a short record because code comments and tests still name them. All 31 items of the former
`WEBSITE-BUGS.md` are fixed and re-verified; the ones that changed an invariant:

- **Ex-custody import blanked the whole app** (critical): `ImportResponse.portfolio` is the F5 shape while
  the panel read the parsed-report shape, and the first unguarded `.length` threw with no error boundary
  anywhere. Now the response carries `report` beside `portfolio`, the panel renders `report` with guarded
  access, and a root `ErrorBoundary` turns any render crash into a localized panel. Re-verified live: one
  POST, zero console errors, KPIs and 21 position rows.
- **Briefings leaked other portfolios' findings**: `relevance.findings()` now filters by the requested
  portfolio's id, keeping findings with no portfolio id (they are the client's own story).
- **Double POST per briefing mount / fake progress**: in-flight request dedupe in `api/client.ts`,
  server-side `app/cache.single_flight` (60 s, cleared on any dataset reload), real elapsed seconds,
  honest `waiting` stages, a working Cancel, and the fabricated 700 ms creative-sheet animation deleted.
- **Contradictions on one page**: house-view relations now compare against the portfolio's own SAA target
  and are localized; the LIVE provenance chip requires `providers_used.length > 0`.
- **One unit everywhere**: `app/fields.py` owns the `ViolationPath` field vocabulary and unit, so health
  check, action, client card and evidence all read `12.64% / 12.00%` and no `SimulationVolatilityRuleField\`1`
  reaches the UI.
- **Rule text is the violation's own `RuleDescription`** (54 rows carry 53 distinct codes, so a lookup by
  code can name the wrong region — `CASE-008`/`CASE-044` said "Grossbritannien" for a Swiss rule).
- **A withheld risk figure is declared in the briefing**, not only on F4.
- **German-only strings, mid-word truncation, dead sortable columns, `905.5T` for thousand, dashboard tabs
  not in the URL, `(1 PORTFOLIOS)`** — all fixed; `app/text.py::compact` cuts on word boundaries.
- **Uploads are never consumed** — the earlier "phantom client" report was a stale file in
  `data/uploads/`; any file there joins the dataset on every reload, by design.

---

## 6. Reference — how the provided data was generated, and how to synthesise equivalents

Load-bearing for two reasons: it explains the data on stage, and `tools/synth_client.py` implements it.

1. **It is an export from a real .NET rule engine**, not hand-written mock data: `ViolationPath[].FieldName`
   uses engine class names (`SimulationVolatilityRuleField\`1`, `SimulationPositionCollectionPortfolioValueRuleField`,
   `SimulationFilterTopLevelSAAAssetClassRuleField`, `PositionInRecommendationListRuleField\`1`, …) — 15
   distinct classes, 6 opaque `Operator` codes. Rules are evaluated on a **simulation**, so `CASE-007`'s
   breach figure 0.126383759363 matches no stored number.
2. **One shared synthetic price path**: all 57 shipped portfolios carry exactly 58 monthly points,
   2021-10-01 → 2026-07-01, last value = `AssetsUnderManagementInDefaultCurrency`.
3. **Risk figures are model outputs, not statistics over that series** (`CASE-007-01`: realised σ from the
   58 points = 0.1348 vs `Portfolio.Volatility` 0.09182). Recomputing either is invalid — the measured
   basis for "violations are display-only".
4. **Clients come from archetype templates**: 153 notes but 53 distinct texts; tags from a fixed 19-item
   Region/Industry vocabulary; lifecycle scripted (206 proposals: 125 `Final` / 76 `Abgelehnt` / 5 `Entwurf`).
5. **The reference file was trimmed after generation**: 504 securities for the 275 ISINs actually held —
   which is why `CASE-008`/`CASE-038` carry 28 dangling ids and a new client's securities go unresolved.
6. **Two recommendation signals**: `RecommendationLists` holds one list (Id 9, *"Recommendation list free
   assets"*, 232 members) while `Securities[].InRecommendationList` is true on 403 rows; every member
   carries the flag, so membership is the stricter and nameable source. 12 ISINs have two master rows and
   **9 of those disagree on the flag** — so an ISIN-only join reports a field only when every row agrees.
7. **Draft proposals are complete target portfolios** (their `SecurityPositions` weight to 0.966–1.002), so
   a held line the proposal omits is an exit. Proposal amounts are in the proposal's own currency and held
   amounts in the portfolio currency — compare **weights**, never amounts.

Invariants any generated data must reproduce: 58 monthly points ending at the AUM · securities + cash = 1 ·
weights = value / AUM · per-fund mapping sums = 100 · every violation carries a `ViolationPath`.

---

## 7. Where to look for what

| File | Read it for |
|---|---|
| `task_def.md` | the brief (read-only) |
| `STATUS.md` | **this file** — compliance, measured state, open items |
| `notes-task/PROJECT.md` | the frozen contracts (§5), data rules (§7), component rules (§8), as-built surface (§11) |
| `notes-task/PROJECT-OVERVIEW.md` | the ring model, outside → inside |
| `notes-task/PROJECT-NOTES.md` | raw verified data findings and landmines |
| `notes-task/DEMO-SCRIPT.md` | the two-minute role-play, timings, drill runbook, judge Q&A |
| `notes-task/components/<ID>-*.md` | one spec per component (19) |
| `src/README.md` | layout, run commands, endpoints, contract conventions |
| `tools/README.md` | the unseen-client rehearsal kit |
| `presentation/make_deck.py` | the deck generator (12 slides) |
