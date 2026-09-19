"""Minimal ``.env`` loader — no dependency, no surprises.

The optional integrations (currently the R4 LLM pass) need a secret that must not live in the repo, and
the prototype must still start with no ``.env`` at all. This reads one file, ``.env`` at the repository
root, into ``os.environ`` **without ever overriding a variable that is already set** — a real environment
variable always wins, so a container or a shell export is never silently replaced by a stale file.

Deliberately small: ``KEY=value`` per line, ``#`` comments, an optional ``export`` prefix, single or
double quotes around the value. Anything it cannot parse is skipped rather than raising, because a
malformed line in a local file must not prevent the server from booting.
"""

from __future__ import annotations

import os
from pathlib import Path

# src/backend/app/env.py -> parents[3] is the repository root (D:/hack26)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"

# Parsed once per process; the file is a developer convenience, not runtime state.
_loaded = False


def env_file() -> Path:
    """The file this module reads, so a help message can name the exact path."""
    return _ENV_FILE


def _parse(line: str) -> tuple[str, str] | None:
    """``KEY=value`` or ``None`` when the line carries nothing usable."""
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export "):].lstrip()
    if "=" not in text:
        return None
    key, _, value = text.partition("=")
    key = key.strip()
    if not key or not key.replace("_", "").isalnum():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return key, value


def load(force: bool = False) -> dict[str, str]:
    """Load ``.env`` into the process environment. Returns what was newly set.

    Idempotent: the file is read once per process unless ``force`` is set. Missing file, unreadable
    file and unparsable lines are all non-events.
    """
    global _loaded
    if _loaded and not force:
        return {}
    _loaded = True

    try:
        raw = _ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        return {}

    applied: dict[str, str] = {}
    for line in raw.splitlines():
        parsed = _parse(line)
        if parsed is None:
            continue
        key, value = parsed
        if not value or key in os.environ:
            continue
        os.environ[key] = value
        applied[key] = value
    return applied
