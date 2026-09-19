#!/usr/bin/env python3
"""
Full rehearsal drill for the UNRISKOMEGA briefing assistant.

Runs the complete drill against an ISOLATED backend:
1. Starts uvicorn on port 8001 (hub name: api-drill) with isolated data dirs
2. Waits for /api/health
3. Generates synthetic clients with various archetypes
4. Uploads them via POST /api/dataset/clients/json
5. Briefs each client and validates the output
6. Runs the negative test matrix from REVIEW §13.1
7. Cleans up (DELETE uploads, stop server)
8. Prints a compact PASS/FAIL table

Usage:
    python tools/drill.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

# Repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"

# Isolated backend config
DRILL_PORT = 8001
DRILL_HUB_NAME = "api-drill"
DRILL_BACKEND_CWD = REPO_ROOT / "src" / "backend"


def start_isolated_backend():
    """Start uvicorn on port 8001 with isolated data directories."""
    import tempfile
    import os
    
    # Create temp dirs for isolated data
    temp_dir = Path(tempfile.mkdtemp(prefix="uro-drill-"))
    data_dir = temp_dir / "data"
    uploads_dir = data_dir / "uploads"
    excustody_dir = data_dir / "excustody"
    news_cache_dir = temp_dir / "news_cache"
    
    for d in [data_dir, uploads_dir, excustody_dir, news_cache_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Copy reference.json and clients.json to isolated data dir
    import shutil
    src_data = REPO_ROOT / "unriskomega-2026" / "core-case" / "portfolio-data"
    shutil.copy(src_data / "reference.json", data_dir / "reference.json")
    shutil.copy(src_data / "clients.json", data_dir / "clients.json")
    
    # Environment variables for isolated backend
    env = os.environ.copy()
    env["URO_DATA_DIR"] = str(data_dir)
    env["URO_UPLOAD_DIR"] = str(uploads_dir)
    env["URO_EXCUSTODY_DIR"] = str(excustody_dir)
    env["URO_NEWS_CACHE_DIR"] = str(news_cache_dir)
    env["URO_NEWS_OFFLINE"] = "1"
    
    # Start uvicorn
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(DRILL_PORT),
        "--log-level", "warning",
    ]
    
    print(f"Starting isolated backend on port {DRILL_PORT}...")
    print(f"  Data dir: {data_dir}")
    print(f"  Uploads: {uploads_dir}")
    
    process = subprocess.Popen(
        cmd,
        cwd=DRILL_BACKEND_CWD,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    # Wait for health endpoint
    base_url = f"http://127.0.0.1:{DRILL_PORT}"
    for attempt in range(30):
        try:
            resp = requests.get(f"{base_url}/api/health", timeout=1)
            if resp.status_code == 200:
                print(f"✓ Backend ready (attempt {attempt + 1})")
                return process, base_url, temp_dir
        except requests.exceptions.RequestException:
            time.sleep(0.5)
    
    # Timeout
    process.terminate()
    raise RuntimeError(f"Backend did not start within 15 seconds")


def stop_backend(process: subprocess.Popen, temp_dir: Path):
    """Stop the backend and clean up temp dirs."""
    print("\nStopping backend...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    
    # Clean up temp dir
    import shutil
    try:
        shutil.rmtree(temp_dir)
        print(f"✓ Cleaned up {temp_dir}")
    except Exception as e:
        print(f"⚠ Could not clean up {temp_dir}: {e}")


def generate_test_clients(base_url: str) -> list[tuple[str, str, Path]]:
    """Generate test clients with various archetypes."""
    archetypes = [
        ("balanced", "DRILL-BAL"),
        ("concentrated", "DRILL-CON"),
        ("cash_heavy", "DRILL-CSH"),
        ("foreign_currency_heavy", "DRILL-FX"),
        ("broken", "DRILL-BRK"),
    ]
    
    generated = []
    for archetype, prefix in archetypes:
        output_path = TOOLS_DIR / f"test-{archetype}.json"
        cmd = [
            sys.executable, str(TOOLS_DIR / "synth_client.py"),
            "--seed", "42",
            "--archetype", archetype,
            "--count", "1",
            "--output", str(output_path),
            "--prefix", prefix,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        generated.append((archetype, prefix, output_path))
    
    return generated


def upload_client(base_url: str, client_path: Path, filename: str) -> dict:
    """Upload a client file and return the response."""
    with client_path.open("rb") as f:
        resp = requests.post(
            f"{base_url}/api/dataset/clients/json",
            params={"filename": filename},
            data=f,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    return resp


def brief_client(base_url: str, client_ref: str) -> dict:
    """Generate a briefing for a client."""
    resp = requests.post(
        f"{base_url}/api/briefing",
        json={"client_ref": client_ref},
        timeout=10,
    )
    return resp


def validate_briefing(payload: dict, client_ref: str) -> list[str]:
    """Validate a ``POST /api/briefing`` response against the project's invariants.

    The response is ``{"facts": …, "briefing": …, "stages": […]}`` (`PROJECT.md` §5.5): sections,
    ``word_count`` and ``evidence_index`` live under ``briefing``, the declared gaps under
    ``facts.meta.unavailable``. Reading them off the top level validates nothing and reports every
    client as broken — which is exactly what the first version of this drill did.
    """
    errors: list[str] = []
    if "error" in payload or "detail" in payload:
        errors.append(f"payload is an error: {str(payload.get('error') or payload.get('detail'))[:120]}")
        return errors

    briefing = payload.get("briefing") or {}
    facts = payload.get("facts") or {}

    sections = briefing.get("sections") or []
    ids = [section.get("id") for section in sections]
    if ids != ["recent_development", "health_check", "outlook_actions"]:
        errors.append(f"expected the three brief sections in order, got {ids}")

    # Measured across the case data: 124-231 words; a client with no portfolios at all still produces
    # ~72. The band is wider than the target on purpose — the drill hunts a broken briefing, not a
    # short one, and padding a thin client would be invention.
    word_count = briefing.get("word_count") or 0
    if not (60 <= word_count <= 280):
        errors.append(f"word count {word_count} outside the 60-280 band")

    evidence_index = briefing.get("evidence_index") or {}
    traceable = 0
    for section in sections:
        blocks = section.get("blocks") or []
        if not any(block.get("evidence_refs") for block in blocks):
            errors.append(f"section {section.get('id')} has no traceable block")
        for block in blocks:
            refs = block.get("evidence_refs") or []
            traceable += 1 if refs else 0
            for ref in refs:
                if ref not in evidence_index:
                    errors.append(f"unresolvable evidence ref: {ref}")
    if not traceable:
        errors.append("no traceable block anywhere in the briefing")

    questions = briefing.get("questions") or {}
    for key in ("what_happened", "situation", "next", "should_do"):
        if not str(questions.get(key) or "").strip():
            errors.append(f"question {key!r} is empty")

    unavailable = (facts.get("meta") or {}).get("unavailable") or []
    if not unavailable:
        errors.append("expected at least one facts.meta.unavailable declaration")

    return errors


def run_negative_tests(base_url: str) -> list[tuple[str, bool, str]]:
    """Run the negative test matrix from REVIEW §13.1."""
    results = []
    
    # Test 1: Empty array → 400
    resp = requests.post(
        f"{base_url}/api/dataset/clients/json",
        params={"filename": "empty.json"},
        data=b"[]",
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    results.append(("Empty array → 400", resp.status_code == 400, f"status={resp.status_code}"))
    
    # Test 2: Malformed JSON → 400
    resp = requests.post(
        f"{base_url}/api/dataset/clients/json",
        params={"filename": "malformed.json"},
        data=b"{invalid json",
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    results.append(("Malformed JSON → 400", resp.status_code == 400, f"status={resp.status_code}"))
    
    # Test 3: Duplicate ClientRef → 409
    # First upload a client
    dup_client = [{
        "ClientId": 9999,
        "ClientRef": "DUP-001",
        "FirstName": "Test",
        "LastName": "User",
        "IsClientACompany": False,
        "IsEmployee": False,
        "RegulatoryClientTypeId": 13,
        "RegulatoryClientTypeName": "Private client",
        "ReportingCurrency": "CHF",
        "RiskProfileId": 17,
        "RiskProfileName": "Anlageprofil 5",
        "Birthday": "1980-01-01",
        "ProfilingDateUtc": "2026-01-01T00:00:00Z",
        "AssetsUnderManagementInDefaultCurrency": 1000000.0,
        "LiquidityInDefaultCurrency": 1000000.0,
        "Portfolios": [],
        "Proposals": [],
        "Transactions": [],
        "SuitabilityViolations": [],
        "IndividualRuleOverrides": [],
        "Tags": [],
        "ClientNotes": [],
    }]
    requests.post(
        f"{base_url}/api/dataset/clients/json",
        params={"filename": "dup1.json"},
        data=json.dumps(dup_client).encode(),
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    # Try to upload again
    resp = requests.post(
        f"{base_url}/api/dataset/clients/json",
        params={"filename": "dup2.json"},
        data=json.dumps(dup_client).encode(),
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    results.append(("Duplicate ClientRef → 409", resp.status_code == 409, f"status={resp.status_code}"))
    
    # Test 4: Single object (not array) → accepted. It needs its own ClientRef: ``dup_client`` is
    # still uploaded as dup1.json, so reusing it would (correctly) 409 and prove nothing.
    single_obj = dict(dup_client[0])
    single_obj["ClientRef"] = "SINGLE-001"
    resp = requests.post(
        f"{base_url}/api/dataset/clients/json",
        params={"filename": "single.json"},
        data=json.dumps(single_obj).encode(),
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    results.append(("Single object → accepted", resp.status_code == 200, f"status={resp.status_code}"))
    
    # Test 5: Wrapped object {"Clients":[...]} → accepted
    wrapped = {"Clients": [dup_client[0].copy()]}
    wrapped["Clients"][0]["ClientRef"] = "WRAP-001"
    resp = requests.post(
        f"{base_url}/api/dataset/clients/json",
        params={"filename": "wrapped.json"},
        data=json.dumps(wrapped).encode(),
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    results.append(("Wrapped object → accepted", resp.status_code == 200, f"status={resp.status_code}"))
    
    # Test 6: Client with no portfolios → 200 with gaps
    no_portfolios = [dup_client[0].copy()]
    no_portfolios[0]["ClientRef"] = "NOPORT-001"
    no_portfolios[0]["Portfolios"] = []
    resp = requests.post(
        f"{base_url}/api/dataset/clients/json",
        params={"filename": "noport.json"},
        data=json.dumps(no_portfolios).encode(),
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    results.append(("No portfolios → 200", resp.status_code == 200, f"status={resp.status_code}"))
    
    # Clean up test uploads
    for fname in ["dup1.json", "dup2.json", "single.json", "wrapped.json", "noport.json"]:
        requests.delete(f"{base_url}/api/dataset/uploads/{fname}", timeout=5)
    
    return results


def main():
    print("=" * 70)
    print("UNRISKOMEGA Rehearsal Drill")
    print("=" * 70)
    
    # Start isolated backend
    try:
        process, base_url, temp_dir = start_isolated_backend()
    except Exception as e:
        print(f"✗ Failed to start backend: {e}")
        sys.exit(1)
    
    results = []
    
    try:
        # Generate test clients
        print("\n--- Generating test clients ---")
        generated = generate_test_clients(base_url)
        print(f"✓ Generated {len(generated)} client files")
        
        # Upload and brief each
        print("\n--- Upload & brief matrix ---")
        for archetype, prefix, client_path in generated:
            filename = f"test-{archetype}.json"
            
            # Upload
            upload_resp = upload_client(base_url, client_path, filename)
            upload_ok = upload_resp.status_code == 200
            upload_data = upload_resp.json() if upload_ok else {}
            
            client_ref = f"{prefix}-001"
            
            # Brief
            brief_resp = brief_client(base_url, client_ref)
            brief_ok = brief_resp.status_code == 200
            brief_data = brief_resp.json() if brief_ok else {}
            
            # Validate
            validation_errors = validate_briefing(brief_data, client_ref) if brief_ok else ["Briefing failed"]
            brief_valid = len(validation_errors) == 0
            
            # Record result
            status = "PASS" if (upload_ok and brief_ok and brief_valid) else "FAIL"
            details = []
            if not upload_ok:
                details.append(f"upload={upload_resp.status_code}")
            if not brief_ok:
                details.append(f"brief={brief_resp.status_code}")
            if validation_errors:
                details.extend(validation_errors[:2])  # First 2 errors
            
            results.append((f"{archetype:25s} upload+brief+validate", status == "PASS", ", ".join(details) if details else "OK"))
            
            # Clean up
            requests.delete(f"{base_url}/api/dataset/uploads/{filename}", timeout=5)
        
        # Run negative tests
        print("\n--- Negative test matrix (REVIEW §13.1) ---")
        negative_results = run_negative_tests(base_url)
        for test_name, passed, detail in negative_results:
            results.append((test_name, passed, detail))
        
        # Print results table
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"{'Test':<50} {'Status':<8} {'Details'}")
        print("-" * 70)
        
        pass_count = 0
        fail_count = 0
        for test_name, passed, detail in results:
            status = "PASS" if passed else "FAIL"
            if passed:
                pass_count += 1
            else:
                fail_count += 1
            print(f"{test_name:<50} {status:<8} {detail}")
        
        print("-" * 70)
        print(f"Total: {pass_count} PASS, {fail_count} FAIL")
        print("=" * 70)
        
        # Exit with non-zero if any failures
        if fail_count > 0:
            sys.exit(1)
        
    finally:
        # Stop backend
        stop_backend(process, temp_dir)


if __name__ == "__main__":
    main()
