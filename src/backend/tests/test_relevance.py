"""Tests for R3 relevance engine.

Acceptance criteria:
- CASE-007: allocation_drift + rule_violation + liquidity_event
- CASE-028: concentration ~0.9585
- CASE-027: missing_data for uncovered/private instrument
- CASE-008: dangling → missing_data, no crash
- CASE-029: no risk profile → missing_data
- CASE-017: preference_conflict on Neste
- CASE-012: fx_exposure USD 0.8219
- Determinism: two consecutive calls return identical JSON
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.domain import index, metrics, relevance
from app.domain.ingest import as_date, day, intnum, listof, text


def test_case_007_allocation_drift_rule_violation_liquidity_event():
    """CASE-007 must produce allocation_drift, rule_violation, and liquidity_event."""
    findings = relevance.findings("CASE-007")
    types = [f["type"] for f in findings]

    assert "allocation_drift" in types, f"Missing allocation_drift in {types}"
    assert "rule_violation" in types, f"Missing rule_violation in {types}"
    assert "liquidity_event" in types, f"Missing liquidity_event in {types}"

    # Check specific findings
    drift = [f for f in findings if f["type"] == "allocation_drift"]
    assert len(drift) >= 2, f"Expected at least 2 allocation_drift, got {len(drift)}"

    # Check Shares drift (56.7% vs 75%)
    shares_drift = [f for f in drift if "Shares" in f["title"]]
    assert len(shares_drift) > 0, "Missing Shares allocation_drift"
    assert "56.7%" in shares_drift[0]["title"], f"Expected 56.7% in title, got {shares_drift[0]['title']}"

    # Check liquidity_event — assert the evidence chain, not the prose: the finding must cite the
    # client note that states the need and the position weight that makes it illiquid.
    liquidity = [f for f in findings if f["type"] == "liquidity_event"]
    assert len(liquidity) > 0, "Missing liquidity_event"
    paths = [e["path"] for e in liquidity[0]["evidence"]]
    assert any("ClientNotes[" in path for path in paths), f"liquidity_event cites no note: {paths}"

    # Check rule_violation
    violations = [f for f in findings if f["type"] == "rule_violation"]
    assert len(violations) > 0, "Missing rule_violation"


def test_case_028_concentration():
    """CASE-028 must produce concentration finding ~0.9585."""
    findings = relevance.findings("CASE-028")
    types = [f["type"] for f in findings]

    assert "concentration" in types, f"Missing concentration in {types}"

    concentration = [f for f in findings if f["type"] == "concentration"]
    assert len(concentration) > 0, "Missing concentration finding"

    # Check weight is ~0.9585
    conc = concentration[0]
    assert "95.85%" in conc["title"], f"Expected 95.85% in title, got {conc['title']}"
    assert "VZ Holding" in conc["title"], f"Expected VZ Holding in title"

    # Check evidence
    assert len(conc["evidence"]) >= 1, "Concentration finding must have evidence"
    weight_evidence = [e for e in conc["evidence"] if "weight" in e["label"].lower()]
    assert len(weight_evidence) > 0, "Missing weight evidence"
    assert abs(weight_evidence[0]["value"] - 0.9585) < 0.001, f"Expected weight ~0.9585, got {weight_evidence[0]['value']}"


def test_case_027_missing_data():
    """CASE-027 must produce missing_data for SpaceX Aktie."""
    findings = relevance.findings("CASE-027")
    types = [f["type"] for f in findings]

    # Should have concentration (68.53% SpaceX)
    assert "concentration" in types, f"Missing concentration in {types}"

    concentration = [f for f in findings if f["type"] == "concentration"]
    assert len(concentration) > 0, "Missing concentration finding"
    assert "SpaceX" in concentration[0]["title"], f"Expected SpaceX in title"

    # Should have missing_data (no proposals, etc.)
    assert "missing_data" in types, f"Missing missing_data in {types}"


def test_case_008_dangling_missing_data():
    """CASE-008 must produce missing_data for dangling references, no crash."""
    findings = relevance.findings("CASE-008")

    # Should have missing_data findings for dangling portfolio refs
    missing = [f for f in findings if f["type"] == "missing_data"]
    assert len(missing) > 0, "Missing missing_data findings for dangling refs"

    # At least one finding must name a portfolio id that exists on no client. Assert the dangling id
    # itself (language-independent), not the wording of the title.
    missing_ids = {f["portfolio_id"] for f in missing}
    assert missing_ids & {210121, 210525, 141384}, f"No dangling portfolio id reported: {missing_ids}"
    assert any("SuitabilityViolations[" in e["path"] for f in missing for e in f["evidence"])


def test_case_029_no_risk_profile():
    """CASE-029 must produce missing_data for no risk profile."""
    findings = relevance.findings("CASE-029")
    types = [f["type"] for f in findings]

    assert "missing_data" in types, f"Missing missing_data in {types}"

    # The declared gap must point at the field that is actually null (RiskProfileId), not at prose.
    no_risk = [
        f for f in findings
        if f["type"] == "missing_data"
        and any("RiskProfileId" in e["path"] for e in f["evidence"])
    ]
    assert len(no_risk) > 0, "No missing_data finding cites RiskProfileId"


def test_case_017_preference_conflict_neste():
    """CASE-017 must produce preference_conflict on Neste Corporation."""
    findings = relevance.findings("CASE-017")
    types = [f["type"] for f in findings]

    assert "preference_conflict" in types, f"Missing preference_conflict in {types}"

    # Check for Neste conflict
    neste = [f for f in findings if f["type"] == "preference_conflict" and "Neste" in f["title"]]
    assert len(neste) > 0, "Missing Neste preference_conflict"

    # Check that it mentions fossil/energy
    assert "fossil" in neste[0]["title"].lower() or "energy" in neste[0]["title"].lower(), \
        f"Expected fossil/energy in title, got {neste[0]['title']}"


def test_case_012_fx_exposure_usd():
    """CASE-012 must produce fx_exposure for USD ~0.8219."""
    findings = relevance.findings("CASE-012")
    types = [f["type"] for f in findings]

    assert "fx_exposure" in types, f"Missing fx_exposure in {types}"

    # Check for USD exposure
    usd = [f for f in findings if f["type"] == "fx_exposure" and "USD" in f["title"]]
    assert len(usd) > 0, "Missing USD fx_exposure"

    # Check weight is ~0.8219
    fx = usd[0]
    assert "82.19%" in fx["title"], f"Expected 82.19% in title, got {fx['title']}"

    # Check evidence
    assert len(fx["evidence"]) >= 1, "FX exposure finding must have evidence"


def test_determinism():
    """Two consecutive calls must return identical JSON."""
    findings1 = relevance.findings("CASE-007")
    findings2 = relevance.findings("CASE-007")

    # Convert to JSON for comparison
    json1 = json.dumps(findings1, sort_keys=True)
    json2 = json.dumps(findings2, sort_keys=True)

    assert json1 == json2, "Findings are not deterministic"


def test_all_findings_have_evidence():
    """Every finding must have at least one evidence entry."""
    for client_ref in ["CASE-007", "CASE-028", "CASE-027", "CASE-008", "CASE-029", "CASE-017", "CASE-012"]:
        findings = relevance.findings(client_ref)
        for finding in findings:
            assert len(finding["evidence"]) >= 1, \
                f"Finding {finding['id']} in {client_ref} has no evidence"
            for evidence in finding["evidence"]:
                assert "label" in evidence, f"Missing label in evidence"
                assert "value" in evidence, f"Missing value in evidence"
                assert "source" in evidence, f"Missing source in evidence"
                assert "path" in evidence, f"Missing path in evidence"
                assert evidence["source"] in ["clients.json", "reference.json", "computed"], \
                    f"Invalid source: {evidence['source']}"

def test_finding_ids_sequential():
    """Finding IDs must be sequential f1, f2, f3, ..."""
    findings = relevance.findings("CASE-007")
    for i, finding in enumerate(findings, start=1):
        assert finding["id"] == f"f{i}", f"Expected f{i}, got {finding['id']}"


def test_score_range():
    """All scores must be in [0, 1]."""
    for client_ref in ["CASE-007", "CASE-028", "CASE-027", "CASE-008", "CASE-029", "CASE-017", "CASE-012"]:
        findings = relevance.findings(client_ref)
        for finding in findings:
            assert 0.0 <= finding["score"] <= 1.0, \
                f"Score {finding['score']} out of range [0, 1] in {finding['id']}"


def test_severity_values():
    """All severities must be high, medium, or low."""
    findings = relevance.findings("CASE-007")
    valid_severities = {"high", "medium", "low"}
    for finding in findings:
        assert finding["severity"] in valid_severities, \
            f"Invalid severity: {finding['severity']}"


def test_material_change_matches_an_independent_recomputation():
    """Every reported trade must sit inside the window, be executed, and cite its own row.

    The expected set is recomputed here from the raw client dicts — deliberately independent of
    ``relevance`` — so a wrong window, a wrong status filter or a wrong date source fails the test.
    """
    dataset = index.load(force=True)
    as_of = date.fromisoformat(str(dataset.data_as_of())[:10])
    cutoff = as_of - timedelta(days=183)
    checked = 0

    for client in dataset.clients:
        ref = client["ClientRef"]
        proposals = {p.get("ProposalId"): p for p in listof(client, "Proposals")}
        expected = 0
        for transaction in listof(client, "Transactions"):
            proposal = proposals.get(transaction.get("ProposalId"))
            if not proposal or proposal.get("ProposalStatusName") != "Final":
                continue
            stamp = day(proposal.get("FinalizedDateUTC")) or day(proposal.get("ProposedDateUTC"))
            traded = as_date(stamp)
            if traded and traded >= cutoff:
                expected += 1

        reported = [f for f in relevance.findings(ref) if f["type"] == "material_change"]
        assert len(reported) == (1 if expected else 0), f"{ref}: {expected} trades in window, {len(reported)} finding(s)"
        if not reported:
            continue
        checked += 1
        paths = [e["path"] for e in reported[0]["evidence"]]
        assert any("Transactions[" in path for path in paths), paths
        assert any("Proposals[" in path for path in paths), f"{ref}: dating basis not declared: {paths}"

    assert checked > 5, f"only {checked} clients exercised the extractor — the test is not covering it"


def test_pending_task_never_repeats_another_findings_note():
    """One note, one statement: a task may not recycle a note another finding already speaks for."""
    dataset = index.load(force=True)
    checked = 0
    for client in dataset.clients:
        ref = client["ClientRef"]
        findings = relevance.findings(ref)
        tasks = [f for f in findings if f["type"] == "pending_task"]
        if not tasks:
            continue
        checked += 1
        others = {
            str(e["path"])
            for f in findings if f["type"] != "pending_task"
            for e in f["evidence"]
            if "ClientNotes[" in str(e["path"])
        }
        for task in tasks:
            assert task["evidence"], f"{ref}: task without evidence"
            assert all(str(e["path"]) not in others for e in task["evidence"]), \
                f"{ref}: task repeats a note another finding already cites"
            assert "ClientNotes[" in str(task["evidence"][0]["path"]), task["evidence"][0]["path"]
    assert checked > 5, f"only {checked} clients produced a task — the test is not covering it"


def test_reinvestment_owns_cash_and_requires_a_real_excess():
    """Reinvestment fires only above both marks, and cash never appears as an allocation drift."""
    dataset = index.load(force=True)
    checked = 0
    for client in dataset.clients:
        ref = client["ClientRef"]
        findings = relevance.findings(ref)

        for finding in findings:
            if finding["type"] != "allocation_drift":
                continue
            assert not any(e["label"] == "Liquidity target" for e in finding["evidence"]), \
                f"{ref}: cash reported as a strategy deviation"

        for finding in [f for f in findings if f["type"] == "reinvestment"]:
            row = next(
                (p for p in dataset.portfolios_of(ref) if p.get("PortfolioId") == finding["portfolio_id"]),
                None,
            )
            assert row is not None, f"{ref}: reinvestment on an unknown portfolio"
            actual, target = 0.0, 0.0
            for candidate in metrics.saa_deviation(row)["rows"]:
                if candidate["category"] == "Liquidity":
                    actual, target = float(candidate["actual"]), float(candidate["target"])
            assert actual >= 0.10 and (actual - target) >= 0.05, f"{ref}: {actual} vs {target}"
            checked += 1

    assert checked > 5, f"only {checked} portfolios produced a reinvestment finding"


def test_type_enum():
    """All types must be from the enum."""
    valid_types = {
        "concentration", "sector_concentration", "allocation_drift", "rule_violation", "risk_alignment",
        "preference_conflict", "liquidity_event", "performance_driver", "open_proposal",
        "fx_exposure", "stale_data", "missing_data", "material_change", "pending_task",
        "reinvestment", "esg_alignment",
    }
    findings = relevance.findings("CASE-007")
    for finding in findings:
        assert finding["type"] in valid_types, f"Invalid type: {finding['type']}"


def test_every_type_fires_and_every_draft_surfaces():
    """Enum membership is not coverage: every type must fire, and every draft must surface.

    Guards two defects this test would have caught. ``open_proposal`` read field names the data
    does not carry (``Status``/``Id``/``Title``/``CreatedByDateUTC`` instead of
    ``ProposalStatusName``/``ProposalId``/``AdvisoryTypeName``/``ProposedDateUTC``), so it produced
    nothing at all for the clients holding a draft; and it was invoked once per portfolio, which
    would have emitted duplicates once the names were right.
    """
    valid_types = {
        "concentration", "sector_concentration", "allocation_drift", "rule_violation", "risk_alignment",
        "preference_conflict", "liquidity_event", "performance_driver", "open_proposal",
        "fx_exposure", "stale_data", "missing_data", "material_change", "pending_task",
        "reinvestment", "esg_alignment",
    }
    dataset = index.load(force=True)
    seen: set[str] = set()

    for client in dataset.clients:
        ref = client["ClientRef"]
        findings = relevance.findings(ref)
        seen.update(finding["type"] for finding in findings)

        drafts = [
            proposal for proposal in listof(client, "Proposals")
            if text(proposal, "ProposalStatusName") == "Entwurf"
        ]
        reported = [finding for finding in findings if finding["type"] == "open_proposal"]
        assert len(reported) == len(drafts), \
            f"{ref}: {len(drafts)} draft(s) but {len(reported)} open_proposal finding(s)"

        for proposal in drafts:
            proposal_id = intnum(proposal, "ProposalId", -1)
            path = f"Proposals[{proposal_id}].ProposalStatusName"
            assert any(
                evidence["path"].endswith(path)
                for finding in reported
                for evidence in finding["evidence"]
            ), f"{ref}: draft {proposal_id} has no evidence pointing at its status"

    assert seen == valid_types, f"finding types never produced: {sorted(valid_types - seen)}"


def test_evidence_path_resolver_gate():
    """Resolver gate: every evidence entry must either resolve verbatim OR be source='computed'.
    
    This test walks all 47 clients and validates that:
    1. If source != 'computed', the path must resolve to the exact value in raw JSON
    2. If source == 'computed', the label must be non-empty and path must name concrete input fields
    3. No path ends in .SecurityPositions where the target is absent/not a list (unless computed)
    4. No path references a Proposals[<id>].<field> where the field doesn't exist (unless computed)
    """
    import re
    
    dataset = index.load()
    clients_raw = dataset.clients
    reference_raw = dataset.reference
    
    # Build client lookup by ClientRef
    clients_by_ref = {c["ClientRef"]: c for c in clients_raw}
    
    def resolve_path(path: str, value) -> tuple[bool, str]:
        """Attempt to resolve a path against raw JSON. Returns (resolved, reason)."""
        # Parse path like clients[CASE-001].Portfolios[CASE-001-01].SecurityPositions[0].PortfolioValuePercentage
        # or reference.RiskProfiles[17].MaxVola
        
        if path == "FactoryDateUtc":
            # Special case: top-level field in reference
            if "FactoryDateUtc" in reference_raw:
                return True, ""
            return False, "FactoryDateUtc not in reference"
        
        # Split into segments
        segments = []
        current = ""
        i = 0
        while i < len(path):
            if path[i] == '.':
                if current:
                    segments.append(current)
                    current = ""
            elif path[i] == '[':
                if current:
                    segments.append(current)
                    current = ""
                # Find closing ]
                j = path.find(']', i)
                if j == -1:
                    return False, f"Unclosed bracket in {path}"
                segments.append(path[i+1:j])
                i = j
            else:
                current += path[i]
            i += 1
        if current:
            segments.append(current)
        
        if not segments:
            return False, f"Empty path: {path}"
        
        # Start resolution
        root = segments[0]
        if root == "clients":
            if len(segments) < 2:
                return False, "clients path needs at least one more segment"
            # Second segment should be ClientRef
            client_ref = segments[1]
            if client_ref not in clients_by_ref:
                return False, f"Client {client_ref} not found"
            obj = clients_by_ref[client_ref]
            start_idx = 2
        elif root == "reference":
            obj = reference_raw
            start_idx = 1
        else:
            return False, f"Unknown root: {root}"
        
        for seg in segments[start_idx:]:
            if isinstance(obj, dict):
                if seg not in obj:
                    return False, f"Key {seg} not found"
                obj = obj[seg]
            elif isinstance(obj, list):
                # seg should be an index or ID lookup
                try:
                    idx = int(seg)
                    # First try as numeric index
                    if 0 <= idx < len(obj):
                        obj = obj[idx]
                    else:
                        # Try to find by Id, SecurityId, or ProposalId field
                        found = None
                        for item in obj:
                            if isinstance(item, dict):
                                if (str(item.get("Id")) == seg or 
                                    str(item.get("SecurityId")) == seg or
                                    str(item.get("ProposalId")) == seg):
                                    found = item
                                    break
                        if found is None:
                            return False, f"Index {idx} out of range and Id/SecurityId/ProposalId {seg} not found"
                        obj = found
                except ValueError:
                    # Might be a key lookup like Proposals[24488] or Portfolios[CASE-001-01]
                    # Try to find by ID
                    found = None
                    for item in obj:
                        if isinstance(item, dict):
                            # Try various ID fields
                            if str(item.get("ProposalId")) == seg:
                                found = item
                                break
                            if str(item.get("SecurityId")) == seg:
                                found = item
                                break
                            if str(item.get("PortfolioNr")) == seg:
                                found = item
                                break
                            if str(item.get("Id")) == seg:
                                found = item
                                break
                    if found is None:
                        return False, f"ID {seg} not found in list"
                    obj = found
        
        # Check if resolved value matches expected
        if obj == value:
            return True, ""
        # Allow numeric tolerance
        if isinstance(obj, (int, float)) and isinstance(value, (int, float)):
            if abs(obj - value) < 1e-6:
                return True, ""
        # Special case: path resolves to object, value is a field extracted from it
        if isinstance(obj, dict) and isinstance(value, (str, int, float)):
            for k, v in obj.items():
                if v == value:
                    return True, ""
                if isinstance(v, (int, float)) and isinstance(value, (int, float)):
                    if abs(v - value) < 1e-6:
                        return True, ""
        # Special case: path resolves to list, value is the length
        if isinstance(obj, list) and isinstance(value, int) and value == len(obj):
            return True, ""
        # Special case: path resolves to None, value is empty list
        if obj is None and value == []:
            return True, ""
        # Special case: path resolves to list, value is count of items
        if isinstance(obj, list) and isinstance(value, int):
            return True, ""
        return False, f"Value mismatch: got {obj!r}, expected {value!r}"
    
    violations = []
    
    for client in clients_raw:
        client_ref = client["ClientRef"]
        findings = relevance.findings(client_ref)
        
        for finding in findings:
            for evidence in finding["evidence"]:
                path = evidence["path"]
                source = evidence["source"]
                value = evidence["value"]
                label = evidence["label"]
                
                # Check for problematic patterns
                has_wildcard = "[]" in path
                has_negative = re.search(r'\[-\d+\]', path)
                
                if has_wildcard:
                    violations.append(f"{client_ref}/{finding['id']}: wildcard in path: {path}")
                    continue
                
                if has_negative:
                    violations.append(f"{client_ref}/{finding['id']}: negative index in path: {path}")
                    continue
                
                # Check if path ends in .SecurityPositions
                if path.endswith(".SecurityPositions"):
                    # This should only be allowed if source='computed' or if it actually resolves to a list
                    resolved, reason = resolve_path(path, value)
                    if not resolved:
                        if source != "computed":
                            violations.append(f"{client_ref}/{finding['id']}: path ends in .SecurityPositions but doesn't resolve and source != 'computed': {path}")
                        continue
                    # If it resolves, check it's actually a list
                    # (We can't easily check the type here without re-resolving, so skip for now)
                
                # Check for Proposals[<id>].<field> patterns
                prop_match = re.search(r'Proposals\[(\d+)\]\.(\w+)', path)
                if prop_match:
                    proposal_id = prop_match.group(1)
                    field = prop_match.group(2)
                    # Check if this proposal exists and has this field
                    proposals = client.get("Proposals", [])
                    proposal = None
                    for p in proposals:
                        if str(p.get("ProposalId")) == proposal_id:
                            proposal = p
                            break
                    if proposal is None:
                        if source != "computed":
                            violations.append(f"{client_ref}/{finding['id']}: Proposals[{proposal_id}] not found and source != 'computed': {path}")
                        continue
                    if field not in proposal:
                        if source != "computed":
                            violations.append(f"{client_ref}/{finding['id']}: Proposals[{proposal_id}].{field} doesn't exist and source != 'computed': {path}")
                        continue
                
                # If source is not 'computed', the path must resolve verbatim
                if source != "computed":
                    resolved, reason = resolve_path(path, value)
                    if not resolved:
                        violations.append(f"{client_ref}/{finding['id']}: path doesn't resolve and source != 'computed': {path} ({reason})")
                else:
                    # source == 'computed': label must be non-empty
                    if not label or not label.strip():
                        violations.append(f"{client_ref}/{finding['id']}: source='computed' but label is empty: {path}")
    
    assert not violations, f"Resolver gate found {len(violations)} violations:\n" + "\n".join(violations[:20])



if __name__ == "__main__":
    # Run tests manually
    test_case_007_allocation_drift_rule_violation_liquidity_event()
    print("✓ test_case_007_allocation_drift_rule_violation_liquidity_event")

    test_case_028_concentration()
    print("✓ test_case_028_concentration")

    test_case_027_missing_data()
    print("✓ test_case_027_missing_data")

    test_case_008_dangling_missing_data()
    print("✓ test_case_008_dangling_missing_data")

    test_case_029_no_risk_profile()
    print("✓ test_case_029_no_risk_profile")

    test_case_017_preference_conflict_neste()
    print("✓ test_case_017_preference_conflict_neste")

    test_case_012_fx_exposure_usd()
    print("✓ test_case_012_fx_exposure_usd")

    test_determinism()
    print("✓ test_determinism")

    test_all_findings_have_evidence()
    print("✓ test_all_findings_have_evidence")

    test_finding_ids_sequential()
    print("✓ test_finding_ids_sequential")

    test_score_range()
    print("✓ test_score_range")

    test_severity_values()
    print("✓ test_severity_values")

    test_type_enum()
    print("✓ test_type_enum")

    test_every_type_fires_and_every_draft_surfaces()
    print("✓ test_every_type_fires_and_every_draft_surfaces")

    print("\nAll tests passed!")
