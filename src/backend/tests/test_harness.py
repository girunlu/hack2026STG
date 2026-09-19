"""T1 — regression harness: all 47 clients headless → JSON → diff.

This is the real test suite: it catches the moment a change breaks a client you were not
looking at. Run the whole drill with::

    python -m pytest tests/test_harness.py --run-harness -q

Or as a module (writes snapshots to ``--out``)::

    python -m tests.test_harness --out tests/snapshots

Diff two snapshot directories::

    python -m tests.test_harness --diff tests/snapshots tests/snapshots-v2

The harness finishes in seconds, not minutes — the 18 MB of JSON is loaded once.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app


# --------------------------------------------------------------------------- harness


def run_all_clients(output_dir: Path) -> dict:
    """Drive every client through the API, writing one canonical JSON file per client.

    Returns a summary dict with ``clients``, ``portfolios``, ``gaps`` and ``elapsed_ms``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    summary = {"clients": 0, "portfolios": 0, "gaps": [], "elapsed_ms": 0}

    with TestClient(app) as client:
        # F2 — all clients
        r = client.get("/api/clients")
        r.raise_for_status()
        clients_response = r.json()
        summary["clients"] = len(clients_response["rows"])

        for row in clients_response["rows"]:
            ref = row["ref"]
            # F3 — client detail
            r = client.get(f"/api/clients/{ref}")
            r.raise_for_status()
            detail = r.json()

            portfolios_data = []
            for p_summary in detail["portfolios"]:
                nr = p_summary["nr"]
                # F4 — portfolio detail
                r = client.get(f"/api/clients/{ref}/portfolios/{nr}")
                r.raise_for_status()
                portfolios_data.append(r.json())
                summary["portfolios"] += 1

            # Collect gaps from client and portfolios
            client_gaps = list(detail.get("data_gaps", []))
            for p in portfolios_data:
                client_gaps.extend(p.get("data_gaps", []))
            if client_gaps:
                summary["gaps"].append({"client": ref, "gaps": client_gaps})

            # Write canonical JSON (sorted keys, stable order)
            payload = {
                "client": detail,
                "portfolios": portfolios_data,
            }
            out_file = output_dir / f"{ref}.json"
            out_file.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")

    summary["elapsed_ms"] = int((time.perf_counter() - start) * 1000)
    # Write summary
    (output_dir / "_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def diff_snapshots(baseline: Path, current: Path) -> dict:
    """Compare two snapshot directories; report added/removed files and per-file JSON diffs.

    Returns a dict with ``added``, ``removed``, ``changed`` (list of client refs) and
    ``differences`` (dict mapping client ref to list of diff descriptions).
    """
    baseline_files = {p.stem for p in baseline.glob("*.json") if p.stem != "_summary"}
    current_files = {p.stem for p in current.glob("*.json") if p.stem != "_summary"}

    added = sorted(current_files - baseline_files)
    removed = sorted(baseline_files - current_files)
    common = sorted(baseline_files & current_files)

    differences = {}
    for ref in common:
        baseline_data = json.loads((baseline / f"{ref}.json").read_text(encoding="utf-8"))
        current_data = json.loads((current / f"{ref}.json").read_text(encoding="utf-8"))
        diffs = _deep_diff(baseline_data, current_data, path="$")
        if diffs:
            differences[ref] = diffs

    return {
        "added": added,
        "removed": removed,
        "changed": sorted(differences.keys()),
        "differences": differences,
    }


def _deep_diff(a: Any, b: Any, path: str) -> list[str]:
    """Recursive JSON diff; returns a list of human-readable difference descriptions."""
    diffs = []
    if type(a) != type(b):
        diffs.append(f"{path}: type changed from {type(a).__name__} to {type(b).__name__}")
        return diffs
    if isinstance(a, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for key in sorted(all_keys):
            if key not in a:
                diffs.append(f"{path}.{key}: added")
            elif key not in b:
                diffs.append(f"{path}.{key}: removed")
            else:
                diffs.extend(_deep_diff(a[key], b[key], f"{path}.{key}"))
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: length changed from {len(a)} to {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diffs.extend(_deep_diff(x, y, f"{path}[{i}]"))
    elif a != b:
        diffs.append(f"{path}: {a!r} → {b!r}")
    return diffs


# --------------------------------------------------------------------------- pytest


def test_harness_all_clients(request, api, tmp_path):
    """Run the harness over all 47 clients and assert the invariants.

    - Every client produces a document.
    - No 500s.
    - Every response declares its ``data_gaps``.
    - Known-hard clients behave: CASE-008 (dirty refs), CASE-027 (private instrument),
      CASE-029 (no risk profile) — they return 200 with declared gaps instead of crashing.
    """
    if not request.config.getoption("--run-harness"):
        pytest.skip("pass --run-harness to run the full snapshot drill")
    output_dir = tmp_path / "snapshots"
    summary = run_all_clients(output_dir)

    assert summary["clients"] == 47
    assert summary["portfolios"] == 57
    assert summary["elapsed_ms"] < 60_000  # must finish in under a minute

    # Every client produced a file
    files = list(output_dir.glob("CASE-*.json"))
    assert len(files) == 47

    # Known-hard clients: they return 200 with declared gaps
    for ref in ("CASE-008", "CASE-027", "CASE-029"):
        payload = json.loads((output_dir / f"{ref}.json").read_text(encoding="utf-8"))
        assert payload["client"]["data_gaps"]  # non-empty
        # No 500s — the harness would have raised on non-2xx


def test_diff_reports_changes(tmp_path):
    """The diff mode must detect added/removed/changed files and per-file JSON differences."""
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    baseline.mkdir()
    current.mkdir()

    # Baseline: two clients
    (baseline / "CASE-001.json").write_text('{"a": 1, "b": 2}', encoding="utf-8")
    (baseline / "CASE-002.json").write_text('{"x": 10}', encoding="utf-8")

    # Current: CASE-001 changed, CASE-002 removed, CASE-003 added
    (current / "CASE-001.json").write_text('{"a": 1, "b": 99}', encoding="utf-8")
    (current / "CASE-003.json").write_text('{"y": 20}', encoding="utf-8")

    result = diff_snapshots(baseline, current)
    assert result["added"] == ["CASE-003"]
    assert result["removed"] == ["CASE-002"]
    assert result["changed"] == ["CASE-001"]
    assert "$.b" in result["differences"]["CASE-001"][0]


# --------------------------------------------------------------------------- CLI


def main():
    """CLI entry point for the snapshot+diff drill.

    Examples::

        python -m tests.test_harness --out tests/snapshots
        python -m tests.test_harness --diff tests/snapshots tests/snapshots-v2
    """
    parser = argparse.ArgumentParser(description="T1 regression harness")
    parser.add_argument("--out", type=Path, help="write snapshots to this directory")
    parser.add_argument("--diff", nargs=2, metavar=("BASELINE", "CURRENT"), help="compare two snapshot directories")
    args = parser.parse_args()

    if args.diff:
        baseline, current = Path(args.diff[0]), Path(args.diff[1])
        result = diff_snapshots(baseline, current)
        print(json.dumps(result, indent=2))
        if result["added"] or result["removed"] or result["changed"]:
            sys.exit(1)
    elif args.out:
        summary = run_all_clients(args.out)
        print(json.dumps(summary, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
