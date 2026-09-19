"""X2 — House / CIO view.

Loads a curated mock CIO view from ``data/house_view.json`` and matches it
against real portfolio exposures. The mock is honest about being a mock —
``mock: true`` and a German disclaimer travel with every response.

Public API:
- ``house_view()`` — returns the raw structured view.
- ``match(exposures, portfolios=None, targets=None)`` — compares each stance to the portfolio's own
  position and emits ``portfolio overweight`` / ``portfolio underweight`` / ``aligned`` (against the
  portfolio's SAA target) or ``stance aligned`` / ``stance contrary`` / ``no target`` for dimensions
  that carry no target, with evidence.

The matcher uses the same category vocabulary as the SAA mappings
(``Shares``, ``Bonds``, ``Liquidity``, ``Real estate``,
``Specialties andCommodities``, currency groups, country groups, industries)
so matching is exact-string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Tolerance for "aligned" classification — within ±2 percentage points of the
# stance's implied direction is considered aligned.
_ALIGNMENT_TOLERANCE = 0.02

# Where the mock house view lives
_DATA_PATH = Path(__file__).parent / "data" / "house_view.json"

# Cache the parsed JSON at module level (it is small and read-only)
_cached_view: dict | None = None


def _load_view() -> dict:
    """Load and cache the house view JSON."""
    global _cached_view
    if _cached_view is not None:
        return _cached_view
    try:
        data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        _cached_view = data
        return data
    except (OSError, json.JSONDecodeError) as exc:
        # Return a minimal valid view so callers never crash
        return {
            "source": "Fehler beim Laden",
            "source_url": "",
            "title": "Fehler",
            "as_of": "",
            "mock": True,
            "disclaimer": f"Hausansicht konnte nicht geladen werden: {exc}",
            "stances": [],
        }


def house_view() -> dict:
    """Return the curated house/CIO view.

    Always returns a dict with at least ``source``, ``as_of``, ``mock``,
    ``disclaimer``, ``stances``. The ``mock: true`` flag and German disclaimer
    MUST be shown in the UI.
    """
    return _load_view()


def _classify_relation(
    weight: float,
    stance: str,
    target: float | None = None,
) -> str:
    """How the *portfolio* sits — never how the bank's stance reads.

    ``overweight`` is a statement about a benchmark, so it needs one:

    * With the portfolio's own SAA target (asset classes) the relation is the portfolio's deviation
      from it. A Shares weight of 56.7% against a 75% target is ``portfolio underweight`` even while
      the bank is overweight the asset class — the earlier version compared the weight to a 2%
      tolerance and told the advisor the portfolio was overweight while the same briefing said it sat
      18.3 pp below target.
    * Without a target (currency, region and sector groups carry none) no overweight/underweight
      claim can be made at all; the match states only whether the positioning is consistent with the
      bank's stance (``stance aligned``) or against it (``stance contrary``), and stays silent
      (``no target``) when the bank has no directional view either.
    """
    if target is not None:
        difference = weight - target
        if difference > _ALIGNMENT_TOLERANCE:
            return "portfolio overweight"
        if difference < -_ALIGNMENT_TOLERANCE:
            return "portfolio underweight"
        return "aligned"
    if stance == "overweight":
        return "stance aligned" if weight >= _ALIGNMENT_TOLERANCE else "stance contrary"
    if stance == "underweight":
        return "stance aligned" if weight <= _ALIGNMENT_TOLERANCE else "stance contrary"
    return "no target"


def _build_evidence(
    weight: float,
    source_label: str,
    source_path: str,
) -> list[dict]:
    """Build evidence list for a match."""
    return [
        {
            "label": source_label,
            "value": weight,
            "source": "clients.json",
            "path": source_path,
        }
    ]


def match(
    exposures: dict,
    portfolios: list[dict] | None = None,
    targets: dict[str, float] | None = None,
) -> list[dict]:
    """Match house-view stances against portfolio exposures.

    Args:
        exposures: Mapping of dimension -> category -> weight. The weight is a
            fraction 0–1 representing the portfolio's actual exposure in that
            category. Example structure::

                {
                    "AssetClass": {"Shares": 0.567, "Bonds": 0.352, ...},
                    "CurrencyGroup": {"Swiss francs": 0.65, ...},
                    "CountryGroup": {"Switzerland": 0.55, ...},
                    "Industry": {"Financials": 0.40, ...},
                }

            Each dimension is optional — missing dimensions produce no matches.

        portfolios: Optional list of portfolio dicts. When provided, matches
            include ``portfolio_id`` for traceability. If None, ``portfolio_id``
            is omitted.

        targets: The portfolio's own SAA targets, ``{category: fraction}``. When a
            stance's category has one, the relation is the portfolio's deviation from
            it; without one, the relation only states consistency with the stance.

    Returns:
        List of match dicts, each with ``category``, ``dimension``, ``stance``,
        ``relation``, ``portfolio_id`` (when portfolios provided), ``evidence``.
        Every match carries real weights in its evidence.
    """
    view = _load_view()
    stances = view.get("stances", [])
    if not stances:
        return []

    matches: list[dict] = []

    for stance_entry in stances:
        dimension = stance_entry.get("dimension")
        category = stance_entry.get("category")
        stance = stance_entry.get("stance")
        note = stance_entry.get("note", "")

        if not dimension or not category or not stance:
            continue

        dim_exposures = exposures.get(dimension, {})
        if not isinstance(dim_exposures, dict):
            continue

        weight = dim_exposures.get(category)
        if weight is None:
            # No exposure in this category — skip (no evidence to cite)
            continue

        if not isinstance(weight, (int, float)):
            continue

        relation = _classify_relation(
            float(weight),
            stance,
            (targets or {}).get(str(category)) if dimension == "AssetClass" else None,
        )

        match_entry: dict[str, Any] = {
            "dimension": dimension,
            "category": category,
            "stance": stance,
            "stance_note": note,
            "relation": relation,
            "evidence": _build_evidence(
                weight=float(weight),
                source_label=f"Tatsächliche Gewichtung {category}",
                source_path=f"exposures.{dimension}.{category}",
            ),
        }

        # Attach portfolio id if portfolios are provided
        if portfolios:
            # Use the first portfolio's id as the primary reference
            # (callers can call match() per-portfolio for multi-portfolio)
            portfolio_id = portfolios[0].get("PortfolioId") if portfolios else None
            if portfolio_id is not None:
                match_entry["portfolio_id"] = portfolio_id

        matches.append(match_entry)

    return matches
