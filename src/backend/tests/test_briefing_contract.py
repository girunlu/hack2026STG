"""All-47 briefing invariants — the T1 gap.

The harness verified the F2/F3/F4 projections and a handful of hard clients; nothing verified the
*product*: the briefing itself. These tests run ``POST /api/briefing`` for every client and assert the
contract the brief demands — three sections in order, four answered questions, every claim traceable,
bounded actions, the ~60-second budget, no IBAN, and determinism.

Market news runs offline here (``URO_NEWS_OFFLINE``, set in ``conftest``), so the run touches no
network and produces the same bytes twice. The declaration path is still exercised: offline lookups
report themselves unavailable, exactly as a dead network would.
"""

from __future__ import annotations

import json
import re

import pytest

from app.i18n import t

# The brief's own section titles, in its order (task_def.txt §"Required Briefing Content").
BRIEF_TITLES = (
    "Recent Portfolio Development",
    "Portfolio Health Check",
    "Portfolio Outlook & Next Best Actions",
)
QUESTION_KEYS = ("what_happened", "situation", "next", "should_do")

# 210 words is the renderer's target, not a ceiling: the four answers are never trimmed and every
# section keeps at least one block, so data-rich clients land slightly above it while data-thin ones
# read shorter (thinnest observed: 124 words). The band below catches a runaway or an empty briefing.
WORD_MIN, WORD_MAX = 110, 300
READ_SECONDS_MAX = 90

# A claim of performance attribution is impossible with this data (no cost basis, no position
# history) and is the one thing the project forbids outright.
ATTRIBUTION_PATTERNS = (
    "performance contribution",
    "Performancebeitrag",
    "contributed to the return",
    "hat zur Rendite beigetragen",
)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[ ]?(?:[A-Z0-9]{4}[ ]?){2,7}[A-Z0-9]{1,4}\b")


@pytest.fixture(scope="session")
def briefings(api) -> dict[str, dict]:
    """One briefing per client, produced the way the UI produces it."""
    refs = [row["ref"] for row in api.get("/api/clients").json()["rows"]]
    assert len(refs) == 47
    out: dict[str, dict] = {}
    for ref in refs:
        response = api.post("/api/briefing", json={"client_ref": ref, "renderer": "template"})
        assert response.status_code == 200, f"{ref}: {response.status_code} {response.text[:200]}"
        out[ref] = response.json()
    return out


def test_every_client_gets_the_three_brief_sections(briefings):
    for ref, payload in briefings.items():
        sections = payload["briefing"]["sections"]
        assert [s["title"] for s in sections] == list(BRIEF_TITLES), ref
        for section in sections:
            assert section["blocks"], f"{ref}/{section['id']} has no blocks"


def test_every_factual_block_is_traceable(briefings):
    """A block that states a fact cites evidence that resolves; disclosure notes carry none."""
    for ref, payload in briefings.items():
        briefing = payload["briefing"]
        index_ = briefing["evidence_index"]
        for section in briefing["sections"]:
            evidencing = [b for b in section["blocks"] if b["evidence_refs"]]
            assert evidencing, f"{ref}/{section['id']} states nothing traceable"
            for block in section["blocks"]:
                for evidence_ref in block["evidence_refs"]:
                    assert evidence_ref in index_, f"{ref}: {evidence_ref} unresolved"


def test_all_four_questions_are_answered(briefings):
    for ref, payload in briefings.items():
        questions = payload["briefing"]["questions"]
        for key in QUESTION_KEYS:
            assert questions.get(key), f"{ref}: {key} is empty"
        assert questions.get("evidence_refs"), f"{ref}: questions carry no evidence"

def test_per_question_evidence_refs_resolve(briefings):
    """Each of the four question-specific ref arrays must resolve in evidence_index."""
    for ref, payload in briefings.items():
        briefing = payload["briefing"]
        questions = briefing["questions"]
        index_ = briefing["evidence_index"]
        actions = briefing.get("actions", [])

        # Check all four ref arrays exist and resolve
        for key in ("what_happened_refs", "situation_refs", "next_refs", "should_do_refs"):
            refs = questions.get(key, [])
            assert isinstance(refs, list), f"{ref}: {key} is not a list"
            for evidence_ref in refs:
                assert evidence_ref in index_, f"{ref}: {key} contains unresolved ref {evidence_ref}"

        # should_do_refs must be non-empty when actions exist
        if actions:
            assert questions.get("should_do_refs"), f"{ref}: should_do_refs empty despite actions"



def test_findings_and_actions_are_bounded_and_cited(briefings):
    for ref, payload in briefings.items():
        facts = payload["facts"]
        assert facts["findings"], f"{ref} produced no findings"
        for finding in facts["findings"]:
            assert finding["evidence"], f"{ref}/{finding['id']} has no evidence"
            for entry in finding["evidence"]:
                assert entry["label"] and entry["source"] and entry["path"], f"{ref}/{finding['id']}"

        actions = facts["actions"]
        assert len(actions) <= 5, f"{ref}: {len(actions)} action candidates"
        finding_ids = {f["id"] for f in facts["findings"]}
        for action in actions:
            assert action["finding_refs"], f"{ref}/{action['id']} cites no finding"
            assert set(action["finding_refs"]) <= finding_ids, f"{ref}/{action['id']} cites an unknown finding"
            assert action["evidence"], f"{ref}/{action['id']} has no evidence"


def test_briefing_fits_the_read_budget(briefings):
    for ref, payload in briefings.items():
        briefing = payload["briefing"]
        assert WORD_MIN <= briefing["word_count"] <= WORD_MAX, (
            f"{ref}: {briefing['word_count']} words"
        )
        assert briefing["read_seconds_estimate"] <= READ_SECONDS_MAX, ref


def test_gaps_are_declared_never_silent(briefings):
    for ref, payload in briefings.items():
        briefing = payload["briefing"]
        portfolio_gaps = [gap for p in payload["facts"]["portfolios"] for gap in p["data_gaps"]]
        assert payload["facts"]["meta"]["unavailable"] or portfolio_gaps, f"{ref} declares nothing"
        # Every trimmed block is disclosed rather than dropped in silence.
        for section_id, dropped in (briefing["trimmed_blocks"] or {}).items():
            assert dropped > 0 and any(s["id"] == section_id for s in briefing["sections"])


def test_house_view_stances_cite_the_saa_weight(briefings):
    """A house-view stance must be justified by the same weight the SAA table shows.

    The matcher compares the bank's stances against the SAA vocabulary ("Shares", "Bonds", …). Fund
    look-through uses a *finer* taxonomy ("Equities Switzerland"), so a look-through weight can never
    match an SAA category — doing that made CASE-007 report `Shares 4.9%` while the portfolio held
    56.7%. This test pins the evidence to the roll-up that every other target comparison uses.
    """
    payload = briefings["CASE-007"]
    matches = payload["facts"]["house_view"]["matches"]
    shares = [m for m in matches if m["dimension"] == "AssetClass" and m["category"] == "Shares"]
    assert shares, "CASE-007 must match the Shares stance"
    assert abs(shares[0]["evidence"][0]["value"] - 0.567046) < 1e-6

    # Every match's evidence must be an SAA-vocabulary export of the same portfolio.
    portfolio = payload["facts"]["portfolios"][0]
    assert shares[0]["evidence"][0]["path"].startswith("exposures.")


def test_house_view_is_declared_mock(briefings):
    """The brief requires saying which elements are mock — the house view is the one."""
    view = briefings["CASE-007"]["facts"]["house_view"]
    assert view["mock"] is True
    assert view["disclaimer"]
    assert view["source"] and view["as_of"]


def test_no_iban_reaches_a_briefing(briefings):
    for ref, payload in briefings.items():
        raw = json.dumps(payload, ensure_ascii=False)
        assert "IBAN" not in raw, ref
        assert not IBAN_RE.search(raw), ref


def test_no_performance_attribution_is_claimed(briefings):
    for ref, payload in briefings.items():
        raw = json.dumps(payload, ensure_ascii=False).lower()
        for pattern in ATTRIBUTION_PATTERNS:
            assert pattern.lower() not in raw, f"{ref} claims {pattern!r}"


# The five follow-up questions the brief names in its "Interactive Follow-Up Assistant" section. Each
# must produce either a grounded answer (with evidence) or an explicit refusal naming what is missing —
# never a plausible-looking answer to a different question.
BRIEF_EXAMPLE_QUESTIONS = (
    "What is the client's total semiconductor exposure?",
    "Has the client previously raised concerns about volatility?",
    "Which positions contribute most to the current risk?",
    "How would a proposed rebalancing affect the portfolio allocation?",
    "Which open proposal is most relevant to this conversation?",
)

# Questions asked of *other* clients, where the data has a specific answer (or a specific gap) to give.
CLIENT_SPECIFIC_QUESTIONS = (
    ("CASE-017", "What does the client want to avoid?", "fossil", True),
    ("CASE-034", "Which open proposal is most relevant to this conversation?", "draft", True),
    ("CASE-023", "Which positions contribute most to the current risk?", "not available", False),
)


def test_brief_example_questions_are_answered_or_refused(api):
    for question in BRIEF_EXAMPLE_QUESTIONS:
        response = api.post("/api/qa", json={"client_ref": "CASE-007", "question": question})
        assert response.status_code == 200, question
        body = response.json()
        assert body["answer"].strip(), question
        assert body["evidence"] or body["unavailable"], f"{question}: neither evidence nor a declared gap"
        for entry in body["evidence"]:
            assert entry["value"] is not None, question
            assert entry.get("source") and entry.get("path"), question
        # An answer must never be a different question's answer.
        assert "no answer to this question" not in body["answer"], question


def test_client_specific_questions_use_that_client_s_data(api):
    """Each client gets its own answer: the fossil-fuel note, the draft, or a declared gap."""
    for ref, question, expected, grounded in CLIENT_SPECIFIC_QUESTIONS:
        body = api.post("/api/qa", json={"client_ref": ref, "question": question}).json()
        assert expected.lower() in body["answer"].lower(), f"{ref}: {body['answer'][:120]}"
        if grounded:
            assert body["evidence"], ref
        else:
            assert body["unavailable"], f"{ref}: a refusal must name what is missing"


def test_risk_contribution_question_ranks_positions_not_volatility(api):
    """The brief's "which positions drive the risk?" is a position ranking, not a volatility quote."""
    body = api.post("/api/qa", json={
        "client_ref": "CASE-007",
        "question": "Which positions contribute most to the current risk?",
    }).json()

    assert "of the portfolio's risk" in body["answer"]
    assert "Volatility" not in body["answer"]
    assert len(body["evidence"]) == 3
    for entry in body["evidence"]:
        assert entry["path"].endswith("ContributionVolatility")
        assert 0 < entry["value"] < 1  # a fraction of volatility, never the withheld sentinel


def test_unpopulated_risk_series_is_declared_in_the_answer(api):
    body = api.post("/api/qa", json={
        "client_ref": "CASE-023",
        "question": "Which positions contribute most to the current risk?",
    }).json()

    assert "not available" in body["answer"].lower()
    assert body["unavailable"], "the reason must be declared"


def _strip_volatile(payload: dict) -> str:
    """Serialise a briefing without its wall-clock stamps and stage timings.

    ``meta.generated_at``, ``market_meta.fetched_at`` and every stage's ``ms`` describe *when* the
    response was produced; they cannot be byte-stable and are not content. Everything else — findings,
    evidence, wording, ordering — must be identical between two identical calls.
    """
    volatile = {"generated_at", "fetched_at", "ms"}

    def clean(node):
        if isinstance(node, dict):
            return {k: clean(v) for k, v in node.items() if k not in volatile}
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node

    return json.dumps(clean(payload), sort_keys=True)


def test_briefings_are_deterministic(api):
    """Same input, same content — no randomness, no wall-clock dependence."""
    for ref in ("CASE-007", "CASE-027", "CASE-041"):
        first = api.post("/api/briefing", json={"client_ref": ref, "renderer": "template"}).json()
        second = api.post("/api/briefing", json={"client_ref": ref, "renderer": "template"}).json()
        assert _strip_volatile(first) == _strip_volatile(second), ref


def test_language_switch_changes_words_not_numbers(api):
    """Section titles are part of the bilingual product; numbers and findings stay put."""
    english = api.post("/api/briefing", json={"client_ref": "CASE-007", "renderer": "template"}).json()
    german = api.post("/api/briefing", json={"client_ref": "CASE-007", "renderer": "template", "lang": "de"}).json()

    english_titles = [s["title"] for s in english["briefing"]["sections"]]
    german_titles = [s["title"] for s in german["briefing"]["sections"]]

    # The English rendering is the brief's own wording; the German one is translated from the
    # catalogue. The section *ids* stay English in both, so anchors and snapshots keep working.
    assert english_titles == list(BRIEF_TITLES)
    assert german_titles == [
        t("section.recent_development", "de"),
        t("section.health_check", "de"),
        t("section.outlook_actions", "de"),
    ]
    assert german_titles != english_titles
    assert [s["id"] for s in english["briefing"]["sections"]] == [
        s["id"] for s in german["briefing"]["sections"]
    ]

    for payload in (english, german):
        assert WORD_MIN <= payload["briefing"]["word_count"] <= WORD_MAX

    # Data is identical...
    assert [f["score"] for f in english["facts"]["findings"]] == [f["score"] for f in german["facts"]["findings"]]
    assert [f["severity"] for f in english["facts"]["findings"]] == [f["severity"] for f in german["facts"]["findings"]]
    assert [e["value"] for f in english["facts"]["findings"] for e in f["evidence"]] == [
        e["value"] for f in german["facts"]["findings"] for e in f["evidence"]
    ]
    assert len(english["facts"]["actions"]) == len(german["facts"]["actions"])
    # ...only the words differ (German runs slightly longer, which is why word counts are not equated).
    assert [f["title"] for f in english["facts"]["findings"]] != [f["title"] for f in german["facts"]["findings"]]
    assert english["briefing"]["sections"][0]["blocks"][0]["text"] != german["briefing"]["sections"][0]["blocks"][0]["text"]
