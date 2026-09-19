"""B2 follow-up Q&A: the named-instrument topic (`REVIEW.md` §11.1.1, `compose/qa.py`).

The brief's bonus challenge requires answers that stay *grounded in the available data* and clearly
indicate when the information required is unavailable. These tests hold both halves for the instrument
topic: a client with candidates gets named instruments with evidence, and a client without any gets a
structured refusal instead of an answer borrowed from another topic.
"""

from __future__ import annotations

from app.compose import qa
from app.compose.facts import assemble
from app.domain import index

BUY_QUESTION = "Which securities should we buy or sell for this client?"
BUY_QUESTION_DE = "Welche Wertpapiere sollten wir für diesen Kunden kaufen oder verkaufen?"


def _client_with(kind: str) -> str:
    """First shipped client whose candidate bundle has `kind` rows ("moves" or "buys")."""
    for client in index.load().clients:
        ref = str(client.get("ClientRef"))
        if not ref.startswith("CASE-"):
            continue
        if assemble(ref, None, None, "en")["instrument_candidates"].get(kind):
            return ref
    raise AssertionError(f"no shipped client has candidate {kind} — the extractor stopped firing")


def _client_without_candidates() -> str:
    for client in index.load().clients:
        ref = str(client.get("ClientRef"))
        if not ref.startswith("CASE-"):
            continue
        bundle = assemble(ref, None, None, "en")["instrument_candidates"]
        if not bundle.get("moves") and not bundle.get("buys"):
            return ref
    raise AssertionError("every client has candidates — the refusal path is untestable")


def _ask(api, ref: str, question: str, lang: str = "en") -> dict:
    response = api.post("/api/qa", json={"client_ref": ref, "portfolio_nr": None,
                                         "question": question, "lang": lang})
    assert response.status_code == 200, response.text
    return response.json()


def test_proposal_moves_are_named_with_evidence(api):
    """CASE-045's open proposal exits Novartis and builds new lines — the answer must name them."""
    ref = _client_with("moves")
    payload = _ask(api, ref, BUY_QUESTION)

    assert payload["answer"].strip(), payload
    assert payload["evidence"], "a grounded answer carries its evidence rows"
    assert not payload["unavailable"], payload["unavailable"]

    moves = assemble(ref, None, None, "en")["instrument_candidates"]["moves"]
    named = [str(m["name"]) for m in moves[:3] if m.get("name")]
    assert named, moves[:3]
    assert any(name.split(" ")[-1] in payload["answer"] for name in named), \
        f"none of {named} appears in: {payload['answer'][:160]}"


def test_recommendation_buys_are_named_and_respect_the_client_preference(api):
    """CASE-007 asks to avoid fossil-fuel energy, so no Energy instrument may be recommended."""
    ref = _client_with("buys")
    payload = _ask(api, ref, BUY_QUESTION)

    assert payload["answer"].strip() and payload["evidence"], payload
    buys = assemble(ref, None, None, "en")["instrument_candidates"]["buys"]
    assert all(str(b["industry"]) != "Energy" for b in buys), buys
    for excluded in assemble(ref, None, None, "en")["instrument_candidates"]["excluded"]:
        assert str(excluded["name"]) not in payload["answer"], \
            f"a preference-excluded instrument was recommended: {excluded['name']}"


def test_no_candidates_is_a_structured_refusal(api):
    """A client with nothing to name gets a declared reason, not an answer from another topic."""
    ref = _client_without_candidates()
    payload = _ask(api, ref, BUY_QUESTION)

    assert payload["unavailable"], f"expected a declared reason for {ref}: {payload}"
    assert not payload["evidence"], payload["evidence"]
    # The refusal must not smuggle in an unrelated figure (the §4.10 defect class).
    facts = assemble(ref, None, None, "en")
    for finding in facts["findings"][:3]:
        assert str(finding["title"]) not in payload["answer"], payload["answer"][:160]


def test_german_answer_names_the_same_instruments(api):
    """Bilingual: the words change, the instruments and the numbers do not."""
    ref = _client_with("moves")
    english = _ask(api, ref, BUY_QUESTION, "en")
    german = _ask(api, ref, BUY_QUESTION_DE, "de")

    assert german["answer"].strip() and german["answer"] != english["answer"], (english, german)
    assert len(german["evidence"]) == len(english["evidence"])
    assert [e["path"] for e in german["evidence"]] == [e["path"] for e in english["evidence"]]


def test_answer_builder_never_returns_an_empty_string_with_evidence(api):
    """The unit contract: either an answer with evidence, or a refusal with a reason."""
    for ref in (_client_with("moves"), _client_with("buys"), _client_without_candidates()):
        facts = assemble(ref, None, None, "en")
        answer, evidence, unavailable = qa._answer_instruments(facts, BUY_QUESTION, None, "en")
        assert answer.strip(), ref
        assert bool(evidence) != bool(unavailable), (ref, evidence, unavailable)
        for row in evidence:
            assert set(row) >= {"label", "value", "source", "path"}, row
