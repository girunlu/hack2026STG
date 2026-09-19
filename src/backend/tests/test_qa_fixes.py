"""Tests for QA violations routing fix.

Verified bug: "Which rule violations are open?" was being routed to proposals instead of rules
because the word "open" appears in both PROPOSAL_KEYWORDS and PROPOSAL_FOLLOWUP_KEYWORDS, and
the dispatcher checked proposal_followup BEFORE calling _classify().

Fix: Check RULE_KEYWORDS before proposal_followup in the dispatcher.
"""

from __future__ import annotations

import pytest


def test_case_007_violation_question_mentions_volatility_rule(api):
    """CASE-007 has an open max-volatility Error violation; answer must mention it with evidence."""
    body = api.post("/api/qa", json={
        "client_ref": "CASE-007",
        "question": "Which rule violations are open?",
    }).json()
    
    answer = body["answer"].lower()
    
    # Must mention the volatility rule
    assert "volatility" in answer or "vola" in answer, (
        f"Answer must mention volatility rule, got: {body['answer']}"
    )
    
    # Must include the engine's actual-vs-limit comparison, in one unit (percent) — the same unit the
    # briefing's health check uses. 12.64% vs 12.00%, never a bare 0.1264 next to prose that says 12.64%.
    assert "12.64%" in body["answer"] and "12.00%" in body["answer"], (
        f"Answer must include the engine's comparison in percent, got: {body['answer']}"
    )
    
    # Must have evidence
    assert body["evidence"], "Answer must carry evidence refs"
    
    # Evidence must point to the violations path
    evidence_paths = [e["path"] for e in body["evidence"]]
    assert any("SuitabilityViolations" in p for p in evidence_paths), (
        f"Evidence must reference SuitabilityViolations, got: {evidence_paths}"
    )


def test_case_028_no_violations_not_proposals(api):
    """CASE-028 has no violations; answer must say so, NOT fall through to proposals."""
    body = api.post("/api/qa", json={
        "client_ref": "CASE-028",
        "question": "Which rule violations are open?",
    }).json()
    
    answer = body["answer"].lower()
    
    # Must NOT talk about proposals
    assert "proposal" not in answer, (
        f"Answer must not mention proposals for a violations question, got: {body['answer']}"
    )
    
    # Must say no violations
    assert "no" in answer and ("violation" in answer or "rule" in answer), (
        f"Answer must state no violations, got: {body['answer']}"
    )
    
    # Must have evidence pointing to client's violations (even if empty)
    assert body["evidence"], "No-violations answer must still carry evidence"
    evidence_paths = [e["path"] for e in body["evidence"]]
    assert any("SuitabilityViolations" in p for p in evidence_paths), (
        f"Evidence must reference client's SuitabilityViolations, got: {evidence_paths}"
    )


def test_german_variant_routes_identically(api):
    """DE variant 'Welche Regelverletzungen sind offen?' must route to violations, not proposals."""
    body = api.post("/api/qa", json={
        "client_ref": "CASE-007",
        "question": "Welche Regelverletzungen sind offen?",
    }).json()
    
    answer = body["answer"].lower()
    
    # Must mention the violation (same as English)
    assert "volatility" in answer or "vola" in answer, (
        f"DE answer must mention volatility rule, got: {body['answer']}"
    )
    
    # Must NOT talk about proposals
    assert "vorschlag" not in answer and "proposal" not in answer, (
        f"DE answer must not mention proposals, got: {body['answer']}"
    )
    
    # Must have evidence
    assert body["evidence"], "DE answer must carry evidence"


def test_unanswerable_question_declares_unavailable(api):
    """An unanswerable question must declare unavailable, not hallucinate."""
    body = api.post("/api/qa", json={
        "client_ref": "CASE-007",
        "question": "What is the meaning of life?",
    }).json()
    
    # Must declare unavailable
    assert body["unavailable"], "Unanswerable question must declare unavailable"
    
    # Must say no answer
    assert "no answer" in body["answer"].lower() or "cannot" in body["answer"].lower(), (
        f"Unanswerable question must say no answer, got: {body['answer']}"
    )
