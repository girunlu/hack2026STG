"""Engine field vocabulary — the ``ViolationPath`` field names of ``SuitabilityViolations``.

The risk engine names its comparison fields after its own C# types (``SimulationVolatilityRuleField`1``).
Three consumers have to speak about them — R3 (which explains a violation with the engine's own
comparison), R4 (which phrases it) and F3 (which prints it) — and they must agree twice over:

* on the human name, so no screen shows ``RegulatoryClientTypeRuleField`1``;
* on the unit, so the same comparison is not ``0.1264`` in one place and ``12.6384%`` in the next.

``unit`` is derived from the engine's own field name, never guessed. Only fields whose two sides are a
0–1 fraction (volatility, portfolio value share) are ratios. Contract-class fields such as
``RegulatoryClientTypeRuleField`` or ``PositionIsSecurityRuleField`` compare codes, ids and booleans;
a percentage there would invent a unit the engine never had.
"""

from __future__ import annotations

from .i18n import DEFAULT_LANG, t

# The engine's own field name stays the truth; these are only mechanical trims before the catalogue
# lookup. Order matters only in that the loop repeats until nothing matches (``GenericSimulation…``).
PREFIXES = ("Simulation", "Generic", "Regulatory", "Filter")
SUFFIXES = ("RuleField", "Field")

RATIO_MARKERS = ("Volatility", "PortfolioValue")

RATIO = "ratio"
VALUE = "value"


def trim(field_name: str) -> str:
    """``SimulationFilterTopLevelSAACurrencyGroupRuleField`` → ``TopLevelSAACurrencyGroup``."""
    name = str(field_name or "").split("`")[0]
    changed = True
    while changed:
        changed = False
        for prefix in PREFIXES:
            if name.startswith(prefix) and len(name) > len(prefix):
                name = name[len(prefix):]
                changed = True
        for suffix in SUFFIXES:
            if name.endswith(suffix) and len(name) > len(suffix):
                name = name[:-len(suffix)]
                changed = True
    return name or str(field_name or "")


def label(field_name: str, lang: str = DEFAULT_LANG) -> str:
    """Localised name of the compared field. An unknown field keeps the engine's own wording."""
    name = trim(field_name)
    key = f"field.{name}"
    translated = t(key, lang)
    return translated if translated != key else (name or str(field_name or ""))


def unit(field_name: str) -> str:
    """``ratio`` when both sides are 0–1 fractions, else ``value`` (codes, ids, booleans, amounts)."""
    name = trim(field_name)
    return RATIO if any(marker in name for marker in RATIO_MARKERS) else VALUE
