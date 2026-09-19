"""Regression tests for the defects listed in ``WEBSITE-BUGS.md`` (v2).

Every test here failed before the fix and passes after it, and every assertion is on what a consumer
observes in a payload — not on internals that merely moved. The defects they pin down:

* #2  a briefing scoped to one portfolio reported the client's *other* portfolios' findings
* #3  ``?lang`` was ignored on the client detail endpoint
* #5  the bank view said "portfolio overweight" while the briefing said the same asset class was
      below its own target
* #8  one briefing printed the same comparison as ``0.1264`` and as ``12.6384%``
* #9  a currency question claimed currency data was missing while F4 rendered the currency split
* #10 an unrelated question was answered with the strategy's and the service's names
* #11 the client screen printed raw engine field names (``RegulatoryClientTypeRuleField`1``)
* #12 the rule text was looked up by ``RuleCode``, which is not unique, so the wrong region showed
"""

from __future__ import annotations

import pytest


def _briefing(api, client_ref: str, portfolio_nr: str | None = None, lang: str = "en") -> dict:
    response = api.post("/api/briefing", json={
        "client_ref": client_ref,
        "portfolio_nr": portfolio_nr,
        "renderer": "template",
        "lang": lang,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _block_texts(payload: dict, section_id: str | None = None) -> list[str]:
    return [
        block["text"]
        for section in payload["briefing"]["sections"]
        if section_id is None or section["id"] == section_id
        for block in section["blocks"]
    ]


def test_client_detail_honours_the_requested_language(api):
    """#3 — the detail endpoint answered ``lang: "en"`` to ``?lang=de``."""
    assert api.get("/api/clients/CASE-007", params={"lang": "de"}).json()["lang"] == "de"
    assert api.get("/api/clients/CASE-007").json()["lang"] == "en"


def test_scoped_briefing_reports_only_the_scoped_portfolio(api):
    """#2 — CASE-038-01's briefing used to carry 15 findings of an unknown portfolio plus CASE-038-02's."""
    payload = _briefing(api, "CASE-038", "CASE-038-01")
    ids = {portfolio["id"] for portfolio in payload["facts"]["portfolios"]}
    foreign = [
        finding["portfolio_id"]
        for finding in payload["facts"]["findings"]
        if finding.get("portfolio_id") is not None and finding["portfolio_id"] not in ids
    ]
    assert foreign == [], f"findings from portfolios outside the scope: {sorted(set(foreign))}"


def test_rule_text_describes_the_violation_it_belongs_to(api):
    """#12 — ``Overweight in the equity region "Switzerland"`` exists twice in ``SuitabilityRules``.

    Looking the text up by code resolved to the last duplicate and printed "Grossbritannien".
    """
    violations = api.get("/api/clients/CASE-008").json()["violations"]
    duplicated = [
        violation for violation in violations
        if violation["rule_code"] == 'Overweight in the equity region "Switzerland"'
    ]
    assert duplicated, "fixture expects CASE-008 to hold the duplicated rule code"
    assert all("Schweiz" in violation["rule_description"] for violation in duplicated)

    texts = " ".join(_block_texts(_briefing(api, "CASE-008")))
    assert "Grossbritannien" not in texts, "the briefing must not borrow the other region's rule text"


def test_violation_values_name_the_field_and_its_unit(api):
    """#11 — raw engine field names reached the advisor; #8 — units were mixed on one page."""
    violations = api.get("/api/clients/CASE-007").json()["violations"]
    values = [value for violation in violations for value in violation["values"]]
    assert values, "fixture expects CASE-007 to hold a violation with a ViolationPath"
    assert all("RuleField" not in value["label"] and "`" not in value["label"] for value in values)
    assert all(value["unit"] in ("ratio", "value") for value in values)
    assert any(
        value["label"] == "Volatility" and value["unit"] == "ratio" for value in values
    ), "the volatility comparison must be labelled and marked as a ratio"
    # The client screen renders the data's own rule text, not a code lookup.
    assert all(violation["rule_description"] is not None for violation in violations)
    assert not any("rule_description_de" in violation for violation in violations)


def test_one_briefing_prints_the_comparison_in_one_unit(api):
    """#8 — the health check said 0.1264/0.1200 while action #2 said 12.6384%/12.0000%."""
    payload = _briefing(api, "CASE-007")
    health = " ".join(_block_texts(payload, "health_check"))
    assert "12.64%" in health and "12.00%" in health
    assert "0.1264" not in health

    actions = " ".join(str(action.get("rationale") or "") for action in payload["facts"]["actions"])
    assert "0.1264" not in actions


def test_currency_question_is_answered_from_the_exposure_rows(api):
    """#9 — "bond exposure in EUR" answered "Currency exposure not in the data" while F4 showed the split."""
    body = api.post("/api/qa", json={
        "client_ref": "CASE-007",
        "question": "What is the client's total bond exposure in EUR?",
    }).json()

    assert "Currency exposure not in the data." not in body["answer"]
    assert "%" in body["answer"], body["answer"]
    assert body["evidence"], "the answer must cite the exposure it used"
    # The asset-class/currency crossing is declared rather than quietly substituted.
    assert body["unavailable"], body


def test_unanswerable_allocation_question_is_declared(api):
    """#10 — an unrelated question was answered with "The strategy is: … The service is: …"."""
    body = api.post("/api/qa", json={
        "client_ref": "CASE-007",
        "question": "What is the private equity allocation of the client's holiday home?",
    }).json()

    assert "The strategy is:" not in body["answer"]
    assert body["unavailable"], body


def test_bank_view_relation_follows_the_portfolios_own_target(api):
    """#5 — "Shares portfolio overweight" while the same document said Shares sat 18.3 pp below target."""
    payload = _briefing(api, "CASE-007")
    shares = [m for m in payload["facts"]["house_view"]["matches"] if m["category"] == "Shares"]
    assert shares, "fixture expects a Shares stance in the mock bank view"
    assert {m["relation"] for m in shares} == {"portfolio underweight"}

    contradicted = [
        text for text in _block_texts(payload)
        if "Shares" in text and "portfolio overweight" in text
    ]
    assert contradicted == [], contradicted
