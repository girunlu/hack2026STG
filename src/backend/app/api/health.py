"""F5 health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..domain import index
from ..external import llm
from ..i18n import resolve_lang

router = APIRouter(prefix="/api", tags=["F5"])


def get_lang(lang: str | None = None) -> str:
    """Get language from query parameter."""
    return resolve_lang(lang, None)


@router.get("/health")
def health(lang: str = Depends(get_lang)) -> dict:
    """Liveness plus the shape of what was loaded, so a missing data file is obvious."""
    dataset = index.get()
    report = dataset.integrity_report()
    return {
        "status": "ok",
        "lang": lang,
        "data_as_of": dataset.data_as_of(),
        "counts": report["counts"],
        "clients_without_risk_profile": report["clients_without_risk_profile"],
        "dangling_portfolio_refs": len(report["dangling_portfolio_refs"]),
        "engine_version": "0.1.0",
        # Whether the optional LLM renderer (R4, phrasing only) can run here. The UI offers it only
        # when it can, so a missing key shows as the deterministic template rather than an error.
        "llm_available": llm.available(),
        "llm_model": llm.model() if llm.available() else None,
    }
