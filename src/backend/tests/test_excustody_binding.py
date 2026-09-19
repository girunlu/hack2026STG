"""B1 — an imported ex-custody statement must behave like a native portfolio.

The brief requires the import to be *"include[d] in the portfolio analysis and 60-second briefing"*
and to *"behave like a portfolio already available in URO Advisor Pro"*. Parsing alone achieves
neither, so these assert the *binding*: attachment, visibility in the dataset, and reach into the
briefing. The parser has its own coverage.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain import excustody_store, index

REPORT = "Quartalsreporting_Q4_2025_01_Herr_Max_Muster.pdf"
CLIENT = "CASE-028"


@pytest.fixture()
def client() -> TestClient:
    """A client that leaves no imports behind — the Dataset is process-wide for the session."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    for record in excustody_store.list_imported():
        excustody_store.delete(record["client_ref"], record["portfolio_nr"])
    index.load(force=True)


def test_import_attaches_and_reaches_the_briefing(client: TestClient):
    before = len(index.get().portfolios)
    response = client.post("/api/import/ex-custody", json={"file": REPORT, "client_ref": CLIENT})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["attached"] is True
    assert body["positions"] > 0

    reference = body["portfolio_nr"]
    dataset = index.get()
    assert len(dataset.portfolios) == before + 1
    assert reference in [p["PortfolioNr"] for p in dataset.portfolios_of(CLIENT)]
    assert dataset.portfolio(CLIENT, reference) is not None

    briefing = client.post("/api/briefing", json={"client_ref": CLIENT, "lang": "en"}).json()
    assert reference in [p["nr"] for p in briefing["facts"]["portfolios"]]

    # The import screen renders the statement itself — positions with their PDF page, the currency
    # structure, transactions, the data-quality notes — while F3/F4/R2 consume the F5 projection. The
    # response must carry both, or the panel dereferences fields the F5 shape does not have and React
    # unmounts the whole app (the blank-page defect this test pins down).
    report = body["report"]
    for key in ("file", "client_name", "stichtag", "currency", "total_value", "positions",
                "position_count", "currency_structure", "transactions", "transaction_count",
                "isins_matched", "isins_unmatched", "gaps", "unavailable"):
        assert key in report, f"the parsed report must reach the panel: {key} missing"
    assert report["positions"], "the parsed statement must carry its positions"
    # The PDF page is what makes the panel a statement view rather than a portfolio view — the F5
    # projection has no such field.
    assert all("page" in position for position in report["positions"])
    assert body["portfolio"]["PortfolioNr"] == reference

    # It must be labelled as third-party *in the briefing*, and carry its provenance.
    imported_block = next(p for p in briefing["facts"]["portfolios"] if p["nr"] == reference)
    assert imported_block["is_external"] is True
    assert imported_block["provenance"] == "ex_custody"
    assert any("ex-custody portfolio" in gap for gap in imported_block["data_gaps"])


def test_the_same_statement_cannot_be_imported_twice(client: TestClient):
    """Importing one statement twice would count the same assets twice in the analysis."""
    first = client.post("/api/import/ex-custody", json={"file": REPORT, "client_ref": CLIENT})
    assert first.status_code == 200, first.text

    second = client.post("/api/import/ex-custody", json={"file": REPORT, "client_ref": CLIENT})
    assert second.status_code == 409, second.text
    detail = second.json()["detail"]
    assert detail["code"] == "already_imported"
    assert "already imported" in detail["message"]
    assert detail["portfolio_nr"] and detail["source_file"]

    # A different statement for the same client is still accepted.
    other = "Quartalsreporting_Q4_2025_02_Frau_Anna_Beispiel.pdf"
    third = client.post("/api/import/ex-custody", json={"file": other, "client_ref": CLIENT})
    assert third.status_code == 200, third.text


def test_import_without_a_client_parses_but_is_not_attached(client: TestClient):
    """No client means no attachment — and it must say so rather than silently looking bound."""
    before = len(index.get().portfolios)
    body = client.post("/api/import/ex-custody", json={"file": REPORT}).json()
    assert body["attached"] is False
    assert len(index.get().portfolios) == before


def test_unknown_client_is_refused(client: TestClient):
    response = client.post("/api/import/ex-custody", json={"file": REPORT, "client_ref": "CASE-NOPE"})
    assert response.status_code == 404


def test_delete_detaches_the_portfolio(client: TestClient):
    reference = client.post("/api/import/ex-custody",
                            json={"file": REPORT, "client_ref": CLIENT}).json()["portfolio_nr"]
    removed = client.delete(f"/api/import/imported/{reference}", params={"client_ref": CLIENT})
    assert removed.status_code == 200
    assert reference not in [p["PortfolioNr"] for p in index.get().portfolios_of(CLIENT)]


def test_imported_portfolio_ids_are_unique_across_clients():
    """Two clients' first imports must not share a PortfolioId.

    ``next_sequence`` is per client, so ``ID_BASE + sequence`` gave both ``EXT-028-01`` and
    ``EXT-022-01`` the id 900000001 (observed live), and ``index.portfolio_by_id`` resolves by id —
    a collision silently returns another client's portfolio.
    """
    from app.domain import excustody_store

    refs = ("CASE-028", "CASE-022", "DRILL-101", "SCEN-001")
    ids = [excustody_store.portfolio_id_for(ref, 1) for ref in refs]
    assert len(set(ids)) == len(refs), ids
    assert all(excustody_store.ID_BASE < i < 1_000_000_000 for i in ids), ids
    # Stable, because the value is persisted with the import; and distinct per sequence.
    assert excustody_store.portfolio_id_for("CASE-028", 1) == ids[0]
    assert excustody_store.portfolio_id_for("CASE-028", 2) != ids[0]
