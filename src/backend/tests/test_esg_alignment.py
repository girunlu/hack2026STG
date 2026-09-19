"""Tests for ESG alignment finding (R3 relevance engine)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.domain import relevance, index


def test_esg_alignment_fires_for_case_016():
    """CASE-016 has ESG profile Yes (floor 5.714) and portfolio score 3.1 — a breach of the client's
    own elected floor, ranked ``high`` so it survives the word budget (at ``medium``/0.35 the block was
    trimmed away and the advisor never saw the only ESG breach in the dataset).
    """
    findings = relevance.findings("CASE-016")
    esg_findings = [f for f in findings if f["type"] == "esg_alignment"]

    assert len(esg_findings) == 1, f"Expected 1 esg_alignment finding, got {len(esg_findings)}"

    finding = esg_findings[0]
    assert finding["severity"] == "high", f"Expected high severity, got {finding['severity']}"
    assert finding["score"] > 0.5, f"Expected score > 0.5, got {finding['score']}"
    
    # Check evidence contains portfolio score and profile floor
    evidence_labels = [e["label"] for e in finding["evidence"]]
    assert "Portfolio sustainability score" in evidence_labels
    assert "ESG profile floor" in evidence_labels


def test_esg_alignment_fires_for_above_floor():
    """Test a client with ESG profile and score above floor - should fire low severity."""
    # Find a client with ESG profile and score above floor
    dataset = index.load()
    for client in dataset.clients:
        client_ref = client.get("ClientRef")
        findings = relevance.findings(client_ref)
        esg_findings = [f for f in findings if f["type"] == "esg_alignment"]
        
        if esg_findings and esg_findings[0]["severity"] == "low":
            # Found one - verify it's low severity
            finding = esg_findings[0]
            assert finding["severity"] == "low"
            assert finding["score"] < 0.3
            return
    # Not a tautology: 47 of the 48 clients carry an ESG profile and exactly one breaches its floor,
    # so an above-floor client always exists. If none is found the extractor has stopped firing.
    pytest.fail("no client produced an above-floor esg_alignment finding — the extractor is not firing")


def test_esg_alignment_no_fire_without_profile():
    """Test that clients without ESG profile don't fire esg_alignment."""
    # Find a client without ESG profile
    dataset = index.load()
    for client in dataset.clients:
        if not client.get("EsgProfileId"):
            client_ref = client.get("ClientRef")
            findings = relevance.findings(client_ref)
            esg_findings = [f for f in findings if f["type"] == "esg_alignment"]
            assert len(esg_findings) == 0, f"Client {client_ref} has no ESG profile but fired esg_alignment"
            return
    
    # If all clients have profiles, that's OK
    assert True


def test_esg_alignment_no_fire_without_score():
    """Test that portfolios without sustainability scores don't fire esg_alignment."""
    # CASE-028 has ESG profile but no sustainability score coverage
    findings = relevance.findings("CASE-028")
    esg_findings = [f for f in findings if f["type"] == "esg_alignment"]
    
    # Should not fire because no score coverage
    assert len(esg_findings) == 0, "CASE-028 has no score coverage but fired esg_alignment"


def test_esg_alignment_evidence_paths_resolve():
    """Test that all evidence paths in esg_alignment findings resolve correctly."""
    dataset = index.load()
    
    for client in dataset.clients:
        client_ref = client.get("ClientRef")
        findings = relevance.findings(client_ref)
        esg_findings = [f for f in findings if f["type"] == "esg_alignment"]
        
        for finding in esg_findings:
            for evidence in finding["evidence"]:
                # All evidence should be source="computed"
                assert evidence["source"] == "computed", \
                    f"ESG evidence should be computed, got {evidence['source']}"
                
                # Path should not contain wildcards
                assert "[]" not in evidence["path"], \
                    f"ESG evidence path contains wildcard: {evidence['path']}"


def test_esg_alignment_in_type_enum():
    """Test that esg_alignment is recognized as a valid finding type."""
    findings = relevance.findings("CASE-016")
    
    # Should not raise an error
    for finding in findings:
        assert finding["type"] in {
            "concentration", "sector_concentration", "allocation_drift", "rule_violation",
            "risk_alignment", "preference_conflict", "liquidity_event", "performance_driver",
            "open_proposal", "fx_exposure", "stale_data", "missing_data", "material_change",
            "pending_task", "reinvestment", "esg_alignment"
        }


def test_esg_alignment_rendered_in_briefing():
    """Test that esg_alignment findings are rendered in the briefing."""
    from app.compose import facts, render
    
    # Use CASE-016 which should have an esg_alignment finding
    bundle = facts.assemble("CASE-016", lang="en")
    briefing = render.render(bundle, lang="en")
    
    # Check that esg_alignment appears in health_check section
    health_check = briefing["sections"][1]  # health_check is section 1 (0-indexed)
    assert health_check["id"] == "health_check"
    
    # Look for ESG block in health_check
    esg_blocks = [b for b in health_check["blocks"] if "ESG" in b.get("text", "")]
    assert len(esg_blocks) > 0, f"Expected ESG block in health_check, got blocks: {[b.get('text', '')[:50] for b in health_check['blocks']]}"


def test_esg_alignment_count_across_clients():
    """Test that esg_alignment fires for a reasonable number of clients."""
    dataset = index.load()
    
    firing_count = 0
    for client in dataset.clients:
        client_ref = client.get("ClientRef")
        findings = relevance.findings(client_ref)
        esg_findings = [f for f in findings if f["type"] == "esg_alignment"]
        if esg_findings:
            firing_count += 1
    
    # Should fire for some clients but not all (some have no ESG profile or no score)
    assert 0 < firing_count < len(dataset.clients), \
        f"esg_alignment fired for {firing_count} clients, expected some but not all"
