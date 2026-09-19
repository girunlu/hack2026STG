"""B1 — imported ex-custody portfolios.

The brief requires an imported third-party statement to *"behave like a portfolio already available in
URO Advisor Pro"* and to be *"include[d] in the portfolio analysis and 60-second briefing"*. A parsed
report on its own achieves neither: it is a document, not a portfolio, and it belonged to no client.

This module closes both gaps:

* :func:`to_portfolio` maps a parsed report onto the F5 portfolio shape, so every existing consumer
  (F3, F4, R2, R3, R6) treats it like any other portfolio — no special-casing downstream.
* :func:`save` persists it under ``data/excustody/`` (outside the read-only case materials), and
  :func:`load_all` is merged by :func:`app.domain.ingest.load_raw`, so ``index.load(force=True)``
  remains the single reload path — the same pattern the client-file uploads use.

Positions whose ISIN is not in the trimmed ``reference.json`` carry ``SecurityId: None``. They are kept
and surface as declared gaps, never dropped.
"""

from __future__ import annotations

import json
import os
import re
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# src/backend/app/domain/excustody_store.py -> parents[4] is the repository root (D:/hack26)
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DIR = _REPO_ROOT / "data" / "excustody"

PROVENANCE = "ex_custody"
# Reserved PortfolioId range: far above anything the provided data uses, so an import can never
# collide with a real portfolio id in R3's findings or in a violation reference.
ID_BASE = 900_000_000
STORE_FILE = "imported.json"


def store_dir() -> Path:
    """Where imported portfolios live. Environment-overridable so tests stay isolated."""
    override = os.environ.get("URO_EXCUSTODY_DIR")
    return Path(override) if override else DEFAULT_DIR


def _store_path() -> Path:
    return store_dir() / STORE_FILE


def client_key(client_ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", client_ref or "unknown")[:80]


def _read_store() -> dict[str, list[dict]]:
    path = _store_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_store(data: dict[str, list[dict]]) -> None:
    directory = store_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = _store_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def next_sequence(client_ref: str) -> int:
    """1-based index of the next import for this client, so portfolio numbers are stable and unique."""
    return len(_read_store().get(client_key(client_ref), [])) + 1


def portfolio_id_for(client_ref: str, sequence: int) -> int:
    """Reserved-range surrogate id, unique per (client, sequence) and stable across reloads.

    ``sequence`` is per client, so ``ID_BASE + sequence`` on its own gave every client's first import
    the same id — measured live: `EXT-028-01` and `EXT-022-01` were both 900000001. ``index.
    portfolio_by_id`` resolves by id, so a collision silently hands back another client's portfolio:
    the same class of leak as `WEBSITE-BUGS.md` #2. The client ref is mixed in through a checksum, and
    the result is persisted by :func:`save`, so a bound import keeps its id.
    """
    checksum = zlib.crc32(client_key(client_ref).encode("utf-8")) % 1_000_000
    return ID_BASE + checksum * 100 + min(max(sequence, 0), 99)


def to_portfolio(parsed: dict, client_ref: str, sequence: int) -> dict:
    """Map a parsed Privatbank Helvetia report onto the F5 portfolio shape.

    Field names match the provided data deliberately: consumers already read ``SecurityPositions[].
    PortfolioValuePercentage`` and friends, and the brief asks the import to behave like a native
    portfolio rather than a parallel concept.
    """
    digits = re.sub(r"\D", "", client_ref) or "000"
    currency = parsed.get("currency") or "CHF"
    securities: list[dict] = []
    accounts: list[dict] = []

    for position in parsed.get("positions") or []:
        value = position.get("market_value")
        weight = position.get("weight")
        if position.get("is_cash"):
            accounts.append({
                "AccountName": position.get("name"),
                "Currency": position.get("currency"),
                "TotalAmountInPortfolioCurrency": value,
                "PortfolioValuePercentage": weight,
                "Provenance": PROVENANCE,
            })
            continue
        securities.append({
            "SecurityId": position.get("matched_security_id"),
            "Isin": position.get("isin"),
            "Valor": position.get("valor"),
            "SecurityName": position.get("name"),
            "Quantity": position.get("quantity"),
            "PricePerUnit": position.get("market_price"),
            "Currency": position.get("currency"),
            "TotalAmountInPortfolioCurrency": value,
            "PortfolioValuePercentage": weight,
            "AssetClassName": position.get("asset_class"),
            "MatchedSecurityName": position.get("matched_security_name"),
            "Provenance": PROVENANCE,
        })

    label = parsed.get("portfolio_label") or parsed.get("depot_nr") or "Ex-Custody"
    liquidity = sum(a.get("TotalAmountInPortfolioCurrency") or 0 for a in accounts)
    return {
        "PortfolioId": portfolio_id_for(client_ref, sequence),
        "PortfolioNr": f"EXT-{digits}-{sequence:02d}",
        "Name": f"{label} (Fremdbank)".strip(),
        "PortfolioCurrency": currency,
        "ReferenceCurrency": currency,
        "AssetsUnderManagementInDefaultCurrency": parsed.get("total_value"),
        "LiquidityInDefaultCurrency": liquidity or None,
        "StrategyName": parsed.get("mandat"),
        "SecurityPositions": securities,
        "AccountPositions": accounts,
        # Every consumer keys off this to label the portfolio as third-party.
        "Provenance": PROVENANCE,
        "IsExternal": True,
        "SourceFile": parsed.get("file"),
        "SourceReport": {
            "pages": parsed.get("pages"),
            "stichtag": parsed.get("stichtag"),
            "depot_nr": parsed.get("depot_nr"),
            "performance_2025_twr_pct": parsed.get("performance_2025_twr_pct"),
            "position_total_vs_reported_delta": parsed.get("position_total_vs_reported_delta"),
            "isins_matched": parsed.get("isins_matched"),
            "isins_unmatched": parsed.get("isins_unmatched"),
            "evidence": parsed.get("evidence"),
            "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        # An ex-custody statement carries no risk series and no monthly performance history. Declared,
        # never invented — R2/R6 surface these as gaps.
        "DataGaps": sorted(set(list(parsed.get("gaps") or []) + [
            "PerformanceHistory: an ex-custody statement prints no monthly series",
            "Volatility/ExpectedReturn/ValueAtRisk are not part of a custody statement",
        ])),
    }


def find_duplicate(client_ref: str, source_file: str | None) -> dict | None:
    """An already-stored import of the same statement, if any.

    Importing one statement twice would count the same assets twice in the portfolio analysis and the
    briefing, so the API refuses it instead (409) — the advisor can still delete and re-import.
    """
    if not source_file:
        return None
    for portfolio in _read_store().get(client_key(client_ref), []):
        if portfolio.get("SourceFile") == source_file:
            return portfolio
    return None


def save(client_ref: str, portfolio: dict) -> dict:
    """Persist one imported portfolio under its client. Returns the stored portfolio."""
    data = _read_store()
    key = client_key(client_ref)
    bucket = data.setdefault(key, [])
    bucket.append(portfolio)
    _write_store(data)
    return portfolio


def delete(client_ref: str, portfolio_nr: str) -> bool:
    """Remove one imported portfolio. Returns whether anything was removed."""
    data = _read_store()
    key = client_key(client_ref)
    bucket = data.get(key) or []
    remaining = [p for p in bucket if p.get("PortfolioNr") != portfolio_nr]
    if len(remaining) == len(bucket):
        return False
    if remaining:
        data[key] = remaining
    else:
        data.pop(key, None)
    _write_store(data)
    return True


def clear() -> int:
    """Delete every stored import; returns how many portfolios were removed.

    Imports live outside the provided materials (``data/excustody/``) and survive a dataset reload,
    so returning to the shipped 47-client state needs an explicit reset — this is it. The provided
    case data is never touched.
    """
    data = _read_store()
    removed = sum(len(bucket) for bucket in data.values() if isinstance(bucket, list))
    path = _store_path()
    if path.is_file():
        path.unlink()
    return removed


def load_all() -> tuple[dict[str, list[dict]], list[str]]:
    """Client ref -> imported portfolios, plus a problem line per unusable record.

    Called by :func:`app.domain.ingest.load_raw`. A malformed record degrades to a warning; it never
    stops the provided data from loading.
    """
    problems: list[str] = []
    merged: dict[str, list[dict]] = {}
    for key, bucket in _read_store().items():
        if not isinstance(bucket, list):
            problems.append(f"ex-custody store: {key!r} is not a list — ignored")
            continue
        kept = []
        for portfolio in bucket:
            if isinstance(portfolio, dict) and portfolio.get("PortfolioNr"):
                kept.append(portfolio)
            else:
                problems.append(f"ex-custody store: {key!r} holds a record without PortfolioNr — ignored")
        if kept:
            merged[key] = kept
    return merged, problems


def list_imported() -> list[dict]:
    """Flat list of every stored import, for the API and the UI."""
    out: list[dict] = []
    for key, bucket in sorted(load_all()[0].items()):
        for portfolio in bucket:
            report = portfolio.get("SourceReport") or {}
            out.append({
                "client_ref": key,
                "portfolio_nr": portfolio.get("PortfolioNr"),
                "name": portfolio.get("Name"),
                "currency": portfolio.get("PortfolioCurrency"),
                "aum": portfolio.get("AssetsUnderManagementInDefaultCurrency"),
                "positions": len(portfolio.get("SecurityPositions") or []),
                "accounts": len(portfolio.get("AccountPositions") or []),
                "source_file": portfolio.get("SourceFile"),
                "imported_at": report.get("imported_at"),
                "stichtag": report.get("stichtag"),
                "data_gaps": portfolio.get("DataGaps") or [],
            })
    return out
