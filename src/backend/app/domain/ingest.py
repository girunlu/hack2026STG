"""F5 — ingest and normalisation helpers.

This module and its siblings in ``app.domain`` are the **only** place that reads or indexes the
provided JSON. Everything else in the backend consumes the ``Dataset`` in ``index.py``.

The provided data mixes two conventions for "no value": the key is absent, or the key is present
with ``null``. Both must behave identically — ``obj.get(key, [])`` is a bug, because a present-but-null
key returns ``None`` and the next ``len()``/iteration crashes. Use :func:`opt`, :func:`listof`,
:func:`num`, :func:`text`.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from . import excustody_store, uploads

# src/backend/app/domain/ingest.py -> parents[4] is the repository root (D:/hack26)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DATA_DIR = _REPO_ROOT / "unriskomega-2026" / "core-case" / "portfolio-data"

CLIENTS_FILE = "clients.json"
REFERENCE_FILE = "reference.json"


def data_dir() -> Path:
    """Directory holding ``clients.json`` and ``reference.json``.

    Overridable with ``URO_DATA_DIR`` so an unseen test client can be dropped in without editing code.
    """
    override = os.environ.get("URO_DATA_DIR")
    return Path(override) if override else _DEFAULT_DATA_DIR


def opt(obj: Any, key: str) -> Any:
    """Value or ``None``. A missing key and an explicit ``null`` are indistinguishable."""
    return obj.get(key) if isinstance(obj, dict) else None


def listof(obj: Any, key: str) -> list:
    """A list, always. Missing, ``null`` or a wrong type all become ``[]``."""
    value = opt(obj, key)
    return value if isinstance(value, list) else []


def num(obj: Any, key: str, default: float = 0.0) -> float:
    """A float, never ``None``. Booleans are not numbers here."""
    value = opt(obj, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def intnum(obj: Any, key: str, default: int = 0) -> int:
    """An int, never ``None``."""
    value = opt(obj, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


def text(obj: Any, key: str, default: str = "") -> str:
    """A string, never ``None``."""
    value = opt(obj, key)
    return value if isinstance(value, str) else default


def flag(obj: Any, key: str, default: bool = False) -> bool:
    """A bool, never ``None``."""
    value = opt(obj, key)
    return value if isinstance(value, bool) else default


def day(value: Any) -> str | None:
    """ISO date or timestamp -> ``YYYY-MM-DD``, else ``None``."""
    if isinstance(value, str) and len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return value[:10]
    return None


def as_date(value: Any) -> date | None:
    """ISO date or timestamp -> :class:`datetime.date`, else ``None``."""
    iso = day(value)
    if not iso:
        return None
    try:
        return date(int(iso[:4]), int(iso[5:7]), int(iso[8:10]))
    except ValueError:
        return None


def redact(obj: Any) -> Any:
    """Recursively drop IBAN-bearing keys.

    ``AccountPositions[].IBAN`` is real data. It must never be rendered, logged or transmitted, so it
    is stripped at the API boundary rather than trusted to the frontend.
    """
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items() if k.lower() != "iban"}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


# Problems raised by the most recent load: unusable uploads, ClientRef collisions. Surfaced by
# F5's health endpoint and the dataset ingestion API; never fatal.
LOAD_WARNINGS: list[str] = []


def load_raw() -> tuple[list, dict]:
    """Read both provided files, **plus** every additional client file under ``data/uploads/``.

    Uploads are merged here rather than at the API layer so ``index.load(force=True)`` stays the
    single reload path and no consumer has to know that uploaded files exist.

    A ``ClientRef`` already present in the provided data is never overridden — the case data stays
    authoritative and the clash is recorded in :data:`LOAD_WARNINGS`.
    """
    global LOAD_WARNINGS

    directory = data_dir()
    with (directory / CLIENTS_FILE).open(encoding="utf-8") as handle:
        clients = json.load(handle)
    with (directory / REFERENCE_FILE).open(encoding="utf-8") as handle:
        reference = json.load(handle)
    if not isinstance(clients, list):
        raise ValueError(f"{directory / CLIENTS_FILE} is not a list")
    if not isinstance(reference, dict):
        raise ValueError(f"{directory / REFERENCE_FILE} is not an object")

    uploaded, problems = uploads.load_all()
    warnings: list[str] = list(problems)
    known = {text(client, "ClientRef") for client in clients}
    added: list[dict] = []
    for client in uploaded:
        reference_id = text(client, "ClientRef")
        if reference_id in known:
            warnings.append(
                f"uploaded client {reference_id!r} already exists in the provided data "
                "— skipped, provided data wins"
            )
            continue
        known.add(reference_id)
        added.append(client)

    # B1: imported ex-custody portfolios join their client's own book, so every existing consumer
    # (F3, F4, R2, R3, R6) treats them like native portfolios with no special-casing.
    imported, import_problems = excustody_store.load_all()
    warnings.extend(import_problems)
    if imported:
        for client in clients + added:
            extra = imported.get(excustody_store.client_key(text(client, "ClientRef")))
            if not extra:
                continue
            bucket = client.get("Portfolios")
            if not isinstance(bucket, list):
                bucket = []
                client["Portfolios"] = bucket
            bucket.extend(extra)

    LOAD_WARNINGS = warnings
    return clients + added, reference
