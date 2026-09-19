"""Client-file ingestion — accept additional client files shaped like ``clients.json``.

The case README is explicit that three further client files arrive later and the solution must
*"accept new files of this shape (for example via an upload) rather than hardcoding the one you have
today"*. The brief adds that a previously unseen test client may be presented at the final.

Files land in ``data/uploads/`` — outside the read-only ``unriskomega-2026/`` materials — and are
merged into the dataset by :func:`ingest.load_raw`, so ``index.load(force=True)`` stays the single
reload path.

Nothing here validates against the security master. ``reference.json`` is trimmed to the rows the
original 47 clients reference, so a new client may legitimately reference securities we do not hold;
those are reported as unresolved rather than dropped.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# src/backend/app/domain/uploads.py -> parents[4] is the repository root (D:/hack26)
_REPO_ROOT = Path(__file__).resolve().parents[4]

# Every uploaded client file. Never inside unriskomega-2026/ — that tree is read-only source material.
UPLOAD_DIR = _REPO_ROOT / "data" / "uploads"

MAX_BYTES = 20 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def upload_dir() -> Path:
    """Directory holding uploaded client files.

    Read from the environment on every call so tests can point it at a temporary directory.
    """
    override = os.environ.get("URO_UPLOAD_DIR")
    return Path(override) if override else UPLOAD_DIR


def ensure_dir() -> Path:
    directory = upload_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_name(filename: str) -> str:
    """A filesystem-safe ``.json`` name. Never a path, never empty."""
    stem = os.path.basename(filename or "").strip() or "clients"
    stem = _SAFE_NAME.sub("_", stem)
    if not stem.lower().endswith(".json"):
        stem += ".json"
    return stem[:120]


def parse(raw: bytes) -> tuple[list[dict], list[str]]:
    """Decode and structurally validate an uploaded client file.

    Returns ``(clients, warnings)``. Raises ``ValueError`` when the payload is unusable, so a bad
    upload is rejected before anything is persisted.
    """
    if len(raw) > MAX_BYTES:
        raise ValueError(f"file too large: {len(raw)} bytes (limit {MAX_BYTES})")
    if not raw.strip():
        raise ValueError("file is empty")
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("file is not valid UTF-8") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"file is not valid JSON: {error.msg} (line {error.lineno})") from error

    # Accept the canonical array, a single client object, or a wrapper carrying one.
    if isinstance(payload, dict):
        wrapped = next((payload[k] for k in ("clients", "Clients") if isinstance(payload.get(k), list)), None)
        payload = wrapped if wrapped is not None else [payload]
    if not isinstance(payload, list):
        raise ValueError("expected a JSON array of client objects (the shape of clients.json)")

    clients: list[dict] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            warnings.append(f"entry {index}: not an object — skipped")
            continue
        reference = entry.get("ClientRef")
        if not isinstance(reference, str) or not reference.strip():
            warnings.append(f"entry {index}: no ClientRef — skipped")
            continue
        if reference in seen:
            warnings.append(f"entry {index}: duplicate ClientRef {reference!r} within the file — skipped")
            continue
        seen.add(reference)
        clients.append(entry)

    if not clients:
        raise ValueError("no usable client objects found (every entry lacked a ClientRef)")
    return clients, warnings


def save(filename: str, raw: bytes) -> dict:
    """Validate, then persist atomically. A validation failure leaves the store untouched."""
    clients, warnings = parse(raw)
    directory = ensure_dir()
    target = directory / safe_name(filename)
    temporary = directory / f".{target.name}.{uuid.uuid4().hex}.tmp"
    temporary.write_bytes(raw)
    os.replace(temporary, target)
    return {
        "file": target.name,
        "clients": len(clients),
        "refs": [client["ClientRef"] for client in clients],
        "bytes": len(raw),
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warnings": warnings,
    }


def list_files() -> list[dict]:
    """Every stored upload, in deterministic filename order, each marked valid or why not."""
    directory = upload_dir()
    if not directory.is_dir():
        return []
    out: list[dict] = []
    for item in sorted(directory.glob("*.json")):
        stat = item.stat()
        record: dict[str, Any] = {
            "file": item.name,
            "bytes": stat.st_size,
            "saved_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "valid": True,
            "clients": 0,
            "refs": [],
            "error": None,
        }
        try:
            clients, _ = parse(item.read_bytes())
            record["clients"] = len(clients)
            record["refs"] = [client["ClientRef"] for client in clients]
        except (ValueError, OSError) as error:
            record["valid"] = False
            record["error"] = str(error)
        out.append(record)
    return out


def delete(filename: str) -> bool:
    """Remove one stored upload. Returns whether a file was actually removed."""
    target = upload_dir() / safe_name(filename)
    if target.is_file():
        target.unlink()
        return True
    return False


def load_all() -> tuple[list[dict], list[str]]:
    """Every client across all stored uploads, plus a problem line per unusable file.

    Called by :func:`ingest.load_raw`. An unreadable upload degrades to a warning — it never stops
    the provided data from loading.
    """
    directory = upload_dir()
    clients: list[dict] = []
    problems: list[str] = []
    if not directory.is_dir():
        return clients, problems
    for item in sorted(directory.glob("*.json")):
        try:
            batch, warnings = parse(item.read_bytes())
        except (ValueError, OSError) as error:
            problems.append(f"{item.name}: {error}")
            continue
        problems.extend(f"{item.name}: {warning}" for warning in warnings)
        clients.extend(batch)
    return clients, problems
