# src/ — the UNRISKOMEGA prototype

Everything we build lives here: one backend, one frontend, one contract between them.

## Layout

```
src/
├─ backend/                    Python 3.12 + FastAPI
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ main.py               app, CORS, router registration
│  │  ├─ domain/               F5 (ingest, index, metrics, rail), F6 (crm), R3 (relevance),
│  │  │                        named buy/sell candidates (data only, not yet wired), B1 (excustody), uploads
│  │  ├─ external/             X1 news, X2 house view (+ data/house_view.json, cache/news/)
│  │  ├─ compose/              R2 assembly (facts), R5 actions, R4 renderers, B2 qa
│  │  └─ api/                  HTTP routers; schemas.py holds the JSON contract
│  └─ tests/                   T1 harness + contract tests + snapshots/ baseline
└─ frontend/                   React 18 + Vite + TypeScript
   ├─ public/logos/            copied from unriskomega-2026/assets/logos (read-only source)
   └─ src/
      ├─ App.tsx               F1 shell + routing
      ├─ components/           shared UI kit
      ├─ screens/              dashboard/ client/ portfolio/ briefing/ creative/ fremdbanken/
      ├─ shell/                per-screen nav config + badge context
      ├─ api/client.ts         typed fetch wrapper
      ├─ types.ts              contract types (mirrors api/schemas.py)
      ├─ utils/format.ts       Swiss number/date formatting
      └─ styles/               tokens.css (measured palette) + global.css
```

## Run it

Backend (port 8000):

```
cd src/backend
python -m uvicorn app.main:app --reload --port 8000
```

The ambient Python 3.12 already has every dependency. `uv run uvicorn app.main:app --reload` works too if
you prefer an isolated environment. Interactive API docs: <http://127.0.0.1:8000/docs>.

Frontend (port 5173, proxies `/api` to 8000):

```
cd src/frontend
npm install          # once
npm run dev
```

`npm run build` type-checks (`tsc --noEmit`) and produces a production bundle.

## Configuration — `.env`

`.env` at the repository root is gitignored and read at startup (real environment variables always win).
Everything works without it; the one optional feature it unlocks is the LLM briefing pass:

```
DEEPSEEK_API_KEY=…            # required for `renderer:"llm"` (R4, phrasing only)
URO_LLM_MODEL=deepseek-chat   # optional
URO_LLM_BASE_URL=…            # optional, default https://api.deepseek.com
URO_NEWS_OFFLINE=1            # optional, disables every market-news request
```

With a key set, `GET /api/health` reports `llm_available: true` and both briefing screens ask for the
LLM renderer; without one the endpoint returns **400** naming the variable and the template stays. Paste
the key on the `DEEPSEEK_API_KEY=` line and restart the backend.

## Endpoints

| Method | Path | What it serves |
|---|---|---|
| GET | `/api/health` | liveness + loaded counts + integrity summary |
| GET | `/api/clients` | F2 rows, real filter-tab counts, integrity report |
| GET | `/api/clients/{ref}` | F3 client detail |
| GET | `/api/clients/{ref}/portfolios/{nr}` | F4 portfolio detail |
| POST | `/api/briefing` | `{facts, briefing, stages}` — the whole pipeline, stage-timed |
| GET | `/api/import/reports` · POST `/api/import/ex-custody` | B1 ex-custody report parsing |
| POST | `/api/import/ex-custody/upload` | B1 upload a statement as a **PDF** (multipart: `file` + `client_ref`) — the brief's bonus challenge |
| GET | `/api/import/imported` · DELETE `/api/import/imported/{nr}` · DELETE `/api/import/imported` | imported portfolios: list, detach one, clear all |
| POST | `/api/qa` | B2 follow-up Q&A over the facts bundle |
| GET | `/api/market/search?q=…` | advisor market search — instrument facts, live news, bank view, book exposure. Security-master instruments only: an unknown company is refused with a stated reason (see `STATUS.md` §4.4) |
| `/api/dataset/*` | | client-file ingestion — the unseen-client drill (see below) |

## The unseen-client drill

The case requires new client files "of this shape" to be accepted rather than the dataset being
hardcoded:

```
curl -X POST localhost:8000/api/dataset/clients/json \
     -H 'Content-Type: application/json' --data-binary @newclients.json
curl -X POST localhost:8000/api/dataset/reload
```

Uploads land in `data/uploads/` (never inside the read-only `unriskomega-2026/` tree) and unresolved
security references are reported as data. A successful upload mutates the process-wide dataset, so a
demo starts by restoring the shipped state:

```
rm -f data/uploads/*.json
curl -X POST   localhost:8000/api/dataset/reload
curl -X DELETE localhost:8000/api/import/imported   # clears ex-custody imports (59 -> 57 portfolios)
```

The second call matters: imported ex-custody portfolios live in `data/excustody/imported.json`, which
`POST /api/dataset/reload` does **not** clear — without it the running process keeps serving `EXT-*`
portfolios and `GET /api/health` reports more than 57. Alternatively point `URO_DATA_DIR` and
`URO_EXCUSTODY_DIR` elsewhere.

Set `URO_NEWS_OFFLINE=1` to run without touching the network: every market lookup then declares itself
unavailable instead of fetching. The test suite sets it for the whole session, which is what makes the
briefing invariants deterministic.

## Tests

```
cd src/backend && python -m pytest tests -q          # 150 tests + 1 skipped (the harness drill)
python -m tests.test_harness --out tests/snapshots   # 47 clients -> JSON (≈0.7 s)
python -m tests.test_harness --diff tests/snapshots other-dir
```

## Where the contracts live

- **JSON contract:** `backend/app/api/schemas.py` ⇄ `frontend/src/types.ts`. Change both together.
- **Conventions:** fields ending `_pct` are already percentages; `weight`/`target`/`min`/`max`/`actual`/
  `difference` are fractions (0.567 = 56.70%). Derived values are relative to `data_as_of`, never the
  wall clock.
- **Visual spec:** `unriskomega-2026/ui_reverse/` (measured palette, typography, glyphs, chart geometry)
  is the fidelity reference for the UI kit and screens. Its own static screenshot dataset is *not* used —
  all data comes from the API over the real case data.
- **Component specs:** `notes-task/components/<ID>-*.md`, plus `notes-task/PROJECT.md` §5 for the frozen
  shapes.

## Rules that are not negotiable

- Never modify `unriskomega-2026/` or `task_def.txt`.
- Only `backend/app/domain/ingest.py` reads raw JSON. Everything else goes through F5.
- Never render, log or transmit an `IBAN` — it is real data and is stripped at the API boundary.
- Never invent a value to fill a gap: gaps go into `data_gaps` / `meta.unavailable` and are visible in
  the UI.
- Suitability violations are display-only: explain them from `ViolationPath`, never recompute them.
- The UI is bilingual — English by default, German via `?lang=de` (see `notes-task/PROJECT.md` §5.5);
  numbers are Swiss-formatted (`1'234.56`, `5.20 %`), dates `DD.MM.YYYY`.
- No LLM computes a number, and none is required to build or demo anything up to and including R3.
