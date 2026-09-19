"""PDF upload — the brief's bonus challenge as an advisor would actually use it.

The brief asks the advisor to *upload a portfolio statement from another custodian as a PDF*
(L235–244), not to pick one of the samples. These assert the upload path produces the same artifact as
the picker (an ``EXT-*`` portfolio that behaves natively), that a stored upload can never escape its
directory, and that a file the reader cannot use is **refused** rather than imported as an empty
portfolio that would quietly distort the client's totals.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain import excustody, excustody_store, index

CLIENT = "CASE-041"
PROVIDED = "Quartalsreporting_Q4_2025_03_Familie_Weber_Brunner.pdf"


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    """A client whose uploads and imports land in temporary directories, never in the working copy."""
    monkeypatch.setenv("URO_EXCUSTODY_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("URO_EXCUSTODY_DIR", str(tmp_path / "store"))

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    for record in excustody_store.list_imported():
        excustody_store.delete(record["client_ref"], record["portfolio_nr"])
    index.load(force=True)


def _provided_pdf() -> bytes:
    return (excustody._SIDE_CHALLENGE_DIR / PROVIDED).read_bytes()


def test_an_uploaded_statement_becomes_a_native_portfolio(client: TestClient):
    """The advisor's own file, not one of the samples, must reach the analysis like any import."""
    before = len(index.get().portfolios)

    response = client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("depot-auszug-maerz.pdf", _provided_pdf(), "application/pdf")},
        data={"client_ref": CLIENT},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["portfolio_nr"].startswith("EXT-")
    assert body["report"]["file"] == "depot-auszug-maerz.pdf", "the advisor's filename is kept"
    assert body["positions"] > 0
    assert len(index.get().portfolios) == before + 1

    # It behaves like a natively held portfolio: the client's detail lists it as external.
    detail = client.get(f"/api/clients/{CLIENT}").json()
    imported = [p for p in detail["portfolios"] if p["nr"] == body["portfolio_nr"]]
    assert imported and imported[0]["is_external"] is True


def test_the_upload_joins_the_report_list(client: TestClient):
    client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("statement.pdf", _provided_pdf(), "application/pdf")},
        data={"client_ref": CLIENT},
    )
    reports = client.get("/api/import/reports").json()["reports"]
    uploaded = [report for report in reports if report["file"] == "statement.pdf"]
    assert uploaded and uploaded[0]["source"] == "upload"
    assert [report for report in reports if report["source"] == "side-challenge"]


def test_a_duplicate_upload_is_refused(client: TestClient):
    """Importing the same statement twice would count the same assets twice."""
    first = client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("statement.pdf", _provided_pdf(), "application/pdf")},
        data={"client_ref": CLIENT},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("statement.pdf", _provided_pdf(), "application/pdf")},
        data={"client_ref": CLIENT},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "already_imported"


def test_a_file_that_is_not_a_pdf_is_refused_with_a_reason(client: TestClient):
    response = client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
        data={"client_ref": CLIENT},
    )
    assert response.status_code == 400
    assert "PDF" in str(response.json()["detail"])


def test_a_pdf_that_cannot_be_read_is_refused_and_deleted(client: TestClient, tmp_path):
    """A damaged file must not leave a stored artifact behind, nor an empty portfolio."""
    before = len(index.get().portfolios)
    response = client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("broken.pdf", b"%PDF-1.4 not really a pdf", "application/pdf")},
        data={"client_ref": CLIENT},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unreadable_pdf"
    assert len(index.get().portfolios) == before
    assert not list(excustody.reports_dir().glob("*.pdf")), "the unusable file was not kept"


def test_the_stored_name_cannot_escape_the_upload_directory(client: TestClient):
    """A filename arriving from a browser chooses nothing about where the file lands."""
    response = client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("../../evil/../statement.pdf", _provided_pdf(), "application/pdf")},
        data={"client_ref": CLIENT},
    )
    assert response.status_code == 200, response.text
    stored = list(excustody.reports_dir().glob("*.pdf"))
    assert len(stored) == 1
    assert stored[0].parent == excustody.reports_dir()
    assert ".." not in stored[0].name


def test_an_unknown_client_is_refused(client: TestClient):
    response = client.post(
        "/api/import/ex-custody/upload",
        files={"file": ("statement.pdf", _provided_pdf(), "application/pdf")},
        data={"client_ref": "CASE-NOPE"},
    )
    assert response.status_code == 404


def test_the_picker_cannot_be_asked_for_a_path(client: TestClient):
    """``file`` now comes from a request: a path would read any file the process can read."""
    response = client.post(
        "/api/import/ex-custody",
        json={"file": "../../../etc/passwd", "client_ref": CLIENT},
    )
    assert response.status_code == 404
    assert "path" in str(response.json()["detail"])
