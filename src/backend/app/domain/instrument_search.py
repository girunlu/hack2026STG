"""Instrument lookup over the security master — the entry point of an advisor search.

The briefing never needs this: it starts from a holding and already carries the ``SecurityId``. An
advisor starts from a word, so the row has to be found first. Matching uses the keys the master
actually carries — ISIN, Valor and name — and never guesses a symbol, because no ticker table
exists anywhere in the provided data.

Two facts about the data shape the result:

* one ISIN is often several master rows (currency share classes, ``PROJECT.md`` §7.2), so a hit
  returns the best row *plus* the other instruments the query could have meant, rather than
  silently choosing one and presenting it as *the* answer;
* the master was trimmed after generation to the ISINs the case clients hold (``STATUS.md`` §6.5),
  so the common case for a search is a miss. ``matched: False`` is a normal answer, not an error.
"""

from __future__ import annotations

import re

from . import index

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Name-match ranks. An exact hit beats a prefix, which beats a hit inside the name — the master
# spells names the way a bank does ("Na. u. Inh. Ti.-Aktie ASML Holding NV"), so "asml holding nv"
# only ever matches by containment and must still beat a longer partial match.
_EXACT, _PREFIX, _CONTAINS = 3, 2, 1

# Below this a name query matches too much to be a search ("ag", "sa").
_MIN_NAME_CHARS = 3


def _key(value: str) -> str:
    """Comparison key: lowercase, punctuation flattened to single spaces."""
    return _NON_ALNUM.sub(" ", value.lower()).strip()


def _digits(value: str) -> str:
    """Digits only, without leading zeros — the master prints Valors as ``989 001``."""
    return re.sub(r"\D", "", value or "").lstrip("0")


def _brief(security: dict) -> dict:
    """The few fields an alternative needs to be recognisable in a list."""
    return {
        "security_id": security.get("Id"),
        "name": security.get("Name"),
        "isin": security.get("Isin"),
        "currency": security.get("Currency"),
        "security_type": security.get("SecurityTypeName"),
    }


def _miss(raw: str) -> dict:
    return {
        "matched": False,
        "raw_query": raw,
        "matched_on": None,
        "security": None,
        "alternatives": [],
        "share_class_count": 0,
    }


def _hit(rows: list[dict], raw: str, matched_on: str, limit: int, dataset) -> dict:
    """Build the result for a resolved query.

    ``rows`` is ordered best-first. The first row is the instrument; the master rows sharing its
    ISIN are its share classes (counted, not listed as alternatives); every *other* row is a
    different instrument the query could have meant.
    """
    best = rows[0]
    isin = str(best.get("Isin") or "")
    alternatives: list[dict] = []
    seen_isins = {isin}
    for row in rows[1:]:
        row_isin = str(row.get("Isin") or "")
        if row_isin in seen_isins:
            continue
        seen_isins.add(row_isin)
        alternatives.append(_brief(row))
        if len(alternatives) >= limit:
            break
    return {
        "matched": True,
        "raw_query": raw,
        "matched_on": matched_on,
        "security": best,
        "alternatives": alternatives,
        "share_class_count": len(dataset.securities_by_isin(isin)) or 1,
    }


def resolve(query: str, limit: int = 5) -> dict:
    """Find the master row(s) a query refers to.

    Args:
        query: ISIN, Valor or (partial) instrument name.
        limit: Max alternatives to return alongside the matched row.

    Returns:
        ``{"matched", "raw_query", "matched_on", "security", "alternatives", "share_class_count"}``
        where ``matched_on`` is ``"isin"``, ``"valor"`` or ``"name"``.
    """
    raw = (query or "").strip()
    if not raw:
        return _miss(raw)

    dataset = index.get()

    # ISIN first: the only unambiguous key in the data.
    upper = raw.upper()
    if _ISIN_RE.match(upper):
        rows = dataset.securities_by_isin(upper)
        if rows:
            return _hit(list(rows), raw, "isin", limit, dataset)

    # Valor: digits only, at least four of them, or "989 001" would look like a name.
    digits = _digits(raw)
    if len(digits) >= 4 and not any(character.isalpha() for character in raw):
        rows = [s for s in dataset.securities if _digits(str(s.get("Valor") or "")) == digits]
        if rows:
            return _hit(rows, raw, "valor", limit, dataset)

    needle = _key(raw)
    if len(needle.replace(" ", "")) < _MIN_NAME_CHARS:
        return _miss(raw)

    scored: list[tuple[int, dict]] = []
    for security in dataset.securities:
        name_key = _key(str(security.get("Name") or ""))
        if not name_key:
            continue
        if name_key == needle:
            rank = _EXACT
        elif name_key.startswith(needle):
            rank = _PREFIX
        elif needle in name_key:
            rank = _CONTAINS
        else:
            continue
        scored.append((rank, security))

    if not scored:
        return _miss(raw)

    # Best rank first, then the shortest name: "Nestlé AG" beats "Nestlé AG Namensaktie" for the
    # query "nestle", and the order stays deterministic for a repeated search.
    scored.sort(key=lambda pair: (-pair[0], len(str(pair[1].get("Name") or "")), str(pair[1].get("Name") or "")))
    return _hit([security for _, security in scored], raw, "name", limit, dataset)
