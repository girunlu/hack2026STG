"""B1 — Ex-custody report import API.

Provides endpoints to import foreign-bank portfolio statements (the 10
``Privatbank Helvetia AG`` PDFs) as virtual portfolios.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ..domain import excustody, excustody_store, index

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["B1"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class ImportRequest(BaseModel):
    """Request body for importing an ex-custody report."""

    file: str | None = Field(
        default=None,
        description="PDF filename (without path). If omitted, imports the first available report.",
        examples=["Quartalsreporting_Q4_2025_01_Herr_Max_Muster.pdf"],
    )
    client_ref: str | None = Field(
        default=None,
        description="Client to attach the imported portfolio to. Without it the portfolio is parsed but "
                    "not attached, so it cannot reach the analysis or the briefing.",
        examples=["CASE-028"],
    )


class ImportResponse(BaseModel):
    """Response after successfully importing an ex-custody report.

    ``portfolio`` is the F5 projection (PascalCase ``PortfolioNr`` / ``SecurityPositions`` /
    ``AccountPositions`` / ``DataGaps``). ``report`` is the parsed statement in its own shape —
    the snake_case view model the Fremdbanken panel renders (KPIs, positions, transactions,
    currency structure, data-quality notes).
    """

    portfolio_nr: str = Field(
        description="Generated portfolio number (e.g., EXT-001-01)",
        examples=["EXT-001-01"],
    )
    portfolio: dict[str, Any] = Field(
        description="Parsed portfolio data in the same shape as F5 portfolios",
    )
    report: dict[str, Any] = Field(
        description="The parsed statement in its own shape (snake_case view model for the panel)",
    )
    client_ref: str | None = Field(default=None, description="Client the portfolio was attached to")
    attached: bool = Field(default=False, description="Whether it joined the dataset and the briefing")
    positions: int = Field(default=0, description="Securities plus cash accounts")
    resolved_positions: int = Field(
        default=0,
        description="Positions that resolved to a SecurityId in the trimmed reference.json",
    )
    data_gaps: list[str] = Field(default_factory=list, description="Declared gaps, never invented")


class ReportListItem(BaseModel):
    """A single report in the list of available reports."""

    file: str = Field(description="PDF filename", examples=["Quartalsreporting_Q4_2025_01_Herr_Max_Muster.pdf"])
    name: str = Field(description="Human-readable client name", examples=["Herr Max Muster"])
    size: int = Field(description="File size in bytes", examples=[25435])
    pages: int = Field(description="Number of pages", examples=[8])
    source: str = Field(
        default="side-challenge",
        description="'side-challenge' for the ten provided statements, 'upload' for an uploaded PDF",
    )


class ReportsListResponse(BaseModel):
    """Response listing all available ex-custody reports."""

    reports: list[ReportListItem] = Field(description="List of available PDF reports")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _attach_import(parsed: dict, client_ref: str | None) -> ImportResponse:
    """Attach a parsed statement to a client and build the response.

    Shared by the report picker and the PDF upload so both produce the same artifact: same dedupe,
    same portfolio numbering, same declared gaps.
    """
    if client_ref and not index.get().client(client_ref):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown client {client_ref}")

    # Importing the same statement twice would count the same assets twice in the analysis and the
    # briefing; the advisor can delete the existing import first if they want to replace it.
    duplicate = excustody_store.find_duplicate(client_ref or "", parsed.get("file"))
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "already_imported",
                "portfolio_nr": duplicate["PortfolioNr"],
                "source_file": parsed.get("file"),
                "message": (
                    f"{duplicate['PortfolioNr']} was already imported from {parsed.get('file')}; "
                    "delete it before importing the same statement again"
                ),
            },
        )

    # A stable, collision-free number. The previous implementation derived it from Python's
    # randomised hash(), so the same PDF produced a different portfolio number on every restart.
    sequence = excustody_store.next_sequence(client_ref) if client_ref else 1
    portfolio = excustody_store.to_portfolio(parsed, client_ref or "UNATTACHED", sequence)

    if client_ref:
        excustody_store.save(client_ref, portfolio)
        index.load(force=True)
        logger.info("attached %s to %s", portfolio["PortfolioNr"], client_ref)

    securities = portfolio.get("SecurityPositions") or []
    accounts = portfolio.get("AccountPositions") or []
    return ImportResponse(
        portfolio_nr=portfolio["PortfolioNr"],
        portfolio=portfolio,
        report=parsed,
        client_ref=client_ref,
        attached=bool(client_ref),
        positions=len(securities) + len(accounts),
        resolved_positions=sum(1 for p in securities if p.get("SecurityId")),
        data_gaps=portfolio.get("DataGaps") or [],
    )


# A statement is a few dozen kilobytes; anything of this size is a mistake or an attack.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


@router.post("/ex-custody/upload", response_model=ImportResponse)
async def upload_ex_custody(
    file: UploadFile = File(..., description="The custodian's statement, as a PDF"),
    client_ref: str | None = Form(default=None, description="Client to attach the portfolio to"),
) -> ImportResponse:
    """Import a statement the advisor uploads — the brief's bonus challenge.

    The advisor uploads a PDF from another custodian rather than choosing one of the provided
    samples. It is parsed with the same reader, so it produces the same artifact: an ``EXT-*``
    portfolio, labelled ex-custody, with every gap declared.

    A statement the reader cannot make sense of is **refused** with what it did manage to read,
    instead of attaching an empty portfolio that would quietly distort the client's totals.
    """
    name = (file.filename or "").strip()
    content = await file.read()
    await file.close()

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    if not name.lower().endswith(".pdf") and content[:5] != b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF statements can be imported; this file is neither named .pdf nor a PDF.",
        )

    stored = excustody.save_upload(name, content)
    try:
        parsed = excustody.parse_report(stored)
    except Exception as error:
        excustody.delete_upload(stored)
        logger.warning("uploaded statement could not be read: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "unreadable_pdf",
                "message": (
                    "The file could not be read as a PDF — it may be damaged, password-protected or "
                    "not a PDF at all."
                ),
                "error": type(error).__name__,
            },
        )

    if not (parsed.get("positions") or []):
        gaps = list(parsed.get("gaps") or [])
        excustody.delete_upload(stored)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "no_positions",
                "message": (
                    "No positions could be read from this statement, so nothing was imported. The "
                    "prototype reads the Privatbank Helvetia template (Detailpositionen ledger on "
                    "pages 6-7); another layout needs its own extractor."
                ),
                "gaps": gaps,
            },
        )

    return _attach_import(parsed, (client_ref or "").strip() or None)


@router.post("/ex-custody", response_model=ImportResponse)
def import_ex_custody(request: ImportRequest) -> ImportResponse:
    """Import an ex-custody portfolio report.

    Parses the specified PDF (or the first available report if no file is specified)
    and returns a virtual portfolio in the same shape as F5 portfolios.

    The portfolio is labeled as ex-custody (``provenance: "ex_custody"``) and can be
    attached to a client in a later wave.

    Args:
        request: Import request with optional filename.

    Returns:
        Parsed portfolio with a generated portfolio number.

    Raises:
        HTTPException: 404 if the file is not found, 422 if parsing fails.
    """
    try:
        parsed = excustody.parse_default_or(request.file)
    except FileNotFoundError as e:
        logger.warning(f"Report not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {e}",
        )
    except ValueError as e:
        logger.error(f"Failed to parse report: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse report: {e}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error importing report: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to import report: {e}",
        )

    return _attach_import(parsed, (request.client_ref or "").strip() or None)


@router.get("/imported")
def list_imported() -> dict:
    """Every imported ex-custody portfolio, with the client it was attached to."""
    imported = excustody_store.list_imported()
    return {"imported": imported, "count": len(imported)}


@router.delete("/imported")
def clear_imported() -> dict:
    """Remove every imported ex-custody portfolio and reload the dataset.

    Imports persist under ``data/excustody/`` and survive ``POST /api/dataset/reload``, so this is the
    reset that returns the running process to the shipped 47-client / 57-portfolio demo state. The
    provided case data is never affected.
    """
    removed = excustody_store.clear()
    dataset = index.load(force=True)
    logger.info("cleared %s imported portfolio(s); dataset now holds %s portfolios", removed, len(dataset.portfolios))
    return {"removed": removed, "portfolios_total": len(dataset.portfolios)}


@router.delete("/imported/{portfolio_nr}")
def delete_imported(portfolio_nr: str, client_ref: str) -> dict:
    """Detach and remove an imported portfolio."""
    if not excustody_store.delete(client_ref, portfolio_nr):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No such import: {portfolio_nr}")
    dataset = index.load(force=True)
    return {"removed": portfolio_nr, "client_ref": client_ref, "portfolios_total": len(dataset.portfolios)}


@router.get("/reports", response_model=ReportsListResponse)
def list_reports() -> ReportsListResponse:
    """List all available ex-custody reports.

    Returns a list of the 10 ``Privatbank Helvetia AG`` PDFs in the side-challenge
    directory, sorted by filename.

    Returns:
        List of available reports with metadata.
    """
    try:
        reports = excustody.list_reports()
        return ReportsListResponse(reports=reports)
    except Exception as e:
        logger.exception(f"Failed to list reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list reports: {e}",
        )
