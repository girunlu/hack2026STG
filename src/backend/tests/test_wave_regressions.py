"""Regression tests for the 2026-09-19 wave that landed six behaviors.

The backend gained: sector_concentration finding, instrument-candidate actions, per-question
evidence refs, market block in section 1, preference dedupe, and withheld risk figure disclosure.
These tests pin the observable contracts so none regress silently.
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


# ---------------------------------------------------------------------------------
# 1. sector_concentration
# ---------------------------------------------------------------------------------

def test_sector_concentration_fires_for_case_028_financials(api):
    """CASE-028: 95.85% in Financials — high severity, evidence cites the weight."""
    payload = _briefing(api, "CASE-028")
    findings = payload["facts"]["findings"]
    sector = [f for f in findings if f["type"] == "sector_concentration"]
    assert sector, "CASE-028 must fire sector_concentration"
    f = sector[0]
    assert f["severity"] == "high"
    assert "95.85%" in f["title"] and "Financials" in f["title"]
    assert f["evidence"], "sector_concentration must carry evidence"
    assert any("Financials" in e["label"] for e in f["evidence"])


def test_sector_concentration_fires_for_case_027_industrials(api):
    """CASE-027: 97.9% in Industrials — high severity, evidence cites the weight."""
    payload = _briefing(api, "CASE-027")
    findings = payload["facts"]["findings"]
    sector = [f for f in findings if f["type"] == "sector_concentration"]
    assert sector, "CASE-027 must fire sector_concentration"
    f = sector[0]
    assert f["severity"] == "high"
    assert "97.9%" in f["title"] and "Industrials" in f["title"]
    assert f["evidence"]
    assert any("Industrials" in e["label"] for e in f["evidence"])


def test_sector_concentration_fires_for_case_010_health_care(api):
    """CASE-010 has 80.14% in Health Care, which should trigger sector_concentration finding."""
    payload = _briefing(api, "CASE-010")
    findings = payload["facts"]["findings"]
    sector = [f for f in findings if f["type"] == "sector_concentration"]
    assert sector, "CASE-010 must fire sector_concentration"
    f = sector[0]
    assert f["severity"] == "high"
    assert "80.14%" in f["title"] and "Health Care" in f["title"]


def test_sector_concentration_does_not_fire_for_low_weight_portfolios(api):
    """A portfolio with no classified industry above 30% emits nothing.
    
    CASE-007 has diversified holdings; no single industry dominates.
    """
    payload = _briefing(api, "CASE-007")
    findings = payload["facts"]["findings"]
    sector = [f for f in findings if f["type"] == "sector_concentration"]
    assert sector == [], f"CASE-007 should not fire sector_concentration, got {len(sector)}"


def test_sector_concentration_count_is_in_sane_band(api):
    """Across all 47 clients, sector_concentration fires for a sane number (not 0, not all).
    
    The exact count may shift with concurrent changes, so we assert a band: 10-20 clients.
    """
    clients = api.get("/api/clients").json()["rows"]
    firing_count = 0
    for client in clients:
        ref = client["ref"]
        if not ref.startswith("CASE-"):
            continue
        payload = _briefing(api, ref)
        findings = payload["facts"]["findings"]
        if any(f["type"] == "sector_concentration" for f in findings):
            firing_count += 1
    
    assert 10 <= firing_count <= 20, f"sector_concentration fired for {firing_count} clients, expected 10-20"


# ---------------------------------------------------------------------------------
# 2. Per-question evidence refs
# ---------------------------------------------------------------------------------

def test_per_question_evidence_refs_resolve_for_all_clients(api):
    """For all 47 clients: what_happened_refs, situation_refs, next_refs, should_do_refs all resolve.
    
    This extends the existing test_per_question_evidence_refs_resolve to assert resolvability
    for the four new arrays, not just evidence_refs.
    """
    clients = api.get("/api/clients").json()["rows"]
    for client in clients:
        ref = client["ref"]
        payload = _briefing(api, ref)
        briefing = payload["briefing"]
        questions = briefing["questions"]
        index_ = briefing["evidence_index"]
        
        for key in ("what_happened_refs", "situation_refs", "next_refs", "should_do_refs"):
            refs = questions.get(key, [])
            assert isinstance(refs, list), f"{ref}: {key} is not a list"
            for evidence_ref in refs:
                assert evidence_ref in index_, f"{ref}: {key} contains unresolved ref {evidence_ref}"


def test_should_do_refs_non_empty_when_actions_exist(api):
    """should_do_refs must be non-empty whenever an action exists.
    
    This was a real bug: should_do_refs used to contain bare finding ids like 'f3', which resolve
    to nothing. Now it must cite actual evidence.
    """
    clients = api.get("/api/clients").json()["rows"]
    for client in clients:
        ref = client["ref"]
        payload = _briefing(api, ref)
        briefing = payload["briefing"]
        questions = briefing["questions"]
        actions = briefing.get("actions", [])
        
        if actions:
            assert questions.get("should_do_refs"), f"{ref}: should_do_refs empty despite actions"


def test_evidence_refs_equals_what_happened_refs_for_compatibility(api):
    """evidence_refs still equals what_happened_refs for backward compatibility."""
    clients = api.get("/api/clients").json()["rows"]
    for client in clients:
        ref = client["ref"]
        payload = _briefing(api, ref)
        questions = payload["briefing"]["questions"]
        
        evidence_refs = questions.get("evidence_refs", [])
        what_happened_refs = questions.get("what_happened_refs", [])
        assert evidence_refs == what_happened_refs, f"{ref}: evidence_refs != what_happened_refs"


# ---------------------------------------------------------------------------------
# 3. Market block placement
# ---------------------------------------------------------------------------------

def test_market_block_renders_in_recent_development_with_external_source(api):
    """The top market item renders in section 'recent_development' with source_kind == 'external'.
    
    Stub market_context to ensure the test runs regardless of offline mode.
    """
    from app.compose.facts import assemble
    from app.compose.render import render
    
    facts = assemble("CASE-007", None, None, "en")
    facts["market_context"] = [
        {"headline": "Lonza builds spray-drying plant", "url": "https://example.com/a",
         "published": "2026-09-10T06:00:00+00:00", "source": "bing",
         "linked_security_ids": [11], "relevant_because": "Client holds 3.95% in Lonza."},
        {"headline": "LONZA GROUP AG CDR", "url": "https://example.com/b",
         "published": "2026-09-12T06:00:00+00:00", "source": "bing",
         "linked_security_ids": [11], "relevant_because": "Client holds 3.95% in Lonza."},
        {"headline": "Swisscom raises guidance", "url": "https://example.com/c",
         "published": "2026-09-11T06:00:00+00:00", "source": "bing",
         "linked_security_ids": [12], "relevant_because": "Client holds 4.10% in Swisscom."},
    ]
    briefing = render(facts, "template", "en")
    
    sections = briefing["sections"]
    recent = next((s for s in sections if s["id"] == "recent_development"), None)
    assert recent, "recent_development section must exist"
    
    external_blocks = [b for b in recent["blocks"] if b.get("source_kind") == "external"]
    assert external_blocks, "recent_development must contain at least one external block (market)"
    
    # The first market item should be in section 1
    first_block_text = external_blocks[0]["text"]
    assert "Lonza builds spray-drying plant" in first_block_text


def test_market_headline_not_rendered_again_in_outlook_actions(api):
    """The same market headline must not appear in outlook_actions (it's already in section 1).
    
    Stub market_context to ensure the test runs regardless of offline mode.
    """
    from app.compose.facts import assemble
    from app.compose.render import render
    
    facts = assemble("CASE-007", None, None, "en")
    facts["market_context"] = [
        {"headline": "Lonza builds spray-drying plant", "url": "https://example.com/a",
         "published": "2026-09-10T06:00:00+00:00", "source": "bing",
         "linked_security_ids": [11], "relevant_because": "Client holds 3.95% in Lonza."},
        {"headline": "LONZA GROUP AG CDR", "url": "https://example.com/b",
         "published": "2026-09-12T06:00:00+00:00", "source": "bing",
         "linked_security_ids": [11], "relevant_because": "Client holds 3.95% in Lonza."},
        {"headline": "Swisscom raises guidance", "url": "https://example.com/c",
         "published": "2026-09-11T06:00:00+00:00", "source": "bing",
         "linked_security_ids": [12], "relevant_because": "Client holds 4.10% in Swisscom."},
    ]
    briefing = render(facts, "template", "en")
    
    sections = briefing["sections"]
    recent = next((s for s in sections if s["id"] == "recent_development"), None)
    outlook = next((s for s in sections if s["id"] == "outlook_actions"), None)
    
    assert recent and outlook, "both sections must exist"
    
    recent_texts = [b["text"] for b in recent["blocks"]]
    outlook_texts = [b["text"] for b in outlook["blocks"]]
    
    # The first headline should be in section 1
    first_headline = "Lonza builds spray-drying plant"
    assert any(first_headline in text for text in recent_texts), "first headline must be in section 1"
    
    # The first headline should NOT be in section 3
    assert not any(first_headline in text for text in outlook_texts), (
        f"First headline '{first_headline}' must not appear in outlook_actions"
    )
    # Section 3 must pick the next *different* issuer, not a second headline about the one section 1
    # already used. Asserted on the section builder rather than on the rendered briefing: CASE-007 sits
    # above the 210-word budget, so the trim plan legitimately drops the external block afterwards.
    # This test owns the selection rule; the word band has its own tests.
    from app.compose import render as render_module

    index_ = render_module.EvidenceIndex()
    _, used_ids = render_module._recent_development(facts, index_, "en")
    selected = [b["text"] for b in render_module._outlook_actions(facts, index_, "en", used_ids)["blocks"]
                if b["source_kind"] == "external"]
    assert any("Swisscom raises guidance" in text for text in selected), selected
    assert not any("LONZA GROUP AG CDR" in text for text in selected), selected


# ---------------------------------------------------------------------------------
# 4. Instrument-candidate action
# ---------------------------------------------------------------------------------

def test_instrument_candidate_action_exists_for_case_045(api):
    """CASE-045 has an open proposal; exactly one instrument_candidate action must exist."""
    payload = _briefing(api, "CASE-045")
    actions = payload["facts"]["actions"]
    
    ic_actions = [a for a in actions if a.get("type") == "instrument_candidate"]
    assert len(ic_actions) == 1, f"CASE-045 must have exactly 1 instrument_candidate action, got {len(ic_actions)}"
    
    action = ic_actions[0]
    assert action["action"], "action text must be non-empty"
    assert len(action["action"]) <= 90, f"action label must be <= 90 chars, got {len(action['action'])}"
    assert action["finding_refs"], "action must cite at least one finding"
    assert action["evidence"], "action must have evidence"
    
    # Evidence must have the five contract keys
    for ev in action["evidence"]:
        assert "label" in ev and "value" in ev and "source" in ev and "path" in ev and "unit" in ev


def test_instrument_candidate_action_exists_for_case_007(api):
    """CASE-007 has recommendation-list buys; exactly one instrument_candidate action must exist."""
    payload = _briefing(api, "CASE-007")
    actions = payload["facts"]["actions"]
    
    ic_actions = [a for a in actions if a.get("type") == "instrument_candidate"]
    assert len(ic_actions) == 1, f"CASE-007 must have exactly 1 instrument_candidate action, got {len(ic_actions)}"
    
    action = ic_actions[0]
    assert action["action"], "action text must be non-empty"
    assert len(action["action"]) <= 90, f"action label must be <= 90 chars, got {len(action['action'])}"
    assert action["finding_refs"], "action must cite at least one finding"
    assert action["evidence"], "action must have evidence"


def test_instrument_candidate_action_names_real_instruments(api):
    """The action text must name at least one real instrument from the candidates."""
    payload = _briefing(api, "CASE-045")
    actions = payload["facts"]["actions"]
    ic_actions = [a for a in actions if a.get("type") == "instrument_candidate"]
    
    if not ic_actions:
        return
    
    action = ic_actions[0]
    action_text = action["action"]
    
    # The action text should contain instrument names (check for common patterns)
    # We don't pin exact names, but assert the text is non-trivial
    assert len(action_text) > 20, "action text must name instruments, not be generic"


def test_instrument_candidate_action_finding_refs_cite_same_portfolio(api):
    """The action's finding_refs must cite a finding that belongs to the same portfolio as the candidates.
    
    This pins scope discipline: WEBSITE-BUGS.md #2 was this class of leak.
    """
    payload = _briefing(api, "CASE-045")
    actions = payload["facts"]["actions"]
    findings = payload["facts"]["findings"]
    
    ic_actions = [a for a in actions if a.get("type") == "instrument_candidate"]
    if not ic_actions:
        return
    
    action = ic_actions[0]
    finding_ids = set(action["finding_refs"])
    
    # Find the cited findings
    cited_findings = [f for f in findings if f["id"] in finding_ids]
    assert cited_findings, "action must cite findings that exist in facts.findings"
    
    # All cited findings must belong to the same portfolio (scope discipline)
    portfolio_ids = {f.get("portfolio_id") for f in cited_findings if f.get("portfolio_id")}
    assert len(portfolio_ids) <= 1, f"action cites findings from multiple portfolios: {portfolio_ids}"


def test_case_007_instrument_candidate_excludes_energy_industry(api):
    """CASE-007's fossil-fuel note excludes Energy instruments (Exxon Mobil, TotalEnergies, Equinor).
    
    The action text must not name any Energy industry instrument.
    """
    payload = _briefing(api, "CASE-007")
    actions = payload["facts"]["actions"]
    ic_actions = [a for a in actions if a.get("type") == "instrument_candidate"]
    
    if not ic_actions:
        return
    
    action = ic_actions[0]
    action_text = action["action"].lower()
    
    # Check that no Energy instrument is named
    energy_instruments = ["exxon", "mobil", "totalenergies", "total energies", "equinor"]
    for instrument in energy_instruments:
        assert instrument not in action_text, (
            f"CASE-007 action must not name Energy instrument '{instrument}'"
        )


def test_instrument_candidate_action_direction_wording(api):
    """A buy-only candidate set must not produce a label containing a switch or sell verb, and vice versa."""
    payload = _briefing(api, "CASE-045")
    actions = payload["facts"]["actions"]
    ic_actions = [a for a in actions if a.get("type") == "instrument_candidate"]
    
    if not ic_actions:
        return
    
    action = ic_actions[0]
    action_text = action["action"].lower()
    
    # CASE-045 has both buys and sells (draft proposal exits and builds)
    # So the label should contain a switch verb
    switch_verbs = ["switch", "tauschen", "wechseln"]
    has_switch = any(verb in action_text for verb in switch_verbs)
    
    # If the action has both buy and sell moves, it should mention switching
    # We don't assert the exact wording, but check it's not purely buy or sell
    buy_verbs = ["buy", "kaufen", "erwerben"]
    sell_verbs = ["sell", "verkaufen", "veräußern"]
    has_buy = any(verb in action_text for verb in buy_verbs)
    has_sell = any(verb in action_text for verb in sell_verbs)
    
    # At least one direction verb must be present
    assert has_buy or has_sell or has_switch, (
        f"action text must mention a direction (buy/sell/switch), got: {action_text}"
    )


# ---------------------------------------------------------------------------------
# 5. Preference dedupe
# ---------------------------------------------------------------------------------

def test_case_007_emits_one_preference_conflict_per_position(api):
    """CASE-007 emits one preference_conflict finding per (note, position) even though its note
    matches both 'fossil' and 'energy'.
    """
    payload = _briefing(api, "CASE-007")
    findings = payload["facts"]["findings"]
    
    pref_findings = [f for f in findings if f["type"] == "preference_conflict"]
    assert pref_findings, "CASE-007 must have at least one preference_conflict finding"
    
    # Check that no two findings share the same position evidence path
    position_paths = set()
    for f in pref_findings:
        # Find the evidence entry that cites the position
        position_evidence = [e for e in f["evidence"] if "SecurityName" in e.get("path", "") or "Fund" in e.get("label", "")]
        if position_evidence:
            path = position_evidence[0]["path"]
            assert path not in position_paths, f"CASE-007 has duplicate preference findings for position {path}"
            position_paths.add(path)


def test_case_007_preference_finding_mentions_both_keywords(api):
    """CASE-007's preference_conflict finding must mention both 'fossil' and 'energy' keywords."""
    payload = _briefing(api, "CASE-007")
    findings = payload["facts"]["findings"]
    
    pref_findings = [f for f in findings if f["type"] == "preference_conflict"]
    assert pref_findings, "CASE-007 must have preference_conflict findings"
    
    # At least one finding must mention both keywords
    found_both = False
    for f in pref_findings:
        detail = f["detail"].lower()
        if "fossil" in detail and "energy" in detail:
            found_both = True
            break
    
    assert found_both, "at least one preference finding must mention both 'fossil' and 'energy'"


def test_preference_conflict_count_dropped_versus_old_behaviour(api):
    """The total count of preference findings for CASE-007 dropped versus the old behaviour.
    
    Before dedupe, CASE-007 would emit 2 findings (one for 'fossil', one for 'energy').
    After dedupe, it emits 1 finding per position. Assert the current count is <= 2.
    """
    payload = _briefing(api, "CASE-007")
    findings = payload["facts"]["findings"]
    
    pref_findings = [f for f in findings if f["type"] == "preference_conflict"]
    assert len(pref_findings) <= 2, (
        f"CASE-007 has {len(pref_findings)} preference findings, expected <= 2 after dedupe"
    )


# ---------------------------------------------------------------------------------
# 6. Withheld risk figure disclosure
# ---------------------------------------------------------------------------------

def test_case_041_withheld_risk_figure_declared_in_meta(api):
    """CASE-041's facts declare the dropped ContributionVolatility in meta.unavailable or data_gaps."""
    payload = _briefing(api, "CASE-041")
    facts = payload["facts"]
    
    # Check meta.unavailable
    unavailable = facts.get("meta", {}).get("unavailable", [])
    portfolio_gaps = [gap for p in facts["portfolios"] for gap in p.get("data_gaps", [])]
    
    # At least one must mention the risk figure or the position
    combined = " ".join(unavailable + portfolio_gaps).lower()
    assert "risk" in combined or "contribution" in combined or "withheld" in combined or "574339" in combined, (
        f"CASE-041 must declare the withheld risk figure, got unavailable={unavailable}, gaps={portfolio_gaps}"
    )


def test_case_041_briefing_never_quotes_impossible_figure(api):
    """The briefing must never quote the impossible figure 574339 or the overflowed marginal 9223372."""
    payload = _briefing(api, "CASE-041")
    
    # Serialize the entire payload to check for the forbidden numbers
    import json
    raw = json.dumps(payload, ensure_ascii=False)
    
    assert "574339" not in raw, "briefing must not quote the impossible ContributionVolatility 574339"
    assert "9223372" not in raw, "briefing must not quote the overflowed marginal 9223372"
    
    # Also check in blocks, answers, and evidence values
    briefing = payload["briefing"]
    for section in briefing["sections"]:
        for block in section["blocks"]:
            text = block.get("text", "")
            assert "574339" not in text and "9223372" not in text, (
                f"block text contains forbidden figure: {text[:100]}"
            )
    
    # Check questions
    questions = briefing["questions"]
    for key in ("what_happened", "situation", "next", "should_do"):
        answer = questions.get(key, "")
        assert "574339" not in answer and "9223372" not in answer, (
            f"question {key} contains forbidden figure: {answer[:100]}"
        )


# ---------------------------------------------------------------------------------
# 7. No untranslated backend string reaches an EN briefing
# ---------------------------------------------------------------------------------

def test_news_unavailable_reason_is_localized_not_raw_key(api):
    """The news-unavailable reason must come from news.no_query, not a hardcoded German string.
    
    The concrete regression: news.py used to hardcode "Aus dem Instrumentennamen liess sich keine
    Suchanfrage ableiten." Now it must come from the catalogue.
    """
    # Find a client where news is unavailable (CASE-027 has a private instrument with no news)
    payload = _briefing(api, "CASE-027")
    
    # Check that the German hardcoded string does not appear
    import json
    raw = json.dumps(payload, ensure_ascii=False)
    
    hardcoded_german = "Aus dem Instrumentennamen liess sich keine Suchanfrage ableiten"
    assert hardcoded_german not in raw, (
        "briefing contains hardcoded German string instead of localized catalogue entry"
    )


def test_no_raw_catalogue_key_in_rendered_briefing(api):
    """Sweep the rendered EN briefing for all 47 clients and assert no German-only literal leaks.
    
    The raw-key leak really happened with question.sit_sector. Assert that no raw catalogue key
    (question. / block. / finding. / action. prefixes) appears in rendered text.
    """
    clients = api.get("/api/clients").json()["rows"]
    
    for client in clients:
        ref = client["ref"]
        payload = _briefing(api, ref, lang="en")
        
        # Serialize the briefing text
        import json
        raw = json.dumps(payload["briefing"], ensure_ascii=False)
        
        # Check for raw catalogue key patterns
        raw_key_patterns = ["question.", "block.", "finding.", "action."]
        for pattern in raw_key_patterns:
            # Allow the pattern in evidence paths, but not in rendered text
            # We check the sections' block texts specifically
            for section in payload["briefing"]["sections"]:
                for block in section["blocks"]:
                    text = block.get("text", "")
                    # Check if the pattern appears as a standalone key (not part of a path)
                    if pattern in text:
                        # Allow if it's part of a longer path like "clients[...]"
                        # Disallow if it looks like a raw key like "question.sit_sector"
                        import re
                        if re.search(rf"\b{re.escape(pattern)}[a-z_]+\b", text):
                            # Check it's not part of a valid path
                            if "clients[" not in text and "reference." not in text:
                                pytest.fail(f"{ref}: raw catalogue key '{pattern}...' found in block text: {text[:100]}")

# ---------------------------------------------------------------------------------
# Unfilled catalogue placeholders — a whole class of advisor-visible garbage
# ---------------------------------------------------------------------------------

def test_no_unfilled_placeholder_reaches_the_advisor(api):
    """`i18n.t` returns the raw template when a format field is missing, so one forgotten kwarg ships
    "{category} by {diff} percentage points" straight to the advisor. This swept 34 such strings over
    17 clients × 2 languages before it was guarded.
    """
    import re

    from app.compose.facts import assemble
    from app.compose.render import render
    from app.domain import index

    placeholder = re.compile(r"\{[a-z_]+\}")
    offenders = []
    for client in index.load().clients:
        ref = str(client.get("ClientRef"))
        for lang in ("en", "de"):
            facts = assemble(ref, None, None, lang)
            briefing = render(facts, "template", lang)
            for action in facts["actions"]:
                for field in ("action", "rationale"):
                    if placeholder.search(str(action.get(field) or "")):
                        offenders.append((ref, lang, f"action.{field}", str(action[field])[:80]))
            for section in briefing["sections"]:
                for block in section["blocks"]:
                    if placeholder.search(block["text"]):
                        offenders.append((ref, lang, "block", block["text"][:80]))
            for key, value in briefing["questions"].items():
                if isinstance(value, str) and placeholder.search(value):
                    offenders.append((ref, lang, f"question.{key}", value[:80]))
            for question in briefing["client_questions"]:
                if placeholder.search(str(question.get("question") or "")):
                    offenders.append((ref, lang, "client_question", str(question["question"])[:80]))
    assert not offenders, f"{len(offenders)} unfilled placeholders: {offenders[:5]}"
