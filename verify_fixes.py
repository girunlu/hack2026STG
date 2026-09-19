"""
Verification script for Defect A and Defect B fixes.
"""
import sys
sys.path.insert(0, 'D:/hack26/src/backend')

from app.domain import relevance, index

def verify_defect_a():
    """Verify that evidence paths are now concrete (no wildcards or negative indices)."""
    print("=" * 80)
    print("DEFECT A VERIFICATION: Evidence Path Grammar")
    print("=" * 80)
    
    dataset = index.load()
    issues_found = []
    
    for client in dataset.clients:
        client_ref = client['ClientRef']
        findings = relevance.findings(client_ref)
        
        for finding in findings:
            for evidence in finding['evidence']:
                path = evidence['path']
                
                # Check for wildcards
                if '[]' in path:
                    issues_found.append(f"  ❌ {client_ref}/{finding['id']}: Wildcard in path: {path}")
                
                # Check for negative indices
                if '[-' in path:
                    issues_found.append(f"  ❌ {client_ref}/{finding['id']}: Negative index in path: {path}")
    
    if issues_found:
        print(f"\n❌ FAILED: Found {len(issues_found)} path grammar violations:")
        for issue in issues_found[:10]:  # Show first 10
            print(issue)
        if len(issues_found) > 10:
            print(f"  ... and {len(issues_found) - 10} more")
        return False
    else:
        print("\n✅ PASSED: All evidence paths use concrete indices")
        print("   - No wildcards ([]) found")
        print("   - No negative indices ([-1]) found")
        return True


def verify_defect_b():
    """Verify that draft proposals now have medium severity and score >= 0.55."""
    print("\n" + "=" * 80)
    print("DEFECT B VERIFICATION: Draft Proposal Severity")
    print("=" * 80)
    
    dataset = index.load()
    issues_found = []
    draft_proposals_found = []
    
    for client in dataset.clients:
        client_ref = client['ClientRef']
        findings = relevance.findings(client_ref)
        
        for finding in findings:
            if finding['type'] == 'open_proposal':
                draft_proposals_found.append(client_ref)
                
                # Check severity
                if finding['severity'] != 'medium':
                    issues_found.append(f"  ❌ {client_ref}: severity is '{finding['severity']}', expected 'medium'")
                
                # Check score
                if finding['score'] < 0.55:
                    issues_found.append(f"  ❌ {client_ref}: score is {finding['score']}, expected >= 0.55")
    
    print(f"\nFound {len(draft_proposals_found)} clients with draft proposals:")
    for client_ref in draft_proposals_found:
        print(f"  - {client_ref}")
    
    if issues_found:
        print(f"\n❌ FAILED: Found {len(issues_found)} severity/score violations:")
        for issue in issues_found:
            print(issue)
        return False
    else:
        print("\n✅ PASSED: All draft proposals have correct severity and score")
        print("   - Severity: medium")
        print("   - Score: >= 0.55")
        return True


def show_sample_evidence():
    """Show sample evidence to demonstrate the fixes."""
    print("\n" + "=" * 80)
    print("SAMPLE EVIDENCE (for manual inspection)")
    print("=" * 80)
    
    dataset = index.load()
    
    # Show a stale_data finding (Defect A fix)
    print("\n1. Stale Data Finding (Defect A - Concrete Indices):")
    print("-" * 80)
    for client in dataset.clients[:5]:  # Check first 5 clients
        findings = relevance.findings(client['ClientRef'])
        for finding in findings:
            if finding['type'] == 'stale_data':
                print(f"Client: {client['ClientRef']}")
                print(f"Finding ID: {finding['id']}")
                print(f"Severity: {finding['severity']}, Score: {finding['score']}")
                print("Evidence:")
                for ev in finding['evidence']:
                    print(f"  - {ev['label']}: {ev['path']}")
                print()
                break
        else:
            continue
        break
    
    # Show an open_proposal finding (Defect B fix)
    print("\n2. Open Proposal Finding (Defect B - Medium Severity):")
    print("-" * 80)
    for client in dataset.clients:
        findings = relevance.findings(client['ClientRef'])
        for finding in findings:
            if finding['type'] == 'open_proposal':
                print(f"Client: {client['ClientRef']}")
                print(f"Finding ID: {finding['id']}")
                print(f"Severity: {finding['severity']}, Score: {finding['score']}")
                print("Evidence:")
                for ev in finding['evidence']:
                    print(f"  - {ev['label']}: {ev['path']}")
                print()
                break
        else:
            continue
        break


if __name__ == '__main__':
    defect_a_ok = verify_defect_a()
    defect_b_ok = verify_defect_b()
    show_sample_evidence()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Defect A (Evidence Paths): {'✅ PASSED' if defect_a_ok else '❌ FAILED'}")
    print(f"Defect B (Draft Severity): {'✅ PASSED' if defect_b_ok else '❌ FAILED'}")
    
    if defect_a_ok and defect_b_ok:
        print("\n🎉 All defects successfully fixed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some defects remain unfixed.")
        sys.exit(1)
