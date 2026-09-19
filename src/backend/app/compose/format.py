"""Swiss/German formatting for rendered briefing prose.

The Python counterpart of ``frontend/src/utils/format.ts`` — same conventions, same apostrophe
(U+0027, not the typographic one ICU would produce for ``de-CH``).
"""

from __future__ import annotations

APOSTROPHE = "'"


def amount(value: float | None, decimals: int = 2) -> str:
    """Swiss grouping: ``2'049'658.00``."""
    if value is None:
        return "—"
    fixed = f"{abs(value):.{decimals}f}"
    whole, _, fraction_part = fixed.partition(".")
    grouped = f"{int(whole):,}".replace(",", APOSTROPHE)
    sign = "-" if value < 0 else ""
    return f"{sign}{grouped}.{fraction_part}" if fraction_part else f"{sign}{grouped}"


def money(value: float | None, currency: str = "CHF", decimals: int = 2) -> str:
    return f"{currency} {amount(value, decimals)}"


def pct(value: float | None, decimals: int = 2, signed: bool = False) -> str:
    """For a value that is already a percentage: ``15.15%``."""
    if value is None:
        return "—"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def fraction(value: float | None, decimals: int = 2, signed: bool = False) -> str:
    """For a 0–1 weight: ``56.70%``."""
    if value is None:
        return "—"
    return pct(value * 100, decimals, signed)


def date(iso: str | None) -> str:
    """``2026-07-01`` → ``01.07.2026``."""
    if not iso or len(iso) < 10:
        return "—"
    return f"{iso[8:10]}.{iso[5:7]}.{iso[0:4]}"


def sentence(text: str) -> str:
    """Ensure a block ends as a sentence, without doubling an existing terminator."""
    stripped = text.strip()
    return stripped if stripped.endswith((".", "!", "?", ":")) else f"{stripped}."
