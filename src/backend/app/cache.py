"""Single-flight and a short-lived result cache for expensive, deterministic computations.

The briefing pipeline is the prototype's slow path (a cold market fetch dominates; every other stage is
milliseconds). Two real problems come from running it more than once for the same question:

* a React StrictMode remount or a page reload *mid-generation* issues a second identical request while
  the first is still running, so the advisor waits for the same answer twice over;
* a reload *after* the first answer landed pays the cold path again.

:func:`single_flight` joins concurrent callers onto one computation and keeps the finished result for
``ttl`` seconds. A failing computation is never cached and never blocks a retry. The dataset reload path
calls :func:`invalidate`, so a changed dataset can never serve a stale briefing.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

# Keep the table small and bounded: entries are keyed by (client, portfolio, language, renderer) and a
# dataset reload clears them anyway.
MAX_ENTRIES = 256

_LOCK = threading.Lock()
_INFLIGHT: dict[str, threading.Event] = {}
_RESULTS: dict[str, tuple[float, Any]] = {}


def invalidate() -> None:
    """Drop every cached result. Called whenever the dataset underneath is reloaded."""
    with _LOCK:
        _RESULTS.clear()


def single_flight(key: str, produce: Callable[[], Any], ttl: float = 60.0) -> Any:
    """Compute ``produce()`` once per ``key``; concurrent callers receive the same result.

    ``ttl`` bounds how long a finished result is reused. The producer's exception reaches the caller
    that ran it, and waiters simply become producers themselves — a failure is never cached.
    """
    while True:
        with _LOCK:
            cached = _RESULTS.get(key)
            if cached is not None and (time.monotonic() - cached[0]) < ttl:
                return cached[1]
            event = _INFLIGHT.get(key)
            owner = event is None
            if owner:
                event = threading.Event()
                _INFLIGHT[key] = event
        if owner:
            break
        # Someone else is producing this exact result: wait, then re-read the cache (or take over if
        # that attempt failed and left nothing behind).
        event.wait(timeout=ttl + 30)

    try:
        result = produce()
    except BaseException:
        with _LOCK:
            _INFLIGHT.pop(key, None)
            event.set()
        raise

    with _LOCK:
        if len(_RESULTS) >= MAX_ENTRIES:
            _RESULTS.clear()
        _RESULTS[key] = (time.monotonic(), result)
        _INFLIGHT.pop(key, None)
        event.set()
    return result
