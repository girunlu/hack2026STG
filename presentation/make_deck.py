"""One-shot generator for the final-presentation deck (brief: 'short PowerPoint presentation').

Every number on a slide is measured in this session or taken from the verified-facts list.
The "(in flight)" tag is no longer used — all tagged items shipped.
"""
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
TITLE = prs.slide_layouts[0]
BULLETS = prs.slide_layouts[1]


def slide(title, points):
    s = prs.slides.add_slide(BULLETS)
    s.shapes.title.text = title
    body = s.placeholders[1].text_frame
    body.clear()
    for i, p in enumerate(points):
        para = body.paragraphs[0] if i == 0 else body.add_paragraph()
        para.text = p
        para.font.size = Pt(20 if not p.startswith("  ") else 16)
    return s


# 1. Title
t = prs.slides.add_slide(TITLE)
t.shapes.title.text = "From Ping to Pitch — AI Briefing Assistant"
t.placeholders[1].text = (
    "UNRISKOMEGA AG · Hackathon 2026\n"
    "A feature prototype inside a mocked URO Advisor Pro — never in the live URO environment"
)

# 2. The advisor problem
slide("The advisor problem", [
    "A short-notice client call pulls data from many systems",
    "  performance, allocation, suitability, rules, proposals, notes, news, house view",
    "The information exists — but it is distributed",
    "Building a coherent storyline by hand takes time advisors don't have",
    "Goal: one click → a client-specific briefing readable in ~60 seconds",
])

# 3. Trigger and user flow
slide("Trigger and complete user flow", [
    "1. Advisor opens the client or portfolio in the mocked URO Advisor Pro",
    "2. Clicks Generate Briefing — the only entry point",
    "3. Pipeline: collect → analyse → rules → market → house view → actions → compose",
    "4. Briefing screen: three sections, four answers, evidence traces, stage timings",
    "5. Follow-up Q&A and a printable one-pager reuse the same evidence bundle",
])

# 4. The 60-second briefing
slide("The 60-second briefing", [
    "Three sections: Recent Development · Health Check · Outlook & Next Actions",
    "Four answers: what happened / current situation / what next / what to do",
    "Measured: 207–231 words, 62–69 seconds across all 48 clients (EN); 43 of 48 above 210-word budget",
    "48 of 48 briefings have every evidence ref resolvable (per-question: what_happened_refs, situation_refs, next_refs, should_do_refs)",
    "48 of 48 declare at least one information gap honestly",
])

# 5. Example scenario — Lena Vogt (SCEN-001)
slide("Example scenario — Lena Vogt (SCEN-001)", [
    "Private client, CHF 250'000 property purchase planned for 2027",
    "Portfolio: 62% ASML, 18% Qualcomm, 15% CHF bonds, 5% cash",
    "−11.90% over 12 months, −16.51% over 3 months",
    "Risk profile MaxVola 0.075 vs portfolio volatility 0.184",
    "62% EUR against a CHF base — currency concentration",
    "Action #1: secure liquidity for the property purchase",
])

# 6. What the briefing cannot answer
slide("What the briefing cannot answer", [
    "Per-position return attribution: no cost basis, no position history in the data",
    "We report risk contribution instead and say so explicitly",
    "Isolated vs market-wide move: no index or sector time series exists",
    "Closest honest signals: sector-concentration finding and sector-specific headlines",
    "Honesty over polish: gaps declared, numbers never invented",
])

# 7. Data sources used
slide("Data sources used", [
    "48 clients, 58 portfolios, 703 positions, 504 securities, 275 held ISINs",
    "48'101 fund mappings, 180 suitability violations, 206 proposals",
    "153 client notes across 53 distinct, 19-tag vocabulary, 54 rule rows",
    "Market news: live fetch, phrase-cleaned, filtered to held equities, cached",
    "House view: curated UBS CIO Market Outlook 2026 — declared mock in payload and UI",
])

# 8. Analysis and recommendation logic
slide("How the analysis and recommendation logic works", [
    "16 finding types (the previous 14 plus sector_concentration and esg_alignment)",
    "Named buy/sell/switch: 19 of 47 shipped clients get a nameable move; 18 of 48 render an instrument_candidate action",
    "CASE-045: draft exits Novartis 41%, builds UBS SMI ETF; CASE-007 buys Swisscom + Nestlé for the Shares gap",
    "CASE-007: fossil-fuel note excludes Exxon, TotalEnergies, Equinor — the exclusion is reported",
    "sector_concentration: 15 of 48 clients fire (CASE-028 Financials 95.85%, SCEN-001 Information Technology 80.0%)",
    "News: phrase-based cleaning (13 master rows), ASML 1→5 headlines, biggest-holding-first",
])

# 9. Technical architecture
slide("Technical architecture", [
    "Python 3.12 + FastAPI backend; React 18 + Vite + TypeScript frontend",
    "Keystone contract: BriefingFacts JSON — R3 produces, R4/R5/R6 consume",
    "Bilingual EN/DE with identical findings and numbers",
    "150 tests passing + 1 skipped, offline and deterministic",
    "Evidence resolver gate, IBAN scan, diff-clean snapshot baseline",
])

# 10. Mock data vs production integrations
slide("Mock data vs production integrations", [
    "Mock: house/CIO view (declared in payload and UI), URO chrome, fictional clients",
    "Real: instruments and live news for them; all portfolio maths from case data",
    "Production would connect: URO APIs, licensed news feeds, internal CIO publications, bank CRM",
    "31 mocked-UI defects fixed end-to-end and re-verified in the browser",
    "Unseen-client drill: new client files upload, validate and brief without code changes",
])

# 11. Bonus features completed
slide("Bonus features completed", [
    "Ex-custody PDF import: virtual Fremdbanken portfolios behave like native ones",
    "Interactive follow-up Q&A: grounded answers, says unavailable when it must",
    "Printable one-pager: client sheet with the same traceability",
    "Named-instrument recommendations from Entwurf proposals and the recommendation list",
    "Per-question evidence refs: what_happened_refs, situation_refs, next_refs, should_do_refs — all resolvable",
    "ESG alignment finding: 1 of 48 clients breaches its floor (CASE-016, score 3.10 vs 5.714)",
])

# 12. Verification posture
slide("Verification posture", [
    "150 tests passing + 1 skipped",
    "48-client harness with a diff-clean snapshot baseline",
    "Evidence resolver gate passes over all 48 clients",
    "IBAN scan, determinism check, browser re-verification in EN and DE",
    "Demo clients: CASE-007, CASE-028, CASE-027, CASE-017, CASE-012, CASE-008, SCEN-001",
])

prs.save("D:/hack26/presentation/UNRISKOMEGA-briefing-assistant.pptx")
print("deck written")
