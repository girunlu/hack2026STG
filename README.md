# URO Advisor Pro — AI briefing assistant (prototype)

A working prototype for the **UnRiskOmega "From Ping to Pitch"** challenge: an AI briefing assistant
inside a **mocked** URO Advisor Pro interface that turns a client's portfolio, the bank's CRM context,
current market news and the bank's own investment view into a briefing an advisor can absorb in about
a minute.

Prototype only. It never runs against a live URO environment and contains no real client data.

---

## What it does

An advisor clicks **Create briefing** on a client or portfolio, and the prototype runs one deterministic
pipeline (7 timed stages) and renders:

* **Recent Portfolio Development** — performance, its main drivers, material changes, market context
* **Portfolio Health Check** — SAA deviations, suitability and investment-rule violations, risk-profile
  alignment, concentration, client-specific preferences, open proposals, pending tasks
* **Portfolio Outlook & Next Best Actions** — market developments tied to the holdings, the bank's
  strategic/tactical view, and concrete next steps

plus the **four questions** the brief asks (what happened / what is the situation / what could happen
next / what should be done), **questions the client may raise**, an **evidence panel** that traces every
sentence back to a field, and a **follow-up assistant**.

Three bonus challenges are implemented: **ex-custody PDF import** (pick a provided statement *or upload
your own*), the **interactive follow-up assistant**, and a **creative print one-pager**.

## Quickstart

Backend (FastAPI, Python 3.12):

```bash
cd src/backend
python -m uvicorn app.main:app --port 8000
```

Frontend (React + TypeScript + Vite):

```bash
cd src/frontend
npm install
npm run dev            # http://127.0.0.1:5173, proxies /api to :8000
```

Then open <http://127.0.0.1:5173>. Interactive API docs: <http://127.0.0.1:8000/docs>.

Python needs `fastapi`, `uvicorn`, `httpx`, `pydantic`, `pypdf` (all present in the provided
environment). The app reads the provided case material from `unriskomega-2026/`, so keep this folder
intact.

## Configuration — `.env` (optional)

`.env` in the repository root is read at startup and is **not** committed. Everything works without it;
one feature does not:

```
DEEPSEEK_API_KEY=…            # enables the optional LLM features (see "AI, and what it may not do")
URO_LLM_MODEL=deepseek-chat   # optional, default deepseek-chat
URO_LLM_BASE_URL=…            # optional, default https://api.deepseek.com
URO_NEWS_OFFLINE=1            # optional, disables all market-news and web requests
URO_WEB_OFFLINE=1             # optional, disables only the web-search fallback
```

Real environment variables always win over the file. `GET /api/health` reports whether the LLM is
available (`llm_available`, `llm_model`) and the UI adapts to it.

## AI, and what it may not do

The analysis itself is **deterministic**: findings, actions and every figure are computed from the
provided data, so the same input always produces the same briefing and nothing has to be trusted to a
model. The LLM (optional, DeepSeek) is confined to three jobs, and each is guarded:

| Feature | What the model does | Guard |
|---|---|---|
| Briefing wording (R4 `llm` renderer) | rephrases the finished briefing's sentences | section ids, block kinds, evidence refs and the evidence index are never sent; a rewrite containing a figure its source lacks is discarded block by block; quoted headlines are never rephrased |
| Market signals | labels each retrieved headline (sentiment, materiality, why) | may only explain the headline it was given; a signal whose explanation carries a figure the headline lacks is dropped; every signal is labelled as model output |
| Follow-up assistant | answers the advisor's question from **this client's own analysis** | a reply carrying a figure the client context does not contain is rejected and the deterministic answer stands; `answered_by` states which answered |

If a key is missing, the briefing stays on the deterministic template, signals are declared
unavailable, and the assistant falls back to its routed answers — never a silent downgrade, and never
an invented number.

## Data sources

| Source | Live / mock | Where |
|---|---|---|
| Clients, portfolios, positions, proposals, notes, tags | provided mock data | `unriskomega-2026/core-case/portfolio-data/` |
| Securities, SAA targets, risk/ESG profiles, rules | provided mock data | same |
| Ex-custody statements | provided PDFs (`Privatbank Helvetia AG`) | `unriskomega-2026/side-challenge/` |
| Market news | **live**, keyless RSS (Bing → Google → Yahoo), filtered to the portfolio's holdings | X1 |
| Bank / CIO investment view | **mock**, labelled as mock in every payload | `app/external/data/house_view.json` |
| Web search (assistant fallback) | live, keyless DuckDuckGo Lite → news feeds, used only when the client's data cannot answer | `app/external/browse.py` |

## Endpoints

| Method | Path | What it serves |
|---|---|---|
| GET | `/api/health` | liveness, loaded counts, integrity summary, LLM availability |
| GET | `/api/clients` | advisor dashboard rows + filter-tab counts |
| GET | `/api/clients/{ref}` | client detail |
| GET | `/api/clients/{ref}/portfolios/{nr}` | portfolio analysis (SAA, positions, metrics, exposures) |
| POST | `/api/briefing` | the whole pipeline: `{facts, briefing, stages}` with per-stage timings |
| POST | `/api/qa` | follow-up assistant: grounded answer, evidence, sources, provenance |
| GET | `/api/market/search?q=…` | instrument search: facts, coverage, bank view, who holds it |
| POST | `/api/import/ex-custody` | import one of the provided statements by filename |
| POST | `/api/import/ex-custody/upload` | **upload** a PDF statement (multipart: `file`, `client_ref`) |
| GET / DELETE | `/api/import/imported[/{nr}]` | list, detach or clear imported portfolios |
| POST | `/api/dataset/clients/json`, `/api/dataset/reload` | ingest new client files, reload the dataset |

## Architecture

```
provided flat files ─► F5 ingest + joins ─► F3/F4 HTTP projections ─┐
                          (clients.json, reference.json)             │
                                                                     ▼
client_ref ─► R2 facts ─► R3 relevance (16 finding types) ─► R5 actions ─► R4 render ─► UI
                 │                              │                          │
                 ├── X1 market news (live)      │                          ├── template (deterministic)
                 ├── X2 house view (mock)       │                          └── llm (phrasing only)
                 └── B1 ex-custody import ──────┘
```

* Every sentence carries **evidence** — a field path into the source data — and the API declares what it
  could not read (`meta.unavailable`) instead of filling it in.
* Missing values are `null` with a stated reason, never `0`.
* Provenance is explicit: `Simulated` (portfolio), `Live` (market), `Mock` (bank view).

## Layout

```
src/backend/app/      domain/ (ingest, joins, metrics, relevance, ex-custody, search)
                      compose/ (facts, actions, render, qa, format, search)
                      external/ (news, house_view, llm, browse)  api/ (routers)
src/backend/tests/    220 tests + snapshot harness
src/frontend/src/     screens/ (dashboard, client, portfolio, briefing, creative, market, fremdbanken)
                      components/, i18n/ (EN/DE), styles/
tools/                drill.py (unseen-client rehearsal), synth_client.py
notes-task/           PROJECT.md (frozen contracts), component specs, demo script
presentation/         the deck generator
unriskomega-2026/     the provided case material (data, screenshots, brand, statements)
```

## Tests

```bash
cd src/backend
python -m pytest -q                                        # 220 passed, 1 skipped
python -m tests.test_harness --out /tmp/x \
  && python -m tests.test_harness --diff tests/snapshots /tmp/x   # snapshot baseline: clean
cd ../frontend && npm run typecheck && npm run build
python tools/drill.py                                      # 11 PASS / 0 FAIL (8 unseen-client archetypes)
```

The suite is offline and deterministic: it clears the LLM key and disables market/news requests, so a
test run never touches the network and never calls a paid model.

## Known limitations

* **Reading time.** German briefings sit inside the 60-second budget; English ones run 61–69 seconds
  (median 67 s, 224 words) because the three sections are never trimmed below one traceable block each.
* **The model is optional and imperfect.** The rephrase pass is model-dependent: measured, DeepSeek
  rewrites plain prose but often returns terse, figure-dense bank sentences unchanged — the payload
  reports exactly what happened (`renderer`, `llm.applied`, `llm.changed_sentences`) rather than claiming
  a pass that changed nothing.
* **Ex-custody statements are ~69 % "not classified".** 13 of the 19 securities in a provided statement
  have no master row, so the imported portfolio reports two different USD figures on two screens (the
  briefing uses the position's own currency; the portfolio exposure view cannot classify what it cannot
  resolve). The statement's value is also not added to the client's headline AUM.
* **Investment-rule violations are display-only.** The rule engine's own comparison is shown verbatim;
  re-deriving a rule from the data disagrees with the engine on parts of the book, so nothing is
  recomputed.
* **Nothing is cached across processes.** Imports survive a dataset reload by design — clear them before
  a demo (`DELETE /api/import/imported`).
