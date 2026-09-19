"""B2 — POST /api/qa — follow-up Q&A over the assembled facts bundle.

Deterministic, evidence-backed answers in German. Every answer is grounded in the
R2/R3 evidence bundle; if the data does not contain the answer, the response says
so explicitly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["B2"])


class QaRequest(BaseModel):
    """Request body for POST /api/qa."""
    client_ref: str
    question: str = Field(..., min_length=3)
    portfolio_nr: str | None = None
    lang: str = "en"


class QaEvidence(BaseModel):
    """One piece of evidence supporting an answer."""
    label: str
    value: float | str | None
    source: str
    path: str


class QaMatched(BaseModel):
    """Which findings and sections were used to answer the question."""
    findings: list[str]
    sections: list[str]


class QaSource(BaseModel):
    """One public web page an unrouteable question was answered from."""

    title: str | None = None
    url: str | None = None
    snippet: str | None = None


class QaResponse(BaseModel):
    """Response body for POST /api/qa."""

    answer: str
    answered_by: str = Field(
        default="rules",
        description="'llm' when the model phrased the answer from the client's own analysis, 'rules' "
                    "when the deterministic router did (no key, or the model declined)",
    )
    source_kind: str = Field(
        default="data",
        description="'data' when the answer comes from the client's facts, 'web' when the question "
                    "had no route there and public pages were used, 'none' when neither could answer",
    )
    sources: list[QaSource] = Field(
        default_factory=list,
        description="Public pages behind a 'web' answer — always present when source_kind is 'web'",
    )
    evidence: list[QaEvidence]
    unavailable: list[str]
    matched: QaMatched


@router.post("/qa", response_model=QaResponse)
def answer_question(request: QaRequest) -> QaResponse:
    """Answer a follow-up question from the assembled facts bundle.
    
    Returns a German answer with evidence, unavailable data, and matched findings/sections.
    """
    # Lazy import so a broken upstream stage cannot prevent the app from starting
    from ..compose import facts as facts_module
    from ..compose import qa as qa_module
    
    try:
        result = qa_module.answer(
            client_ref=request.client_ref,
            question=request.question,
            portfolio_nr=request.portfolio_nr,
            lang=request.lang
        )
    except facts_module.UnknownClient:
        raise HTTPException(
            status_code=404,
            detail=f"Unbekannter Klient: {request.client_ref}"
        )
    except facts_module.UnknownPortfolio:
        raise HTTPException(
            status_code=404,
            detail=f"Unbekanntes Portfolio {request.portfolio_nr} für {request.client_ref}"
        )
    
    return QaResponse(
        answer=result["answer"],
        answered_by=result.get("answered_by", "rules"),
        source_kind=result.get("source_kind", "data"),
        sources=[QaSource(**source) for source in result.get("sources") or []],
        evidence=[QaEvidence(**ev) for ev in result["evidence"]],
        unavailable=result["unavailable"],
        matched=QaMatched(**result["matched"])
    )
