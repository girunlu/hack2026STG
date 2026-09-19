"""What the assistant does with a question no section of the client's data covers.

Measured defect. Asking the briefing assistant *"what are the strong parts of this investment case?"*
or *"is the client happy with the portfolio?"* fell straight through to a public web search, which
answered with a generic article (how to build an investment case, how to keep clients happy) and listed
the classifier's own internal state — *"Question could not be classified"* — under the panel's
"Not available" heading. The advisor asked about their client and got the internet.

Two different questions hide behind "unmatched": one about *this client* that the keyword vocabulary
does not cover, and one about the world outside the bank's data. Only the second belongs on the web.
"""

from __future__ import annotations

from app.compose import qa


def test_frame_is_decided_by_entities_the_client_data_does_not_carry():
    """A proper noun the context does not carry means the question is about the world outside it."""
    context = {
        "client": {"name": "Lena Vogt"},
        "findings": [{"title": "Shares: 97.09% instead of 0.0%"}],
    }
    assert qa._unknown_entities("What are the strong parts of this investment case?", context) == []
    assert qa._unknown_entities("Is the client happy with the portfolio?", context) == []
    assert qa._unknown_entities("How should we position for rising rates?", context) == []
    assert qa._unknown_entities("Is NVIDIA worth investing?", context) == ["NVIDIA"]

    held = {"holdings": [{"name": "Namen-Aktie Novartis AG"}]}
    assert qa._unknown_entities("How much Novartis does she hold?", held) == [], (
        "an instrument the client holds is in frame, not a reason to search the web"
    )


def test_an_unmatched_question_about_the_client_is_answered_from_the_client(api):
    facts = api.post("/api/briefing", json={"client_ref": "CASE-008"}).json()["facts"]
    titles = [str(f.get("title") or "") for f in facts.get("findings") or []]
    assert titles, "CASE-008 carries findings"

    body = api.post("/api/qa", json={
        "client_ref": "CASE-008",
        "question": "What are the strong parts of this investment case?",
    }).json()

    assert body["source_kind"] == "data", "a question about this client must not be answered from the web"
    assert body["sources"] == []
    assert body["answer"].strip()
    assert any(title and title in body["answer"] for title in titles), (
        f"the answer must name this client's own analysis, got: {body['answer'][:160]}"
    )
    assert body["evidence"], "the summary names where its items came from"
    assert body["unavailable"], "the scope is declared"
    assert not any("not classified" in item.lower() for item in body["unavailable"]), (
        "the classifier's internal state is not something to tell an advisor"
    )


def test_a_company_the_data_does_not_carry_still_reaches_the_web(api, monkeypatch):
    """The frame rule must not close the web: that is what it exists for."""
    asked: list[str] = []

    def fake_web(question: str, lang: str = "en") -> dict:
        asked.append(question)
        return {
            "answer": "web answer",
            "sources": [{"title": "A page", "url": "https://example.invalid/x", "snippet": "…"}],
            "source_kind": "web",
            "unavailable": [],
        }

    monkeypatch.setattr(qa, "_answer_web", fake_web)
    body = api.post("/api/qa", json={
        "client_ref": "CASE-008",
        "question": "Is NVIDIA worth investing?",
    }).json()

    assert asked == ["Is NVIDIA worth investing?"]
    assert body["source_kind"] == "web"
    assert body["unavailable"] == []
    assert body["evidence"] == [], "a public answer must not carry the client's findings as its evidence"
