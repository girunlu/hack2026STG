"""The follow-up assistant's web sources.

An advisor-facing answer that gives up because one free endpoint refused a connection is worse than
one that asks a second source, so the chain is asserted here — including the case where nothing
answers, which must be *declared* rather than turned into an unsourced paragraph.
"""

from __future__ import annotations

import json

import pytest

from app.compose import qa as qa_module
from app.external import browse, llm as llm_module


@pytest.fixture()
def online(monkeypatch):
    monkeypatch.delenv("URO_WEB_OFFLINE", raising=False)
    monkeypatch.delenv("URO_NEWS_OFFLINE", raising=False)


def test_search_uses_the_web_provider_when_it_answers(monkeypatch, online):
    monkeypatch.setattr(browse, "_lite_results", lambda q, l: [{"title": "T", "url": "https://x", "snippet": "S"}])
    result = browse.search("is NVIDIA worth investing?")

    assert result["provider"] == browse.PROVIDER
    assert [item["url"] for item in result["items"]] == ["https://x"]
    assert result["unavailable"] == []


def test_search_falls_back_to_the_news_feeds(monkeypatch, online):
    """The web endpoint refuses connections intermittently; the feeds are the second source."""
    monkeypatch.setattr(browse, "_lite_results", lambda q, l: [])
    monkeypatch.setattr(
        browse,
        "_news_results",
        lambda q, l, lang: [{"title": "Nvidia-Backed Firm Files for IPO", "url": "https://news/x", "snippet": "Reuters"}],
    )
    result = browse.search("is NVIDIA worth investing?")

    assert result["provider"] == browse.NEWS_PROVIDER
    assert result["items"][0]["title"].startswith("Nvidia")
    assert "news feeds" in result["unavailable"][0]


def test_search_declares_when_no_source_answers(monkeypatch, online):
    monkeypatch.setattr(browse, "_lite_results", lambda q, l: [])
    monkeypatch.setattr(browse, "_news_results", lambda q, l, lang: [])
    result = browse.search("is NVIDIA worth investing?")

    assert result["provider"] is None
    assert result["items"] == []
    assert "no source answered" in result["unavailable"]


def test_offline_declares_itself_without_asking_anyone(monkeypatch):
    monkeypatch.setenv("URO_NEWS_OFFLINE", "1")

    def explode(*args, **kwargs):
        raise AssertionError("no provider may be asked while offline")

    monkeypatch.setattr(browse, "_lite_results", explode)
    monkeypatch.setattr(browse, "_news_results", explode)
    result = browse.search("is NVIDIA worth investing?")

    assert result["items"] == []
    assert "switched off" in result["unavailable"][0]


def test_the_web_provider_is_retried_once_before_giving_up(monkeypatch):
    """One refused connection is not a reason to lose the advisor's answer."""
    calls = {"n": 0}
    html = (
        "<html><body><table>"
        "<tr><td>1.</td><td><a href=\"//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa\" class='result-link'>A result</a></td></tr>"
        "<tr><td></td><td class='result-snippet'>A snippet</td></tr>"
        "</table></body></html>"
    )

    class Response:
        status_code = 200
        text = html

        def raise_for_status(self):
            return None

    def flaky_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("connection refused")
        return Response()

    monkeypatch.setattr(browse.httpx, "get", flaky_get)
    items = browse._lite_results("anything", 5)

    assert calls["n"] == 2
    assert items and items[0]["url"] == "https://example.com/a", "the redirect is unwrapped"


# ---------------------------------------------------------------------------
# Synthesis — the answer may not outrun its sources
# ---------------------------------------------------------------------------

def test_synthesis_rejects_a_figure_its_sources_do_not_carry(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    results = [{"title": "Nvidia results", "url": "https://a", "snippet": "Quarterly revenue rose."}]
    monkeypatch.setattr(
        llm_module,
        "_chat",
        lambda payload: json.dumps({"answer": "Revenue rose 412% last quarter.", "used": [0]}),
    )

    outcome = browse.synthesize("how is Nvidia doing?", results, "en")

    assert outcome["applied"] is False
    assert "figure" in outcome["reason"]


def test_synthesis_requires_the_reply_to_name_its_sources(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    results = [{"title": "T", "url": "https://a", "snippet": "S"}]
    monkeypatch.setattr(llm_module, "_chat", lambda payload: json.dumps({"answer": "It is doing well.", "used": []}))

    outcome = browse.synthesize("how is it doing?", results, "en")

    assert outcome["applied"] is False
    assert "named no sources" in outcome["reason"]


def test_an_unanswered_question_is_declared_and_never_invented(monkeypatch, online):
    """End to end through the assistant: no sources means no answer, with the reasons attached."""
    monkeypatch.setattr(browse, "_lite_results", lambda q, l: [])
    monkeypatch.setattr(browse, "_news_results", lambda q, l, lang: [])

    outcome = qa_module._answer_web("Is NVIDIA worth investing?", "en")

    assert outcome["source_kind"] == "none"
    assert outcome["sources"] == []
    assert outcome["answer"], "the advisor is still told what happened"
    assert len(outcome["unavailable"]) >= 2, "both providers' reasons are declared"
