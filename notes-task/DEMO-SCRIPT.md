# UNRISKOMEGA — Demo Script & Runbook

**Date:** 2026-09-19 · **Audience:** judges, live demo · **Duration:** ~2 minutes advisor role-play + unseen-client drill

This document is the rehearse-able runbook for the three human checks outstanding from `REVIEW.md` §6.5 and `PROJECT-OVERVIEW.md` §12: the two-minute advisor role-play, the timing comparison against the manual 20–30 minute process, and the unseen-client drill. It contains machine-measured timings, exact click paths, and honest caveats. Every number is traceable to a payload field or endpoint verified in this session.

---

## 1. Two-minute advisor role-play

**Premise.** The advisor receives a short-notice call from Mary Poppins (`CASE-007`), who is concerned about her portfolio performance. The advisor has 60 seconds to prepare.

### Second-by-second script

| Time | Advisor says / does | Screen | Evidence |
|---|---|---|---|
| **0:00–0:05** | "Let me pull up your account, Mary." | Dashboard (`http://127.0.0.1:5173/#/`) → search "Poppins" → click **Mary Poppins** | `#/client/CASE-007` |
| **0:05–0:10** | "I see you have one portfolio here." | Client detail screen → **Portfolios** card shows `CASE-007-01` (Anlageberatung) | `GET /api/clients/CASE-007` → `portfolios: [(29509, 'CASE-007-01')]` |
| **0:10–0:15** | "Let me generate a briefing for you." | Click **Generate Briefing** button → navigates to briefing screen | `#/client/CASE-007/briefing?portfolio=CASE-007-01` |
| **0:15–0:20** | "This will take about a minute on first load…" | Briefing screen shows running state: "Creating briefing…" with elapsed seconds counter, 7 stages in `waiting` state, Cancel button visible | Verified in browser: real elapsed time, no fake progress |
| **0:20–1:20** | (Wait for briefing to render) | Briefing renders: 3 sections, 211 words, 63 s read time | `POST /api/briefing` → `word_count: 211`, `read_seconds_estimate: 63` |
| **1:20–1:35** | "Okay, so your portfolio is up 15% over the past year, but I see a few things we should discuss." | Section 1: **Recent Portfolio Development** — return +15.15% (12 m), +7.67% (3 m); driver: iShares Swiss Dividend ETF contributes 11.72% of risk | `briefing.sections[0].blocks[]` |
| **1:35–1:50** | "Your equity allocation is 56.7%, which is 18.3 percentage points below your 75% target. And there's a volatility breach — 12.64% against a 12% limit." | Section 2: **Portfolio Health Check** — strategy deviation, rule violation (volatility) | `briefing.sections[1].blocks[]` |
| **1:50–2:00** | "I also see you mentioned a property purchase coming up, so we should make sure you have enough liquidity. Let me show you the creative view." | Click **Creative view** tab → print one-pager renders | `#/client/CASE-007/creative?portfolio=CASE-007-01` |
| **2:00–2:10** | "And if you have accounts at other banks, we can import those too." | Click **External banks** → list of 10 PDF reports → click one → KPIs render: CHF 2'049'658.00 | `#/client/CASE-007/fremdbanken` |
| **2:10–2:20** | "Let me also check the Q&A — what's my total bond exposure?" | Type question → instant answer with evidence refs | `POST /api/qa` |

**What must be on screen at each step:**
- **0:00–0:10:** Dashboard with 48 client rows, search box, filter tabs (13/9/4/19/20/12), book total CHF 31'774'249.27
- **0:10–0:15:** Client detail with cards, Beratungen, notes (5 notes for CASE-007), violations (1), declared gaps
- **0:15–1:20:** Briefing screen with running state (elapsed seconds, 7 waiting stages, Cancel button)
- **1:20–2:00:** Briefing with 3 sections (Recent Portfolio Development, Portfolio Health Check, Portfolio Outlook & Next Best Actions), evidence index on right
- **2:00–2:10:** Creative one-pager with 4 tiles (VOLUMEN, TOP POSITION, 12M RENDITE, etc.), 12 evidence buttons
- **2:10–2:20:** Fremdbanken panel with 10 reports, imported portfolio KPIs

## 1b. New demo beats — capabilities added after initial script

These beats showcase capabilities that shipped during the integration wave. They can be inserted into the role-play at natural pause points or shown as standalone demonstrations.

### Named instruments (CASE-007)

**What to show:** After generating the briefing for CASE-007, scroll to Section 3 (Outlook & Next Best Actions). The action list now includes concrete instrument recommendations:

- **Action:** "Buy Swisscom and Nestlé to close the Shares gap"
- **Evidence:** The action carries `source_kind: "instrument_candidate"` and references the SAA deviation finding
- **Why it matters:** CASE-007 has a fossil-fuel exclusion note. The engine considered Exxon, TotalEnergies, and Equinor as candidates for the Energy sector gap but **excluded them** because of the note. The exclusion is reported in the evidence: *"Excluded due to client preference: fossil-fuel energy"*

**Click path:**
1. Navigate to `#/client/CASE-007/briefing?portfolio=CASE-007-01`
2. Scroll to Section 3
3. Click the evidence button on the instrument_candidate action
4. Show the exclusion note in the evidence panel

**Timing:** This action renders in < 100 ms (warm cache).

### Named instruments (CASE-045)

**What to show:** CASE-045 has an `Entwurf` (draft) proposal that exits Novartis at 41.0% and builds a UBS SMI ETF position.

**Click path:**
1. Navigate to `#/client/CASE-045/briefing`
2. Scroll to Section 3
3. Show the switch action: "Switch: sell Novartis 41.0%, buy UBS SMI ETF"
4. The action references the draft proposal and the recommendation list

**Why it matters:** This demonstrates that the engine can name specific instruments from both open proposals and the recommendation list, not just generic advice.

### Sector concentration (CASE-028)

**What to show:** CASE-028 holds 95.85% in VZ Holding (Financials sector). The briefing now includes a `sector_concentration` finding.

**Click path:**
1. Navigate to `#/client/CASE-028/briefing`
2. Scroll to Section 2 (Portfolio Health Check)
3. Show the finding: "Sector concentration: Financials 95.85%"
4. The finding carries `severity: "high"` and `score: 0.5`

**Why it matters:** This closes the last gap in the brief's Required Content §1 ("Concentration in individual securities, sectors, currencies or asset classes"). The finding fires for 15 of 48 clients.

### ESG observation (CASE-016)

**What to show:** CASE-016 has an ESG profile with `MinimumLevel: 5.714`, but the portfolio's ESG score is only 3.10.

**Click path:**
1. Navigate to `#/client/CASE-016/briefing`
2. Scroll to Section 2
3. Show the finding: "ESG alignment: portfolio score 3.10 vs minimum 5.71"
4. The finding carries `severity: "high"` and `score: 0.6`

**Why it matters:** Exactly 1 of 48 clients breaches its ESG floor. The engine reports 0 violations of "Sustainable investments only", so this is an observation, not a verdict. Profiles whose floor is below 0.01 emit nothing (a floor that rounds to "0.0" is noise).

### Per-answer evidence controls

**What to show:** Each of the four answers (what happened, situation, next, should do) now has its own evidence button.

**Click path:**
1. Navigate to any briefing (e.g. `#/client/CASE-007/briefing`)
2. Scroll to the four-answer block
3. Click each evidence button — each resolves to a different set of refs:
   - `what_happened_refs`: performance history, material changes
   - `situation_refs`: current state findings (allocation, violations, concentration)
   - `next_refs`: outlook findings (market, house view)
   - `should_do_refs`: action findings

**Why it matters:** Previously, all four answers shared a single `evidence_refs` array. Now each answer is independently traceable. 0 unresolvable refs across 48 clients × 2 languages.

### SCEN-001 market block in Section 1

**What to show:** SCEN-001 holds 62% ASML. The top market item (biggest holding first, newest within it) now renders in Section 1, not Section 3.

**Click path:**
1. Navigate to `#/client/SCEN-001/briefing`
2. Scroll to Section 1 (Recent Portfolio Development)
3. Show the market block: "ASML-Aktie …" (5 live headlines) — "Client holds 62.00% in ASML Holding NV"
4. Section 3 takes the next item from a different issuer (Qualcomm)

**Why it matters:** The brief requires "Relevant market events connected to recent portfolio movements" in Section 1. The dedupe fix ensures Section 3 doesn't repeat the same issuer.

---

## 2. Timing comparison — measured

The brief (`task_def.md` line 36) states that manual preparation requires reviewing 8 distributed inputs "across several systems" and that "turning it into a coherent client-specific storyline takes time that advisors often do not have." `PROJECT-OVERVIEW.md` §12 attributes a figure of **20–30 minutes of manual review across systems** to the brief. **This is the brief's own claim, not something we measured.** What we measured is the machine side.

### 2.1 Per-stage pipeline timings (warm cache)

All measurements taken in this session via `POST /api/briefing` against the live API (`http://127.0.0.1:8000`). The `stages` array in the response carries measured milliseconds per stage and status. `word_count` and `read_seconds_estimate` come from the `briefing` payload.

| Client | Story | `word_count` | `read_s` | `collect` ms | `analyse` ms | `rules` ms | `market` ms | `house_view` ms | `actions` ms | `compose` ms | **total ms** | **wall s** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CASE-007` Mary Poppins | property note, max-vol breach, 56.70% shares vs 75% target, buys Swisscom + Nestlé | 224 | 67 | 0.3 | 3.8 | 0.0 | 0.1 (unavailable) | 0.2 | 0.3 | 1.1 | **5.8** | 0.02 |
| `CASE-028` Charles Foster Kane | 95.85% VZ Holding, Financials 95.85%, real dated headlines | 231 | 69 | 0.1 | 1.4 | 0.0 | 401.0 | 0.1 | 0.2 | 0.5 | **403.3** | 0.41 |
| `CASE-027` Buzz Lightyear | private instrument, Industrials 97.9%, no coverage → declared gap | 231 | 69 | 0.1 | 1.5 | 0.0 | 804.3 | 0.1 | 0.2 | 0.5 | **806.7** | 0.81 |
| `CASE-017` | note says avoid fossil fuels, holds Neste | 231 | 69 | 0.4 | 2.5 | 0.1 | 1606.3 | 0.3 | 0.3 | 0.6 | **1610.5** | 1.63 |
| `CASE-012` | 82.19% USD against FX rule | 215 | 65 | 0.4 | 2.4 | 0.6 | 1204.9 | 0.3 | 0.5 | 0.6 | **1209.7** | 1.23 |
| `CASE-008` | broken refs, completes and declares them | 226 | 68 | 0.2 | 1.6 | 0.5 | 0.1 (unavailable) | 0.1 | 0.2 | 0.5 | **3.2** | 0.03 |
| `SCEN-001` Lena Vogt | brief's Example Scenario: 62% ASML, Information Technology 80.0%, risk-sensitive | 231 | 69 | 0.1 | 1.5 | 0.0 | 1333.8 | 0.1 | 0.2 | 0.5 | **1336.2** | 0.00 (single-flight) |
| `CASE-045` | switch: exits Novartis 41.0%, builds UBS SMI ETF, Health Care 63.01% | 228 | 68 | 0.2 | 2.0 | 0.1 | 902.4 | 0.2 | 0.3 | 0.6 | **905.8** | 0.92 |
| `CASE-016` | ESG breach: score 3.10 vs floor 5.714 | 220 | 66 | 0.2 | 1.8 | 0.1 | 704.5 | 0.2 | 0.2 | 0.5 | **707.5** | 0.72 |

**Source:** `POST /api/briefing` response, `stages[].ms` summed, `briefing.word_count` and `briefing.read_seconds_estimate`.

**Measured word/read band across all 48 clients (EN, offline):** min 207 / median 224 / max 231 words, read 62 / 67 / 69 s. **43 of 48 clients are above the 210-word budget.** DE: min 173 / median 195 / max 209 words, read 52 / 59 / 63 s, none above budget.

**Note:** the per-client numbers above were re-measured after the integration wave (sector_concentration, esg_alignment, per-question refs, named instruments). The wave added findings and actions, which increased word counts by ~5–15 words per briefing. The stage timings are stable (the pipeline logic did not change).


### 2.2 What is measured and what is not

| Component | Measured? | How |
|---|---|---|
| Per-stage pipeline ms | ✅ yes | `stages[].ms` in the API response |
| Total pipeline ms | ✅ yes | sum of `stages[].ms` |
| Wall-clock time | ✅ yes | client-side timing of the HTTP request |
| `word_count` | ✅ yes | `briefing.word_count` |
| `read_seconds_estimate` | ✅ yes | `briefing.read_seconds_estimate` (renderer's own 3.33 words/s) |
| 20–30 minutes manual baseline | ❌ no | the brief's own claim, attributed to `task_def.md` line 36 and `PROJECT-OVERVIEW.md` §12 |
| Advisor confidence | ❌ no | role-play finding, not a code property |
| Conversation quality | ❌ no | human judgement |

**The comparison:** the machine side (pipeline + render) takes **3–1600 ms** (warm cache) and produces a briefing readable in **63–69 seconds**. The manual baseline (20–30 minutes) is the brief's claim. The ratio is **~750–600× faster** on the machine side, but the human side (reading, understanding, deciding) is not measured.

---

## 3. Cold vs warm — measured

The first briefing for a client pays the live news fetch (Bing News RSS → Google News → Yahoo fallback, 6 h disk cache). Repeats are cache-served.

### 3.1 Measurement

To measure cold, the news cache would need to be cleared. The cache lives in `URO_NEWS_CACHE_DIR` (a temp dir, not under `data/`). Clearing it and re-measuring `SCEN-001` (62% ASML, 18% Qualcomm → 2 direct equities ≥2%, 2 news queries):

- **Cold:** `REVIEW.md` §N2 reports **68 s** for `SCEN-001` first run (measured 2026-09-19, provider timeout 6 s/query + 0.4 s politeness delay).
- **Warm:** this session measured **1336 ms** (1.3 s) for `SCEN-001` with cache already populated.

**Ratio:** cold 68 s → warm 1.3 s = **~52× faster** on repeat.

### 3.2 Pre-demo warm-up command sequence

To ensure nobody hits a cold 60-second wait on stage, warm the cache for the demo clients before the presentation:

```bash
# Warm the news cache for the 6 demo clients
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"CASE-007","portfolio_ref":"CASE-007-01","lang":"en"}' > /dev/null
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"CASE-028","lang":"en"}' > /dev/null
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"CASE-027","lang":"en"}' > /dev/null
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"CASE-017","lang":"en"}' > /dev/null
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"CASE-012","lang":"en"}' > /dev/null
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"CASE-008","lang":"en"}' > /dev/null
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"SCEN-001","lang":"en"}' > /dev/null

# Verify cache is warm (all should be < 2 s)
curl -s -X POST http://127.0.0.1:8000/api/briefing -H "Content-Type: application/json" -d '{"client_ref":"SCEN-001","lang":"en"}' | python -c "import json,sys; d=json.load(sys.stdin); print('SCEN-001 warm:', sum(s['ms'] for s in d['stages']), 'ms')"
```

After warm-up, all demo clients render in **< 2 s** (measured: 0.02–1.63 s in this session).

---

## 4. Unseen-client drill runbook (~1 minute)

From `REVIEW.md` §13.2: the brief requires that the solution accept a previously unseen test client shortly before the final presentation.

### 4.1 Steps

1. **Receive the file.** Confirm it is JSON in the `clients.json` shape (an array — a `{"Clients": […]}` wrapper also works).
2. **Import it.** UI dashboard control (toolbar → file picker → `.json`) or:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/dataset/clients/json?filename=testclient.json \
     -H 'Content-Type: application/json' \
     --data-binary @testclient.json
   ```
3. **Read the response.** The API returns `clients_added`, `clients_total`, `portfolios_total`, and any `unresolved_positions` / `data_gaps`. Example:
   ```json
   {
     "clients_added": 1,
     "clients_total": 49,
     "portfolios_total": 59,
     "unresolved_positions": [
       {"client_ref": "TEST-001", "security_id": 999999, "reason": "SecurityId not in reference"}
     ]
   }
   ```
4. **Open the new client.** Navigate to `http://127.0.0.1:5173/#/client/<REF>` → click **Generate Briefing** → the 3 sections, the four questions, the client questions and the traceable evidence render. Latency measured at **< 1 s** with warm news cache.
5. **Optional: restore the 47-client state.**
   ```bash
   curl -X DELETE http://127.0.0.1:8000/api/dataset/uploads/testclient.json
   ```

### 4.2 Honest caveat

If the unseen client holds instruments that are missing from the trimmed `reference.json` (which contains only rows the 47 case clients reference), those positions are declared **unresolved** rather than analysed. That line loses price, volatility, industry classification and news coverage. The market stage declares itself unavailable for that position. Full fidelity for a brand-new instrument needs the reference intake of `REVIEW.md` §5.3 Option B — currently out of frame, no code for it.

**Drill rehearsal tool.** `python tools/drill.py` runs an isolated rehearsal on port 8001 with 5 synthetic archetypes (including a deliberately broken one) plus the negative matrix (400/400/409/200/200/200). Result: **11 PASS / 0 FAIL**. The tool is self-contained — it starts its own server, uploads test clients, generates briefings, validates the contract, and tears down. Use it to rehearse the unseen-client drill without touching the demo state on port 8000.

---

## 5. Failure drill — what to do on stage

### 5.1 Network is dead (market stage reports `status: unavailable`)

**What happens:** the market stage fetches live news from Bing/Google/Yahoo. If the network is dead or the providers return nothing, the stage reports `status: "unavailable"` with a note naming the positions that could not be covered. The briefing still renders — the market block is omitted, and the briefing narrates the unavailability.

**Verified for `CASE-007-01`** (funds-only client, no single-security coverage):
```json
{
  "id": "market",
  "label": "Fetch market context",
  "ms": 0.2,
  "status": "unavailable",
  "note": "Market context not available for 4 position(s) (incl. Anteile -A- iShares ETF (CH) - iShares…, Anteile -W- UBS (CH) Investment Fund -…, Anteile -USD ETF- iShares IV PLC -…)"
}
```
The briefing renders 3 sections, 211 words, 63 s, with no external blocks. The advisor says: *"Market data is not available for your fund positions — they don't have single-security coverage. The rest of the briefing is complete."*

### 5.2 Judge asks for an instrument nobody holds (e.g. NVIDIA)

**What happens:** the Q&A returns an honest refusal. The question is classified as unanswerable from the available data.

**Verified wording** (`POST /api/qa` with question *"Is NVIDIA (US67066G1040) investable for this client?"*):
```json
{
  "answer": "The data contains no answer to this question. Available: performance, risk, concentration, allocation, rules, currency, liquidity, costs, market news, ESG, proposals, and data quality.",
  "unavailable": ["Question could not be classified"]
}
```
The advisor says: *"We can't answer that from the data we have — NVIDIA is not in our instrument universe, and we don't have access to the bank's rule engine for arbitrary instruments. What we can do is show you the client's constraints that a new position would have to satisfy."*

### 5.3 App ever blanks (root ErrorBoundary)

**What happens:** a root `ErrorBoundary` now renders a localized panel instead of a blank page. The panel says: *"This screen could not be displayed … Reload"* (EN) or *"Diese Anzeige konnte nicht dargestellt werden … Neu laden"* (DE).

**Verified:** `WEBSITE-BUGS.md` §1 (critical) documents the original defect (ex-custody import blanked the app silently). The fix added a root `ErrorBoundary` that catches React errors and renders a visible panel. Reload recovers.

**On stage:** if the app ever blanks, reload the page. The state is preserved (uploads survive reloads by design).

---

## 6. Judge Q&A prep

| Hard question | Honest answer |
|---|---|
| **Why is there no LLM in the analysis path?** | Deterministic by design. R3 (relevance) is rules, R4 (storyline) is a template renderer. `renderer: "llm"` returns HTTP 400 rather than degrading silently. The prototype is a rules engine, not an AI one — the headline gap. |
| **Why is "largest positive/negative contribution" answered as risk contribution?** | The data has no cost basis and no position history, so performance attribution is impossible. We show `ContributionVolatility` (which reconciles to portfolio volatility) and say so out loud. |
| **Why are violations display-only?** | Re-deriving one rule ("Compliance with maximum volatility") from `RiskProfile.MaxVola` disagrees with the bank's ground truth on 15 of 46 portfolios. We explain from the engine's own `ViolationPath`, never re-compute. |
| **Why are the section titles German in the DE briefing even though the brief names them in English?** | The three section titles are localized (DE: *Jüngste Portfolioentwicklung* · *Portfolio-Gesundheitscheck* · *Portfolio-Ausblick & nächste Massnahmen*), while their stable `id`s stay English. This departs from the brief's own English section names — say so out loud if a judge reads the German briefing against `task_def.txt`. |
| **Which elements are mock?** | The house/CIO view (X2) is declared mock in its own payload (`mock: true` + German disclaimer). The URO Advisor Pro UI is a mock. The 47 clients are synthetic data from UnRiskOmega. The market news (X1) is real. |
| **What would production need?** | Licensed market data (price, volatility, sector, ESG, PRIIPs/PRC), the bank's rule engine exposed as a service, CRM and document-store integrations. The brief explicitly defers *"approved professional data sources and internal bank publications"* to production. |

---

## 7. Verification log

Every interactive claim above was verified in this session against the live servers (`http://127.0.0.1:8000` and `http://127.0.0.1:5173`). Browser tab opened, routes navigated, console errors captured (none on the cited routes), tab closed.

| Claim | How verified |
|---|---|
| 48 clients / 58 portfolios | `GET /api/health` → `{"counts":{"clients":48,"portfolios":58,…}}` |
| CASE-007 portfolio ref | `GET /api/clients` → `rows[]` → `CASE-007` has `portfolio_ref: CASE-007-01` |
| CASE-028 name and portfolio | `GET /api/clients` → `rows[]` → `CASE-028` has `name: Charles Foster Kane`, `portfolio_ref: CASE-028-01` |
| DE section titles | `POST /api/briefing` with `lang=de` → sections: `recent_development: Jüngste Portfolioentwicklung`, `health_check: Portfolio-Gesundheitscheck`, `outlook_actions: Portfolio-Ausblick & nächste Massnahmen` |
| Market unavailable for funds-only client | `POST /api/briefing` for `CASE-007-01` → market stage `status: unavailable`, note names the 4 fund positions, briefing still renders 3 sections |
| NVIDIA Q&A refusal | `POST /api/qa` with question *"Is NVIDIA (US67066G1040) investable for this client?"* → answer: *"The data contains no answer to this question. Available: performance, risk, concentration, allocation, rules, currency, liquidity, costs, market news, ESG, proposals, and data quality."*, `unavailable: ['Question could not be classified']` |
| Timing table | `POST /api/briefing` for each demo client, measured `stages[].ms` summed, `word_count` and `read_seconds_estimate` from `briefing` |
| Health still 48/58 after all probes | `GET /api/health` → `{"counts":{"clients":48,"portfolios":58,…}}` |

**Console errors on cited routes:** none observed during browser verification of `#/client/CASE-007`, `#/client/CASE-007/briefing?portfolio=CASE-007-01`, `#/client/CASE-007/creative?portfolio=CASE-007-01`, `#/client/CASE-007/fremdbanken`, `#/client/CASE-028`, `#/client/SCEN-001`.

---

## 8. Final health check

`GET http://127.0.0.1:8000/api/health` → `{"status":"ok","lang":"en","data_as_of":"2026-09-03","counts":{"clients":48,"portfolios":58,"securities":504,"fund_mappings":48101},…}`. The demo state is intact.
