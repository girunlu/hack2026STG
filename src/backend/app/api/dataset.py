"""Dataset ingestion API — accept additional client files at runtime.

This is the path the case README requires (*"accept new files of this shape rather than hardcoding
the one you have today"*) and the one the final presentation needs, since a previously unseen test
client may be supplied shortly before it.

Flow: upload -> validate -> persist under ``data/uploads/`` -> reload the dataset -> report exactly
what resolved and what did not. Uploads are merged by :func:`app.domain.ingest.load_raw`, so
``index.load(force=True)`` remains the single reload path and nothing else has to know about uploads.

Two entry points, same behaviour: a multipart upload for the UI file picker, and a raw-body variant
for scripts and the unseen-client drill (``curl --data-binary @newclients.json``).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ..domain import index, ingest, uploads
from ..domain.ingest import intnum, listof, text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dataset", tags=["F5", "ingestion"])

MAX_UNRESOLVED_REPORTED = 50


class UploadRecord(BaseModel):
    file: str
    bytes: int
    clients: int
    refs: list[str]
    saved_at: str
    valid: bool
    error: str | None = None


class UploadsResponse(BaseModel):
    directory: str
    files: list[UploadRecord]
    uploaded_clients: int
    load_warnings: list[str] = Field(default_factory=list)


class ImportClientsResponse(BaseModel):
    file: str
    clients_added: int
    refs: list[str]
    clients_total: int
    portfolios_total: int
    unresolved_positions: list[dict]
    warnings: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    deleted: str
    files_remaining: int
    clients_total: int


class ReloadResponse(BaseModel):
    clients_total: int
    portfolios_total: int
    securities_total: int
    data_as_of: str | None
    load_warnings: list[str] = Field(default_factory=list)


def _unresolved_positions(dataset, refs: list[str]) -> list[dict]:
    """Positions whose ``SecurityId`` is absent from the trimmed ``reference.json``.

    ``reference.json`` was trimmed to the rows the original 47 clients reference, so a new client may
    legitimately hold instruments we have no master row for. Those are reported, never dropped.
    """
    out: list[dict] = []
    for reference in refs:
        client = dataset.client(reference)
        if not client:
            continue
        for portfolio in listof(client, "Portfolios"):
            for position in listof(portfolio, "SecurityPositions"):
                security_id = intnum(position, "SecurityId", -1)
                if dataset.security(security_id) is not None:
                    continue
                out.append({
                    "client_ref": reference,
                    "portfolio_nr": text(portfolio, "PortfolioNr"),
                    "security_id": security_id,
                    "isin": text(position, "Isin") or None,
                    "name": text(position, "SecurityName") or None,
                    "reason": "SecurityId absent from reference.json (trimmed to the provided 47 clients)",
                })
                if len(out) >= MAX_UNRESOLVED_REPORTED:
                    return out
    return out


def _ingest(filename: str, raw: bytes) -> ImportClientsResponse:
    """Validate, persist, reload and report. Shared by both entry points."""
    if not raw:
        raise HTTPException(status_code=400, detail="empty upload")

    # Reject before persisting, so a bad file never reaches the loader.
    try:
        parsed, parse_warnings = uploads.parse(raw)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    dataset = index.get()
    clashes = [client["ClientRef"] for client in parsed if dataset.client(client["ClientRef"])]
    if clashes:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "ClientRef already exists in the provided data — refusing to override it",
                "clashing_refs": clashes,
            },
        )

    try:
        saved = uploads.save(filename, raw)
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    refreshed = index.load(force=True)
    refs = list(saved["refs"])
    unresolved = _unresolved_positions(refreshed, refs)

    warnings = list(saved["warnings"]) + list(parse_warnings) + list(ingest.LOAD_WARNINGS)
    gaps: list[str] = []
    if unresolved:
        gaps.append(
            f"{len(unresolved)} position(s) reference a security absent from reference.json — "
            "shown as unresolved rather than dropped"
        )

    logger.info("ingested %s: %d client(s) added", saved["file"], saved["clients"])
    return ImportClientsResponse(
        file=saved["file"],
        clients_added=saved["clients"],
        refs=refs,
        clients_total=len(refreshed.clients),
        portfolios_total=len(refreshed.portfolios),
        unresolved_positions=unresolved,
        warnings=sorted(set(warnings)),
        data_gaps=gaps,
    )


@router.post("/clients", response_model=ImportClientsResponse)
async def import_clients_multipart(file: UploadFile = File(..., description="A clients.json-shaped file")) -> ImportClientsResponse:
    """Import a client file chosen in the UI (multipart/form-data)."""
    raw = await file.read()
    return _ingest(file.filename or "clients.json", raw)


@router.post("/clients/json", response_model=ImportClientsResponse)
async def import_clients_raw(request: Request, filename: str = "clients.json") -> ImportClientsResponse:
    """Import a client file sent as a raw request body.

    The filename comes from the ``?filename=`` query parameter. Used by the unseen-client drill,
    where there is no browser:

        curl -X POST "http://127.0.0.1:8000/api/dataset/clients/json?filename=extra.json" \\
             -H "Content-Type: application/json" --data-binary @extra-clients.json
    """
    return _ingest(filename, await request.body())


@router.get("/uploads", response_model=UploadsResponse)
def list_uploads() -> UploadsResponse:
    """Every stored upload, including any that no longer parses."""
    files = uploads.list_files()
    return UploadsResponse(
        directory=str(uploads.upload_dir()),
        files=[UploadRecord(**record) for record in files],
        uploaded_clients=sum(record["clients"] for record in files if record["valid"]),
        load_warnings=list(ingest.LOAD_WARNINGS),
    )


@router.delete("/uploads/{filename}", response_model=DeleteResponse)
def delete_upload(filename: str) -> DeleteResponse:
    """Remove an uploaded client file and reload."""
    if not uploads.delete(filename):
        raise HTTPException(status_code=404, detail=f"no such upload: {filename}")
    refreshed = index.load(force=True)
    return DeleteResponse(
        deleted=uploads.safe_name(filename),
        files_remaining=len(uploads.list_files()),
        clients_total=len(refreshed.clients),
    )


@router.post("/reload", response_model=ReloadResponse)
def reload_dataset() -> ReloadResponse:
    """Force a reload of the dataset — provided files plus every upload."""
    dataset = index.load(force=True)
    return ReloadResponse(
        clients_total=len(dataset.clients),
        portfolios_total=len(dataset.portfolios),
        securities_total=len(dataset.securities),
        data_as_of=dataset.data_as_of(),
        load_warnings=list(ingest.LOAD_WARNINGS),
    )
