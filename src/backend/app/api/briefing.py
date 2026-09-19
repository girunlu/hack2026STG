"""``POST /api/briefing`` — R2 collects, R3 finds, R5 actions, R4 phrases.

Synchronous by design: the pipeline is deterministic and CPU-bound (plus one network call that is
cached for hours), so the stage timings the UI shows are measured, not simulated. ``meta.stages``
carries the duration and status of each stage, including stages that degraded to ``unavailable``.

Identical concurrent requests share one run (:func:`app.cache.single_flight`) and the finished result is
reused briefly: a React StrictMode remount, a language toggle or a page reload *during* a cold briefing
joined the same 60-second job before, and a reload right after it paid the cold path a second time.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..cache import single_flight
from ..compose import facts as facts_module
from ..compose import render as render_module
from ..i18n import t

router = APIRouter(prefix="/api", tags=["R2", "R3", "R4", "R5"])

# How long a finished briefing may be reused for the same question. Long enough to absorb a reload or a
# StrictMode remount, short enough that the advisor never reads a stale document; the dataset reload
# path clears it immediately, so an import or an upload is visible at once.
BRIEFING_TTL_SECONDS = 60.0


class BriefingRequest(BaseModel):
    client_ref: str
    portfolio_nr: str | None = None
    renderer: str = render_module.TEMPLATE
    lang: str = "en"


def _build(request: BriefingRequest) -> dict:
    """Run the pipeline once. Raises ``UnknownClient``/``UnknownPortfolio``/``ValueError``."""
    stages = facts_module.Stages(request.lang)
    bundle = facts_module.assemble(request.client_ref, request.portfolio_nr, stages, request.lang)

    stages.start("compose")
    try:
        rendered = render_module.render(bundle, request.renderer, request.lang)
    except ValueError as error:
        stages.finish("compose", "unavailable", str(error))
        raise
    stages.finish("compose", "ok", t("briefing.compose_note", request.lang,
                                     words=rendered["word_count"],
                                     seconds=rendered["read_seconds_estimate"]))

    bundle["meta"]["stages"] = stages.rows
    return {"facts": bundle, "briefing": rendered, "stages": stages.rows}


@router.post("/briefing")
def create_briefing(request: BriefingRequest) -> dict:
    """Assemble the facts bundle and render the briefing for one client (optionally one portfolio)."""
    key = "|".join((
        request.client_ref,
        request.portfolio_nr or "",
        request.renderer,
        request.lang,
    ))
    try:
        return single_flight(key, lambda: _build(request), ttl=BRIEFING_TTL_SECONDS)
    except facts_module.UnknownClient:
        raise HTTPException(status_code=404, detail=f"Unknown client {request.client_ref}")
    except facts_module.UnknownPortfolio:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown portfolio {request.portfolio_nr} for {request.client_ref}",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
