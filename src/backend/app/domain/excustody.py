"""B1 — Ex-custody report parser.

Parses the 10 ``Privatbank Helvetia AG`` PDFs in ``unriskomega-2026/side-challenge/``
into a portfolio shape compatible with the F5 dataset contract. Every position and KPI
carries a page-level ``evidence`` path (``side-challenge/<file>#page=N``) so the UI can
offer traceability back to the source document.

The PDFs share a fixed 8-page template:

- Page 1: cover KPI card — ``Vermögen per Stichtag``, ``Performance 2025 (TWR, netto)``
- Page 4: ``Vermögensstruktur … Währungen`` — asset × currency cross-table + FX quote
- Pages 6–7: ``Detailpositionen`` ledger (ISIN / Valor / name / Einstand / Marktkurs / %-Anteil)
- Page 8: ``Transaktionen`` (Kauf / Verkauf / Dividende / Coupon / Depotgebühren)

Numbers arrive in Swiss formatting (``2'049'658``, ``5.20 %``, possibly ``-`` or empty
cells). The raw string is preserved alongside the parsed value so a juror can check it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ``pypdf`` is the primary extractor; ``pdfminer`` is available as a fallback but the
# text layer of these PDFs is clean, so pypdf alone is sufficient.
import pypdf

from . import index as index_module
_IBAN = re.compile(r"^CH\d{2}[\s\d]{10,}$")
# Repository root (D:/hack26) — four parents up from this file.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SIDE_CHALLENGE_DIR = _REPO_ROOT / "unriskomega-2026" / "side-challenge"

# Swiss number regex: groups of three digits separated by apostrophes, optional decimals.
_SWISS_INT = re.compile(r"^[+-]?(?:\d{1,3}(?:'\d{3})+|\d+)$")
_SWISS_NUM = re.compile(r"^[+-]?(?:\d{1,3}(?:'\d{3})+|\d+)(?:\.\d+)?$")
_PERCENT = re.compile(r"^[+-]?(?:\d{1,3}(?:'\d{3})+|\d+)(?:\.\d+)?\s?%$")
_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")

_DATE_DMY = re.compile(r"^\d{2}\.\d{2}\.\d{2,4}$")
_DATETIME_RANGE = re.compile(r"^\d{2}\.\d{2}\.\d{4}\s*/\s*\d{2}\.\d{2}\.\d{4}$")

# Asset class headers that open a section in the Detailpositionen ledger.
_ASSET_CLASS_HEADERS = [
    "Liquidität / Geldmarkt",
    "Obligationen",
    "Aktien",
    "Alternative Anlagen",
]
# The "Total" rows that close each section.
_SECTION_TOTALS = [
    "Total Liquidität / Geldmarkt",
    "Total Obligationen",
    "Total Aktien",
    "Total Alternative Anlagen",
    "Total Vermögen",
]

# Currency long-name -> code (page 4 uses long names).
_CURRENCY_LONG_TO_CODE = {
    "Schweizer Franken": "CHF",
    "Euro": "EUR",
    "US Dollar": "USD",
    "Britisches Pfund": "GBP",
    "Japanischer Yen": "JPY",
}


def _strip_apostrophes(s: str) -> str:
    return s.replace("'", "")


def parse_swiss_int(s: str) -> int | None:
    """Parse a Swiss-formatted integer (``1'234`` → 1234). Returns ``None`` on failure."""
    if s is None:
        return None
    s = s.strip()
    if s in ("", "-", "—"):
        return None
    if not _SWISS_INT.match(s):
        return None
    return int(_strip_apostrophes(s))


def parse_swiss_float(s: str) -> float | None:
    """Parse a Swiss-formatted float (``1'234.56`` → 1234.56). Returns ``None`` on failure."""
    if s is None:
        return None
    s = s.strip()
    if s in ("", "-", "—"):
        return None
    if not _SWISS_NUM.match(s):
        return None
    return float(_strip_apostrophes(s))


def parse_percent(s: str) -> float | None:
    """Parse ``5.20 %`` → 5.2 (percentage points, not fraction)."""
    if s is None:
        return None
    s = s.strip()
    if not _PERCENT.match(s):
        return None
    return float(_strip_apostrophes(s.rstrip("%").rstrip()))


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def reports_dir() -> Path:
    """Where uploaded statements are kept — never inside the read-only case-material tree.

    Overridable with ``URO_EXCUSTODY_REPORTS_DIR`` so a test run (and the drill) writes to its own
    temporary directory instead of the working copy.
    """
    override = os.environ.get("URO_EXCUSTODY_REPORTS_DIR")
    return Path(override) if override else _REPO_ROOT / "data" / "excustody" / "reports"


def save_upload(filename: str, content: bytes) -> Path:
    """Write an uploaded statement under :func:`reports_dir` and return its path.

    The name is reduced to its basename and anything outside ``[A-Za-z0-9._-]`` is replaced, so a
    filename arriving from a browser can never choose where the file lands or what it overwrites
    outside that directory.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename or "").name).strip("._-")
    if not safe.lower().endswith(".pdf"):
        safe = f"{safe or 'statement'}.pdf"
    target = reports_dir() / safe
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def delete_upload(path: Path) -> None:
    """Remove a stored upload (used when it turned out not to be a readable statement)."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def list_reports() -> list[dict]:
    """Every readable statement: the ten provided PDFs first, then whatever was uploaded."""
    out: list[dict] = []
    for directory, source in ((_SIDE_CHALLENGE_DIR, "side-challenge"), (reports_dir(), "upload")):
        if not directory.is_dir():
            continue
        for name in sorted(os.listdir(directory)):
            if not name.lower().endswith(".pdf"):
                continue
            path = directory / name
            try:
                reader = pypdf.PdfReader(str(path))
                pages = len(reader.pages)
            except Exception:
                pages = 0
            out.append({
                "file": name,
                "name": _friendly_name(name),
                "size": path.stat().st_size,
                "pages": pages,
                "source": source,
            })
    return out


def _friendly_name(filename: str) -> str:
    """``Quartalsreporting_Q4_2025_01_Herr_Max_Muster.pdf`` → ``Herr Max Muster``.

    A name that does not follow that pattern is returned as-is: an uploaded file is called whatever
    the advisor called it, and inventing a contact from it would be worse than showing the filename.
    """
    stem = filename[:-4] if filename.lower().endswith(".pdf") else filename
    parts = stem.split("_")
    # Format: Quartalsreporting_Q4_2025_<nn>_<Name parts...> — skip the four leading parts.
    if len(parts) >= 5:
        return " ".join(parts[4:]).replace("_", " ").strip()
    return stem


def _resolve_path(file: str | None) -> Path:
    """Resolve a report filename against the two known directories.

    A bare filename only: the endpoint takes this straight from a request, and an arbitrary path
    would let a caller read any file the process can read.
    """
    if not file:
        reports = list_reports()
        if not reports:
            raise FileNotFoundError("no ex-custody reports found in side-challenge/ or the upload directory")
        return _SIDE_CHALLENGE_DIR / reports[0]["file"]
    if Path(file).name != file:
        raise FileNotFoundError(f"report name must not contain a path: {file}")
    for directory in (_SIDE_CHALLENGE_DIR, reports_dir()):
        candidate = directory / file
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"unknown ex-custody report: {file}")


# ---------------------------------------------------------------------------
# Low-level text extraction
# ---------------------------------------------------------------------------


def _extract_pages(path: Path) -> list[str]:
    reader = pypdf.PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def _split_lines(text: str) -> list[str]:
    """Split into non-empty stripped lines."""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Page 1 — KPI card
# ---------------------------------------------------------------------------


def _parse_page1(lines: list[str], file: str) -> dict:
    """Extract the cover KPI card: client, portfolio, currency, Stichtag, Vermögen, TWR."""
    out: dict[str, Any] = {
        "client_name": None,
        "client_name_raw": None,
        "portfolio_label": None,
        "depot_nr": None,
        "mandat": None,
        "currency": None,
        "stichtag": None,
        "stichtag_raw": None,
        "total_value": None,
        "total_value_raw": None,
        "performance_2025_twr_pct": None,
        "performance_2025_twr_raw": None,
        "reported_at": None,
    }
    # Walk lines looking for the labelled fields.
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln == "Kunde" and i + 1 < len(lines):
            out["client_name_raw"] = lines[i + 1]
            out["client_name"] = lines[i + 1]
            i += 2
            continue
        if ln == "Portfolio" and i + 1 < len(lines):
            out["portfolio_label"] = lines[i + 1]
            m = re.search(r"Depot-Nr\.\s*([\d\.]+)", lines[i + 1])
            if m:
                out["depot_nr"] = m.group(1)
            m2 = re.search(r"Mandat\s*«([^»]+)»", lines[i + 1])
            if m2:
                out["mandat"] = m2.group(1)
            i += 2
            continue
        if ln == "Referenzwährung" and i + 1 < len(lines):
            out["currency"] = lines[i + 1]
            i += 2
            continue
        if ln == "Stichtag Bewertung" and i + 1 < len(lines):
            out["stichtag_raw"] = lines[i + 1]
            out["stichtag"] = _parse_date_dmy(lines[i + 1])
            i += 2
            continue
        if ln == "Vermögen per Stichtag" and i + 1 < len(lines):
            # Next line is "CHF 2'049'658" — split off currency + amount.
            raw = lines[i + 1]
            out["total_value_raw"] = raw
            m = re.match(r"^([A-Z]{3})\s+(.+)$", raw)
            if m:
                if out["currency"] is None:
                    out["currency"] = m.group(1)
                out["total_value"] = parse_swiss_int(m.group(2))
                if out["total_value"] is None:
                    out["total_value"] = parse_swiss_float(m.group(2))
            i += 2
            continue
        if ln.startswith("Performance 2025") and "TWR" in ln and i + 1 < len(lines):
            raw = lines[i + 1]
            out["performance_2025_twr_raw"] = raw
            out["performance_2025_twr_pct"] = parse_percent(raw)
            i += 2
            continue
        if ln.startswith("Erstellt am"):
            m = re.search(r"Erstellt am\s+(\d{2}\.\d{2}\.\d{4})", ln)
            if m:
                out["reported_at"] = _parse_date_dmy(m.group(1))
            i += 1
            continue
        i += 1
    out["evidence"] = f"side-challenge/{file}#page=1"
    return out


def _parse_date_dmy(s: str) -> str | None:
    """``31.12.2025`` → ``2025-12-31`` (ISO)."""
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{2,4})$", s.strip())
    if not m:
        return None
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    return f"{y}-{mo}-{d}"


# ---------------------------------------------------------------------------
# Page 4 — asset × currency cross-table + FX quote
# ---------------------------------------------------------------------------


def _parse_page4(lines: list[str], file: str) -> dict:
    """Parse the Vermögensstruktur cross-table and the unhedged FX quote."""
    result: dict[str, Any] = {
        "currencies": [],
        "unhedged_foreign_currency_chf": None,
        "unhedged_foreign_currency_pct": None,
        "unhedged_raw": None,
        "asset_class_totals_pct": {},
    }
    # Find currency rows by looking for lines like "Schweizer Franken (CHF)".
    currency_pattern = re.compile(r"^(.+?)\s*\(([A-Z]{3})\)$")
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = currency_pattern.match(ln)
        if m:
            long_name = m.group(1).strip()
            code = m.group(2)
            # Next 10 tokens are 5 pairs of (amount, percent) for Liqu/Obl/Akt/Alt/Total.
            amounts: list[float] = []
            percents: list[float] = []
            j = i + 1
            while j < len(lines) and len(amounts) < 5:
                v = parse_swiss_int(lines[j])
                if v is None:
                    v = parse_swiss_float(lines[j])
                if v is not None:
                    amounts.append(float(v))
                    j += 1
                    continue
                p = parse_percent(lines[j])
                if p is not None:
                    percents.append(p)
                    j += 1
                    continue
                # Anything else ends this currency's row.
                break
            entry = {
                "code": code,
                "name": long_name,
                "amounts": {
                    "liquidity": amounts[0] if len(amounts) > 0 else None,
                    "bonds": amounts[1] if len(amounts) > 1 else None,
                    "shares": amounts[2] if len(amounts) > 2 else None,
                    "alternatives": amounts[3] if len(amounts) > 3 else None,
                    "total": amounts[4] if len(amounts) > 4 else None,
                },
                "percents": {
                    "liquidity": percents[0] if len(percents) > 0 else None,
                    "bonds": percents[1] if len(percents) > 1 else None,
                    "shares": percents[2] if len(percents) > 2 else None,
                    "alternatives": percents[3] if len(percents) > 3 else None,
                    "total": percents[4] if len(percents) > 4 else None,
                },
                "evidence": f"side-challenge/{file}#page=4",
            }
            result["currencies"].append(entry)
            if len(amounts) > 4:
                result["asset_class_totals_pct"][code] = percents[4] if len(percents) > 4 else None
            i = j
            continue
        if ln.startswith("Total") and "Total" in ln and ln != "Total":
            # "Total" row for asset classes — skip; we already have per-currency totals.
            i += 1
            continue
        if ln.startswith("davon Wertschriften in Fremdwährungen ohne Absicherung"):
            result["unhedged_raw"] = ln
            mch = re.search(r"CHF\s+([\d'\.]+)\s*\(([\d'\.]+)\s?%\s*des", ln)
            if mch:
                result["unhedged_foreign_currency_chf"] = parse_swiss_int(mch.group(1))
                result["unhedged_foreign_currency_pct"] = parse_swiss_float(mch.group(2))
            i += 1
            continue
        i += 1
    return result


# ---------------------------------------------------------------------------
# Pages 6–7 — Detailpositionen ledger
# ---------------------------------------------------------------------------


def _is_header_or_total(line: str) -> bool:
    if line in _ASSET_CLASS_HEADERS:
        return True
    if line in _SECTION_TOTALS:
        return True
    if line in (
        "Detailpositionen per 31.12.2025, in CHF",
        "Detailpositionen (Fortsetzung) per 31.12.2025, in CHF",
        "Whg",
        "Stück /",
        "Nominal",
        "Bezeichnung",
        "Valor / ISIN / IBAN",
        "Valor / ISIN",
        "Einstand",
        "Marktkurs",
        "Kurs-",
        "Datum",
        "Marktwert",
        "%-Anteil",
        "Stück / Nominal",
    ):
        return True
    if line.startswith("Seite "):
        return True
    return False


def _is_cash_account_name(line: str) -> bool:
    return line.startswith("Privatkonto ")


def _is_iban(line: str) -> bool:
    return bool(_IBAN.match(line.replace(" ", ""))) or bool(_IBAN.match(line))


def _looks_like_isin_or_valor_token(token: str) -> tuple[str | None, str | None]:
    """Given a line like ``2 000 654 / US0231351067`` return (valor, isin)."""
    if " / " not in token:
        # Could be a bare ISIN.
        if _ISIN.match(token):
            return None, token
        return None, None
    left, right = token.split(" / ", 1)
    left = left.strip()
    right = right.strip()
    valor = left if left else None
    isin = right if _ISIN.match(right) else None
    return valor, isin


def _parse_positions(pages6_7: list[tuple[int, str]], file: str) -> list[dict]:
    """Parse the Detailpositionen ledger across pages 6 and 7."""
    # Concatenate lines with page markers.
    entries: list[tuple[int, str]] = []
    for page_num, text in pages6_7:
        for ln in _split_lines(text):
            entries.append((page_num, ln))

    positions: list[dict] = []
    current_asset_class: str | None = None
    i = 0
    n = len(entries)

    while i < n:
        page_num, ln = entries[i]

        # Track asset class sections.
        if ln in _ASSET_CLASS_HEADERS:
            current_asset_class = ln
            i += 1
            continue
        if ln in _SECTION_TOTALS:
            # Skip the total line plus its two values (amount + percent).
            i += 1
            # Consume amount + percent if present.
            skipped = 0
            while i < n and skipped < 2:
                ppage, pln = entries[i]
                if parse_swiss_int(pln) is not None or parse_swiss_float(pln) is not None:
                    i += 1
                    skipped += 1
                    continue
                if parse_percent(pln) is not None:
                    i += 1
                    skipped += 1
                    continue
                break
            continue
        if _is_header_or_total(ln):
            i += 1
            continue

        # Try to parse a position block starting here.
        pos, consumed = _try_parse_position_block(entries, i, current_asset_class, file)
        if pos is not None:
            positions.append(pos)
            i += consumed
            continue
        i += 1

    return positions


def _try_parse_position_block(
    entries: list[tuple[int, str]],
    start: int,
    current_asset_class: str | None,
    file: str,
) -> tuple[dict | None, int]:
    """Attempt to parse a position block starting at ``start``.

    Returns ``(position_dict, consumed_lines)`` on success, else ``(None, 0)``.
    """
    n = len(entries)
    # A position block starts with a currency code (3 uppercase letters).
    page0, first = entries[start]
    if not re.match(r"^[A-Z]{3}$", first):
        return None, 0
    currency = first

    # Next: quantity (Swiss int or float) OR directly a name if this is a cash account.
    # Cash accounts: currency, amount (with decimals), name (Privatkonto ...), IBAN, date, value, percent.
    # Securities: currency, quantity, name, valor/ISIN, einstand, market price, date, market value, percent.

    # Look ahead to find the structure.
    j = start + 1
    if j >= n:
        return None, 0
    page_qty, qty_str = entries[j]

    qty_val = parse_swiss_float(qty_str)
    if qty_val is None:
        return None, 0
    j += 1

    # Name line.
    if j >= n:
        return None, 0
    page_name, name_line = entries[j]
    # Name must not be a number, percent, date, or header.
    if (
        parse_swiss_float(name_line) is not None
        or parse_percent(name_line) is not None
        or _DATE_DMY.match(name_line)
        or name_line in _ASSET_CLASS_HEADERS
        or name_line in _SECTION_TOTALS
        or _is_header_or_total(name_line)
    ):
        return None, 0
    j += 1

    # Next line: either "valor / ISIN", or an IBAN (cash account), or a date (cash account w/o IBAN line).
    if j >= n:
        return None, 0
    page_ident, ident_line = entries[j]

    is_cash = _is_cash_account_name(name_line)

    valor: str | None = None
    isin: str | None = None
    date_str: str | None = None
    cost_price: float | None = None
    market_price: float | None = None
    market_value: float | None = None
    weight_pct: float | None = None
    cost_basis: float | None = None

    if is_cash:
        # Cash account: ident_line may be IBAN, then optional FX rate, then date, market_value, percent.
        if _is_iban(ident_line):
            j += 1  # skip IBAN — never emit
        if j >= n:
            return None, 0
        # Check for optional FX rate (a float like 0.9420)
        page_fx, fx_str = entries[j]
        fx_val = parse_swiss_float(fx_str)
        if fx_val is not None and fx_val < 10:  # FX rates are small numbers
            j += 1  # skip FX rate
        if j >= n:
            return None, 0
        page_date, date_line = entries[j]
        if _DATE_DMY.match(date_line):
            date_str = date_line
            j += 1
        # market value
        if j >= n:
            return None, 0
        page_mv, mv_str = entries[j]
        market_value = parse_swiss_int(mv_str)
        if market_value is None:
            market_value = parse_swiss_float(mv_str)
        if market_value is None:
            return None, 0
        j += 1
        # percent
        if j >= n:
            return None, 0
        page_w, w_str = entries[j]
        weight_pct = parse_percent(w_str)
        if weight_pct is None:
            return None, 0
        j += 1
        # For cash, quantity is the account balance in currency units.
        quantity = qty_val
        position = {
            "asset_class": current_asset_class,
            "name": name_line,
            "currency": currency,
            "quantity": quantity,
            "quantity_raw": qty_str,
            "valor": None,
            "isin": None,
            "cost_price": None,
            "cost_price_raw": None,
            "market_price": None,
            "market_price_raw": None,
            "cost_basis": None,
            "market_value": market_value,
            "market_value_raw": mv_str,
            "weight": (weight_pct / 100.0) if weight_pct is not None else None,
            "weight_pct_raw": w_str,
            "date": _parse_date_dmy(date_str) if date_str else None,
            "date_raw": date_str,
            "is_cash": True,
            "page": page0,
            "evidence": f"side-challenge/{file}#page={page0}",
        }
        return position, j - start

    # Security position: ident_line is "valor / ISIN".
    valor, isin = _looks_like_isin_or_valor_token(ident_line)
    if isin is None and valor is None:
        return None, 0
    j += 1

    # Einstand (cost price per unit).
    if j >= n:
        return None, 0
    page_cp, cp_str = entries[j]
    cost_price = parse_swiss_float(cp_str)
    if cost_price is None:
        return None, 0
    j += 1

    # Marktkurs (market price per unit).
    if j >= n:
        return None, 0
    page_mp, mp_str = entries[j]
    market_price = parse_swiss_float(mp_str)
    if market_price is None:
        return None, 0
    j += 1

    # Kurs-Datum.
    if j >= n:
        return None, 0
    page_d, d_str = entries[j]
    if not _DATE_DMY.match(d_str):
        return None, 0
    date_str = d_str
    j += 1

    # Marktwert (CHF).
    if j >= n:
        return None, 0
    page_mv, mv_str = entries[j]
    market_value = parse_swiss_int(mv_str)
    if market_value is None:
        market_value = parse_swiss_float(mv_str)
    if market_value is None:
        return None, 0
    j += 1

    # %-Anteil.
    if j >= n:
        return None, 0
    page_w, w_str = entries[j]
    weight_pct = parse_percent(w_str)
    if weight_pct is None:
        return None, 0
    j += 1

    quantity = qty_val
    # Cost basis = quantity * cost_price (in position currency), but we report CHF market value.
    # Keep cost_basis in CHF as market_value - we don't have an FX conversion here; leave None.
    position = {
        "asset_class": current_asset_class,
        "name": name_line,
        "currency": currency,
        "quantity": quantity,
        "quantity_raw": qty_str,
        "valor": valor,
        "isin": isin,
        "cost_price": cost_price,
        "cost_price_raw": cp_str,
        "market_price": market_price,
        "market_price_raw": mp_str,
        "cost_basis": None,  # not printed in the PDF; derivable from quantity * cost_price in position ccy
        "market_value": market_value,
        "market_value_raw": mv_str,
        "weight": (weight_pct / 100.0) if weight_pct is not None else None,
        "weight_pct_raw": w_str,
        "date": _parse_date_dmy(date_str) if date_str else None,
        "date_raw": date_str,
        "is_cash": False,
        "page": page0,
        "evidence": f"side-challenge/{file}#page={page0}",
    }
    return position, j - start


# ---------------------------------------------------------------------------
# Page 8 — Transaktionen
# ---------------------------------------------------------------------------


_TXN_TYPES = {"Kauf", "Verkauf", "Dividende", "Coupon", "Depotgebühren", "Vermögenszufluss"}


def _parse_transactions(page8: str, file: str) -> list[dict]:
    lines = _split_lines(page8)
    txns: list[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        # A transaction block starts with either a currency code or directly a known txn type
        # for fee rows (Depotgebühren) and cash flows (Vermögenszufluss).
        currency: str | None = None
        qty_raw: str | None = None
        qty: float | None = None
        txn_type: str | None = None
        name: str | None = None
        valor: str | None = None
        isin: str | None = None
        booking_date: str | None = None
        price_raw: str | None = None
        price: float | None = None
        amount_chf_raw: str | None = None
        amount_chf: float | None = None
        cost_raw: str | None = None
        cost: float | None = None

        if re.match(r"^[A-Z]{3}$", ln):
            currency = ln
            i += 1
            if i >= n:
                break
            # Next may be quantity, or a txn type directly (e.g. for "Vermögenszufluss").
            nxt = lines[i]
            if nxt in _TXN_TYPES:
                txn_type = nxt
                qty = None
                qty_raw = None
            else:
                q = parse_swiss_float(nxt)
                if q is None:
                    # Not a quantity; treat this line as something else and back out.
                    i -= 1
                    i += 1
                    continue
                qty = q
                qty_raw = nxt
                i += 1
                if i >= n:
                    break
                nxt = lines[i]
                if nxt in _TXN_TYPES:
                    txn_type = nxt
                else:
                    # Not a recognised transaction — skip.
                    continue
        elif ln in _TXN_TYPES:
            txn_type = ln
            currency = None
        else:
            i += 1
            continue

        i += 1
        # Name / description.
        if i >= n:
            break
        name = lines[i]
        i += 1
        # Valor / ISIN — except for Depotgebühren / Vermögenszufluss which have no valor.
        if txn_type in ("Depotgebühren", "Vermögenszufluss"):
            # Next is a date range or date.
            if i >= n:
                break
            date_line = lines[i]
            if _DATETIME_RANGE.match(date_line):
                booking_date = date_line.split("/")[-1].strip()
                i += 1
            elif _DATE_DMY.match(date_line):
                booking_date = date_line
                i += 1
        else:
            if i >= n:
                break
            ident = lines[i]
            valor, isin = _looks_like_isin_or_valor_token(ident)
            i += 1
            # Date range.
            if i >= n:
                break
            date_line = lines[i]
            if _DATETIME_RANGE.match(date_line):
                booking_date = date_line.split("/")[0].strip()
                i += 1
            elif _DATE_DMY.match(date_line):
                booking_date = date_line
                i += 1
        # Amount CHF (signed).
        if i >= n:
            break
        amount_chf_raw = lines[i]
        amount_chf = parse_swiss_float(lines[i])
        if amount_chf is None:
            # Skip malformed.
            continue
        i += 1
        # Aufwand / Ertrag.
        if i >= n:
            break
        cost_raw = lines[i]
        cost = parse_swiss_float(lines[i])
        i += 1
        # Trailing currency code on some rows (e.g. "CHF") — skip if present.
        if i < n and re.match(r"^[A-Z]{3}$", lines[i]):
            i += 1

        txns.append({
            "type": txn_type,
            "name": name,
            "currency": currency,
            "quantity": qty,
            "quantity_raw": qty_raw,
            "valor": valor,
            "isin": isin,
            "booking_date": _parse_date_dmy(booking_date) if booking_date else None,
            "booking_date_raw": booking_date,
            "price": price,
            "price_raw": price_raw,
            "amount_chf": amount_chf,
            "amount_chf_raw": amount_chf_raw,
            "cost": cost,
            "cost_raw": cost_raw,
            "evidence": f"side-challenge/{file}#page=8",
        })
    return txns


# ---------------------------------------------------------------------------
# Top-level parse
# ---------------------------------------------------------------------------


def parse_report(path: str | Path) -> dict:
    """Parse a single ex-custody PDF into a portfolio-shaped dict."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"ex-custody report not found: {path}")
    file = path.name
    pages = _extract_pages(path)
    if len(pages) < 8:
        raise ValueError(f"expected 8 pages in {file}, got {len(pages)}")

    page1 = _parse_page1(_split_lines(pages[0]), file)
    page4 = _parse_page4(_split_lines(pages[3]), file)
    positions = _parse_positions([(6, pages[5]), (7, pages[6])], file)
    transactions = _parse_transactions(pages[7], file)

    # ISIN resolution against the F5 security master.
    matched = 0
    unmatched_isins: list[str] = []
    try:
        dataset = index_module.get()
    except Exception:
        dataset = None
    for pos in positions:
        pos["matched_security_id"] = None
        pos["matched_security_name"] = None
        isin = pos.get("isin")
        if isin and dataset is not None:
            sec = dataset.security_by_isin(isin)
            if sec is not None:
                pos["matched_security_id"] = int(sec.get("Id")) if sec.get("Id") is not None else None
                pos["matched_security_name"] = sec.get("Name")
                matched += 1
            else:
                unmatched_isins.append(isin)

    # Cross-check: sum of position market values vs page 1 total.
    position_total = sum(p.get("market_value") or 0 for p in positions)
    reported_total = page1.get("total_value")
    total_delta = None
    if position_total and reported_total:
        total_delta = position_total - reported_total

    # Gaps: anything we could not parse.
    gaps: list[str] = []
    if page1.get("total_value") is None:
        gaps.append("page 1: Vermögen per Stichtag not parsed")
    if page1.get("performance_2025_twr_pct") is None:
        gaps.append("page 1: Performance 2025 (TWR, netto) not parsed")
    if not positions:
        gaps.append("pages 6-7: no positions parsed")
    if not transactions:
        gaps.append("page 8: no transactions parsed")

    unavailable: list[str] = []
    if not page4.get("currencies"):
        unavailable.append("page 4: currency structure not parsed")

    return {
        "source": "ex-custody",
        "provenance": "ex_custody",
        "file": file,
        "pages": len(pages),
        "client_name": page1.get("client_name"),
        "portfolio_label": page1.get("portfolio_label"),
        "depot_nr": page1.get("depot_nr"),
        "mandat": page1.get("mandat"),
        "reported_at": page1.get("reported_at") or page1.get("stichtag"),
        "stichtag": page1.get("stichtag"),
        "currency": page1.get("currency") or "CHF",
        "total_value": page1.get("total_value"),
        "total_value_raw": page1.get("total_value_raw"),
        "performance_2025_twr_pct": page1.get("performance_2025_twr_pct"),
        "performance_2025_twr_raw": page1.get("performance_2025_twr_raw"),
        "positions": positions,
        "position_count": len(positions),
        "position_total_chf": position_total,
        "position_total_vs_reported_delta": total_delta,
        "currency_structure": page4.get("currencies", []),
        "unhedged_foreign_currency_chf": page4.get("unhedged_foreign_currency_chf"),
        "unhedged_foreign_currency_pct": page4.get("unhedged_foreign_currency_pct"),
        "transactions": transactions,
        "transaction_count": len(transactions),
        "isins_matched": matched,
        "isins_unmatched": unmatched_isins,
        "unavailable": unavailable,
        "gaps": gaps,
        "evidence": {
            "kpi": f"side-challenge/{file}#page=1",
            "currency_structure": f"side-challenge/{file}#page=4",
            "positions": [p["evidence"] for p in positions],
            "transactions": f"side-challenge/{file}#page=8",
        },
    }


# ---------------------------------------------------------------------------
# Convenience for the API layer
# ---------------------------------------------------------------------------


def parse_default_or(file: str | None = None) -> dict:
    """Resolve ``file`` (or the first sorted report) and parse it."""
    path = _resolve_path(file)
    return parse_report(path)
