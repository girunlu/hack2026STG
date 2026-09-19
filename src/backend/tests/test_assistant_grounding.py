"""The follow-up assistant answers from the client's own analysis, and says so.

The chat is the one place an advisor asks a question in their own words, so it is the easiest place to
lose grounding: a model that phrases freely can state a figure the platform never computed. These pin
the guarantees — the context is the application's own analysis, a figure outside it is refused (in
either unit, and although prose puts punctuation after numbers), and the client's data is tried before
the public web.
"""

from __future__ import annotations

import json

import pytest

from app.compose import facts as facts_module
from app.compose import qa as qa_module
from app.external import llm as llm_module

CLIENT = "CASE-028"


def _bundle(lang: str = "en") -> dict:
    return facts_module.assemble(CLIENT, None, None, lang)


def _context(lang: str = "en") -> dict:
    return qa_module._context_block(_bundle(lang), qa_module._find_portfolio(_bundle(lang), None), lang)


def test_the_context_carries_the_analysis_the_screens_show():
    """Portfolio figures, findings, actions, the bank view and the headlines — the app's own output."""
    context = _context()

    assert context["client"]["ref"] == CLIENT
    assert context["portfolios"], "the client's portfolios must be in the context"
    portfolio = context["portfolios"][0]
    assert portfolio["value"] and portfolio["return_12m_pct"] is not None
    assert portfolio["largest_holding"], "the largest holding is what most questions are about"
    assert context["findings"] and context["findings"][0]["title"]
    assert context["actions"] and context["actions"][0]["action"]
    assert "matches" in context["bank_view"]
    assert "declared_gaps" in context and "data_as_of" in context


def test_the_context_is_scoped_to_one_portfolio_when_asked():
    bundle = _bundle()
    scoped = qa_module._find_portfolio(bundle, "CASE-028-01")
    context = qa_module._context_block(bundle, scoped, "en")

    assert [row["nr"] for row in context["portfolios"]] == ["CASE-028-01"]


# ---------------------------------------------------------------------------
# Grounding guards
# ---------------------------------------------------------------------------

def test_a_figure_outside_the_context_is_refused(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({"answer": "The position is 412% of the portfolio.", "used": ["portfolios"]}),
    )

    outcome = llm_module.answer("how concentrated is it?", _context(), "en")

    assert outcome["applied"] is False
    assert "figure" in outcome["reason"]


def test_a_stored_fraction_may_be_stated_as_a_percentage(monkeypatch):
    """The platform stores 0.9585; an advisor-facing sentence says 95.85 % — the same figure."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({"answer": "One position is 95.85% of the portfolio.", "used": ["portfolios"]}),
    )

    outcome = llm_module.answer("how concentrated is it?", _context(), "en")

    assert outcome["applied"] is True
    assert outcome["used"] == ["portfolios"]


def test_a_figure_followed_by_prose_punctuation_is_the_same_figure(monkeypatch):
    """Measured: a reply ends a sentence with "22.6037%." and the trailing dot must not invent a figure."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({
            "answer": "It returned 22.6037% over 12 months (as of 2026-07-01).",
            "used": ["portfolios"],
        }),
    )

    outcome = llm_module.answer("how did it perform?", _context(), "en")

    assert outcome["applied"] is True, outcome["reason"]


def test_json_float_and_plain_integer_are_the_same_figure():
    """Measured: the context renders 196851.0 and the model writes 196851."""
    assert llm_module.numbers("196851.0") == llm_module.numbers("196851")
    assert llm_module.numbers("12.00") == llm_module.numbers("12")
    assert llm_module.numbers("0.9585") == llm_module.numbers("0.9585")


def test_an_integer_aum_from_the_context_is_accepted(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({
            "answer": "The portfolio holds CHF 196851 and one position is 95.85% of it.",
            "used": ["portfolios", "client"],
        }),
    )

    outcome = llm_module.answer("how big is the portfolio?", _context(), "en")

    assert outcome["applied"] is True, outcome["reason"]


def test_an_unusable_reply_keeps_the_routed_answer(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(llm_module, "_chat", lambda payload: "I cannot help with that.")

    outcome = qa_module.answer(CLIENT, "What is the concentration risk?", None, "en")

    assert outcome["answered_by"] == "rules"
    assert outcome["answer"], "the deterministic answer stands in"


def test_without_a_key_the_routed_answer_stands(monkeypatch):
    for name in llm_module._KEY_ENV:
        monkeypatch.delenv(name, raising=False)

    outcome = qa_module.answer(CLIENT, "What is the concentration risk?", None, "en")

    assert outcome["answered_by"] == "rules"
    assert outcome["source_kind"] == "data"
    assert outcome["evidence"], "the routed answer keeps its evidence"


# ---------------------------------------------------------------------------
# Order: the client's data before the public web
# ---------------------------------------------------------------------------

def test_a_client_question_is_not_answered_from_the_web(monkeypatch):
    """The web is the last resort: a question about this client must be answered from this client."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({"answer": "The largest holding is 95.85% of the portfolio.", "used": ["portfolios"]}),
    )

    def no_web(*args, **kwargs):
        raise AssertionError("the web must not be consulted when the client's data answers")

    monkeypatch.setattr(qa_module, "_answer_web", no_web)
    outcome = qa_module.answer(CLIENT, "How concentrated is this client's portfolio?", None, "en")

    assert outcome["answered_by"] == "llm"
    assert outcome["source_kind"] == "data"
    assert outcome["sources"] == []


def test_the_web_still_answers_a_question_the_data_cannot(monkeypatch):
    """A question with no route in the data still reaches the web — the fallback survives."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(llm_module, "_chat", lambda payload: json.dumps({"answer": "", "used": []}))
    monkeypatch.setattr(
        qa_module,
        "_answer_web",
        lambda question, lang: {
            "answer": "web answer",
            "sources": [{"title": "T", "url": "https://x", "snippet": "S"}],
            "source_kind": "web",
            "unavailable": [],
        },
    )

    outcome = qa_module.answer(CLIENT, "Is NVIDIA worth investing?", None, "en")

    assert outcome["source_kind"] == "web"
    assert outcome["sources"]


def test_the_performance_question_routes_to_performance_analysis():
    """'performed' must reach the performance family, not fall through to the web."""
    assert qa_module._classify("How has this client portfolio performed?")[0] == "performance"
    assert qa_module._classify("What is the concentration risk?")[0] == "concentration"


def test_a_decline_is_not_an_answer(monkeypatch):
    """Measured: the model answered an out-of-context question with a non-answer plus unrelated
    portfolio observations, which read as a canned refusal and blocked the web lookup."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({
            "answered": False,
            "answer": "",
            "used": [],
        }),
    )

    outcome = llm_module.answer("is NVIDIA worth investing?", _context(), "en")

    assert outcome["applied"] is False
    assert outcome.get("declined") is True
    assert outcome["answer"] is None


def test_a_declined_instrument_question_reaches_the_web(monkeypatch):
    """The advisor asked about a company the client's data has no view on: look it up."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({"answered": False, "answer": "", "used": []}),
    )
    monkeypatch.setattr(
        qa_module,
        "_answer_web",
        lambda question, lang: {
            "answer": "web answer",
            "sources": [{"title": "T", "url": "https://x", "snippet": "S"}],
            "source_kind": "web",
            "unavailable": [],
        },
    )

    outcome = qa_module.answer(CLIENT, "Should I buy Nestle?", None, "en")

    assert outcome["source_kind"] == "web"
    assert outcome["sources"], "the advisor gets sources rather than a non-answer"


def test_without_a_key_an_instrument_question_keeps_the_routed_answer(monkeypatch):
    """A missing key must not change which answer the platform gives on its own data."""
    for name in llm_module._KEY_ENV:
        monkeypatch.delenv(name, raising=False)

    outcome = qa_module.answer(CLIENT, "Which instruments would you switch?", None, "en")

    assert outcome["answered_by"] == "rules"
    assert outcome["source_kind"] == "data"
