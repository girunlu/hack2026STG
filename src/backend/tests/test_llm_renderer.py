"""R4's optional LLM renderer — phrasing only, and never a new figure.

The whole point of the renderer pair is that a rewording can only ever cost readability. These assert
the guards that make that true with a stubbed model, so no key and no network are needed: a rewrite
that invents a number, drops one, or comes back the wrong shape must leave the template text in place,
and the traceability index must survive untouched.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.compose import facts as facts_module
from app.compose import render as render_module
from app.external import llm as llm_module

CLIENT = "CASE-007"


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def without_key(monkeypatch):
    for name in llm_module._KEY_ENV:
        monkeypatch.delenv(name, raising=False)


def _facts(lang: str = "en") -> dict:
    return facts_module.assemble(CLIENT, None, None, lang)


def test_missing_key_is_an_error_not_a_silent_template(monkeypatch, without_key):
    """Asking for the LLM without a key must say so — a quiet fallback would hide the missing pass."""
    facts = _facts()
    with pytest.raises(ValueError) as error:
        render_module.render(facts, render_module.LLM, "en")
    assert "DEEPSEEK_API_KEY" in str(error.value)


def test_endpoint_reports_the_missing_key(client: TestClient, without_key):
    response = client.post("/api/briefing", json={"client_ref": CLIENT, "renderer": "llm"})
    assert response.status_code == 400
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_unknown_renderer_is_rejected_by_name(monkeypatch, without_key):
    with pytest.raises(ValueError) as error:
        render_module.render(_facts(), "gpt5", "en")
    assert "template" in str(error.value) and "llm" in str(error.value)


def test_rewrite_changes_only_the_prose(monkeypatch):
    """With a well-behaved model the structure and the evidence index are untouched."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    template = render_module.render(_facts(), render_module.TEMPLATE, "en")

    def fake_chat(payload: dict) -> str:
        texts = json.loads(payload["messages"][-1]["content"])["texts"]
        return json.dumps({"texts": [f"Rewritten. {text}" for text in texts]})

    monkeypatch.setattr(llm_module, "_chat", fake_chat)
    rendered = render_module.render(_facts(), render_module.LLM, "en")

    assert rendered["renderer"] == render_module.LLM
    assert rendered["evidence_index"] == template["evidence_index"]
    assert [section["id"] for section in rendered["sections"]] == [
        section["id"] for section in template["sections"]
    ]
    assert [len(section["blocks"]) for section in rendered["sections"]] == [
        len(section["blocks"]) for section in template["sections"]
    ]
    assert all(
        after["text"].startswith("Rewritten.")
        for section in rendered["sections"]
        for after in section["blocks"]
        if after.get("text")
    )


def test_a_rewrite_that_invents_a_number_is_rejected(monkeypatch):
    """The guard that matters: a figure the template never had must not reach the advisor."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    template = render_module.render(_facts(), render_module.TEMPLATE, "en")
    originals = [block["text"] for section in template["sections"] for block in section["blocks"]]

    def fake_chat(payload: dict) -> str:
        texts = json.loads(payload["messages"][-1]["content"])["texts"]
        # Inflate the first figure of every sentence that has one; leave the rest alone.
        def corrupt(text: str) -> str:
            for token in ("0.62", "62", "5.2", "12.0", "44.89"):
                if token in text:
                    return text.replace(token, f"{token} 999.99")
            return text

        return json.dumps({"texts": [corrupt(text) for text in texts]})

    monkeypatch.setattr(llm_module, "_chat", fake_chat)
    rendered = render_module.render(_facts(), render_module.LLM, "en")
    after = [block["text"] for section in rendered["sections"] for block in section["blocks"]]

    assert "999.99" not in " ".join(after)
    assert after == originals, "a block whose figures changed keeps its template wording"


def test_a_reply_that_is_not_usable_keeps_the_template(monkeypatch):
    """An unusable reply must not be reported as a successful LLM pass."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    template = render_module.render(_facts(), render_module.TEMPLATE, "en")
    originals = [block["text"] for section in template["sections"] for block in section["blocks"]]

    monkeypatch.setattr(llm_module, "_chat", lambda payload: "I am afraid I cannot do that.")
    rendered = render_module.render(_facts(), render_module.LLM, "en")

    assert [block["text"] for section in rendered["sections"] for block in section["blocks"]] == originals
    assert rendered["renderer"] == render_module.TEMPLATE
    assert rendered["llm"]["applied"] is False
    assert rendered["llm"]["reason"] == "reply was not usable"


def test_an_echoed_reply_does_not_claim_an_llm_pass(monkeypatch):
    """A model that returns the sentences unchanged leaves the template renderer in place."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    def echo(payload: dict) -> str:
        return json.dumps({"texts": json.loads(payload["messages"][-1]["content"])["texts"]})

    monkeypatch.setattr(llm_module, "_chat", echo)
    rendered = render_module.render(_facts(), render_module.LLM, "en")

    assert rendered["renderer"] == render_module.TEMPLATE
    assert rendered["llm"]["applied"] is False
    assert rendered["llm"]["changed_sentences"] == 0
    assert rendered["llm"]["sentences"] > 0, "the pass still reports how much it reviewed"


def test_fenced_json_reply_is_accepted(monkeypatch):
    """Models wrap JSON in a code fence often enough that it must not cost the rewrite."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    def fake_chat(payload: dict) -> str:
        texts = json.loads(payload["messages"][-1]["content"])["texts"]
        return "```json\n" + json.dumps({"texts": [f"{text} (revised)" for text in texts]}) + "\n```"

    monkeypatch.setattr(llm_module, "_chat", fake_chat)
    rendered = render_module.render(_facts(), render_module.LLM, "en")

    assert rendered["renderer"] == render_module.LLM
    assert rendered["llm"]["applied"] is True
    assert rendered["llm"]["changed_sentences"] > 0
    assert all(section["blocks"] for section in rendered["sections"])


def test_a_dead_endpoint_keeps_the_template(monkeypatch):
    """A network failure costs the phrasing, never the payload — and it is declared."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    template = render_module.render(_facts(), render_module.TEMPLATE, "en")

    def explode(payload: dict) -> str:
        raise ConnectionError("no route to host")

    monkeypatch.setattr(llm_module, "_chat", explode)
    rendered = render_module.render(_facts(), render_module.LLM, "en")

    assert [block["text"] for section in rendered["sections"] for block in section["blocks"]] == [
        block["text"] for section in template["sections"] for block in section["blocks"]
    ]
    assert rendered["renderer"] == render_module.TEMPLATE
    assert rendered["llm"]["reason"] == "ConnectionError"


# ---------------------------------------------------------------------------
# Signals — the one place the model may interpret, so the guard matters most
# ---------------------------------------------------------------------------

def test_signals_label_each_headline(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    def fake_chat(payload: dict) -> str:
        headlines = json.loads(payload["messages"][-1]["content"])["headlines"]
        return json.dumps({
            "signals": [
                {"sentiment": "positive", "materiality": "high", "why": "Reads as a positive development."}
                for _ in headlines
            ]
        })

    monkeypatch.setattr(llm_module, "_chat", fake_chat)
    result = llm_module.signals(["ASML raises its full-year guidance"], "en")

    assert result["applied"] is True
    assert len(result["signals"]) == 1
    assert result["signals"][0]["sentiment"] == "positive"
    assert result["signals"][0]["headline"] == "ASML raises its full-year guidance"


def test_a_signal_that_invents_a_figure_is_dropped(monkeypatch):
    """The explanation may not carry a figure the headline never had."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    def fake_chat(payload: dict) -> str:
        headlines = json.loads(payload["messages"][-1]["content"])["headlines"]
        return json.dumps({"signals": [
            {"sentiment": "positive", "materiality": "high", "why": "The stock jumped 412% on the news."},
            {"sentiment": "neutral", "materiality": "low", "why": "No decision-relevant information."},
        ][: len(headlines)]})

    monkeypatch.setattr(llm_module, "_chat", fake_chat)
    result = llm_module.signals(["ASML raises guidance", "ASML Holding NV DRC (ASML)"], "en")

    assert [signal["headline"] for signal in result["signals"]] == ["ASML Holding NV DRC (ASML)"]
    assert "412" not in json.dumps(result)


def test_signals_declare_the_missing_key_instead_of_returning_nothing(monkeypatch, without_key):
    result = llm_module.signals(["ASML raises guidance"], "en")
    assert result["applied"] is False
    assert "DEEPSEEK_API_KEY" in str(result["reason"])
    assert result["signals"] == []


def test_an_unusable_signal_reply_is_declared(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(llm_module, "_chat", lambda payload: "not json at all")

    result = llm_module.signals(["ASML raises guidance"], "en")
    assert result["applied"] is False
    assert result["reason"] == "reply was not usable"
    assert result["signals"] == []


def test_number_normalisation_sees_through_formatting():
    """A comma-decimal or a thousands separator must not read as a different figure."""
    assert llm_module.numbers("44.89 %") == llm_module.numbers("44,89 %")
    assert llm_module.numbers("CHF 2'049'658") == llm_module.numbers("CHF 2049658")
    assert llm_module.numbers("USD 1,234,567") == llm_module.numbers("USD 1234567")
    assert llm_module.numbers("EUR 1.234.567") == llm_module.numbers("EUR 1234567")
    assert llm_module.numbers("no figures here") == set()
    # A dropped or shifted decimal point is a different figure, not the same one reformatted.
    assert llm_module.numbers("5.59%") != llm_module.numbers("559%")
    assert llm_module.numbers("0.37321") != llm_module.numbers("0.3732")


def test_health_reports_whether_the_llm_can_run(client: TestClient, without_key):
    body = client.get("/api/health").json()
    assert body["llm_available"] is False
    assert body["llm_model"] is None
