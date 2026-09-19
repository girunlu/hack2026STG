"""Client-file ingestion (README: *"accept new files of this shape... rather than hardcoding"*).

Covers the path the final presentation depends on: a previously unseen client file is uploaded,
merged, and flows through the whole pipeline to a briefing — plus the failure modes that must be
refused rather than half-applied.

Isolation: ``URO_UPLOAD_DIR`` points at a temporary directory for every test, and the dataset is
reloaded afterwards so no other test sees an uploaded client.
"""

from __future__ import annotations

import json
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.domain import index


@pytest.fixture()
def _isolated_uploads(monkeypatch, tmp_path):
    """Point the upload store at a temporary directory for the duration of one test."""
    monkeypatch.setenv("URO_UPLOAD_DIR", str(tmp_path))
    index.load(force=True)
    yield tmp_path
    # Restore the real dataset *after* unsetting the override, so later tests are unaffected.
    monkeypatch.delenv("URO_UPLOAD_DIR", raising=False)
    index.load(force=True)


@pytest.fixture()
def client(_isolated_uploads) -> Iterator[TestClient]:
    """A TestClient whose lifespan loads the dataset with the temporary upload store in place."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


# A real SAA id and a real SecurityId from the provided data, plus one deliberately unknown
# instrument — reference.json is trimmed to the original 47 clients, so new clients can hold
# securities we have no master row for.
KNOWN_SECURITY_ID = 5768
UNKNOWN_SECURITY_ID = 999_999_999


def _new_client(reference: str = "CASE-UP-01") -> dict:
    return {
        "ClientId": 990001,
        "ClientRef": reference,
        "FirstName": "Test",
        "LastName": "Upload",
        "IsClientACompany": False,
        "IsEmployee": False,
        "RegulatoryClientTypeId": 13,
        "RegulatoryClientTypeName": "Private client",
        "ReportingCurrency": "CHF",
        "RiskProfileId": 17,
        "RiskProfileName": "Anlageprofil 5",
        "EsgProfileId": 1,
        "EsgProfileName": "Yes",
        "Birthday": "1980-01-01",
        "ProfilingDateUtc": "2026-01-01T00:00:00+01:00",
        "AssetsUnderManagementInDefaultCurrency": 100000.0,
        "LiquidityInDefaultCurrency": 5000.0,
        "Portfolios": [{
            "PortfolioId": 9900011,
            "PublicGuid": "00000000-0000-0000-0000-0000000000UP",
            "PortfolioNr": f"{reference}-01",
            "Name": "Test Depot",
            "PortfolioCurrency": "CHF",
            "StrategicAssetAllocationId": 92,
            "InvestmentServiceId": 12,
            "InvestmentServiceName": "Individual Pension - Depository Advisory",
            "StrategyId": 5,
            "StrategyName": "Investor profile 5",
            "ReferenceCurrency": "CHF",
            "AssetsUnderManagementInDefaultCurrency": 100000.0,
            "LiquidityInDefaultCurrency": 5000.0,
            "Volatility": 0.05,
            "ExpectedReturn": 0.03,
            "ValueAtRisk": 0.01,
            "FactoryDateUtc": "2026-09-01T00:00:00Z",
            "SecurityPositions": [
                {"SecurityId": KNOWN_SECURITY_ID, "Isin": "CH0469273541", "Valor": "46927354",
                 "SecurityName": "known bond", "Quantity": 10, "PricePerUnit": 100.0,
                 "Currency": "CHF", "TotalAmountInPortfolioCurrency": 95000.0,
                 "PortfolioValuePercentage": 0.95, "MarginalContributionToRisk": 0.0,
                 "ContributionVolatility": 0.0},
                {"SecurityId": UNKNOWN_SECURITY_ID, "Isin": "XX0000000000",
                 "SecurityName": "unknown instrument", "Quantity": 1, "PricePerUnit": 100.0,
                 "Currency": "CHF", "TotalAmountInPortfolioCurrency": 5000.0,
                 "PortfolioValuePercentage": 0.05},
            ],
            "AccountPositions": [],
            "PerformanceHistory": [
                {"Date": "2026-04-01", "Value": 97000.0},
                {"Date": "2026-05-01", "Value": 98000.0},
                {"Date": "2026-06-01", "Value": 99000.0},
                {"Date": "2026-07-01", "Value": 100000.0},
            ],
        }],
        "Proposals": [], "Transactions": [], "SuitabilityViolations": [],
        "IndividualRuleOverrides": [], "ClientNotes": [], "Tags": [],
    }


def _upload(client: TestClient, payload, filename: str = "new-clients.json"):
    body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return client.post("/api/dataset/clients",
                       files={"file": (filename, body, "application/json")})


def test_uploaded_client_flows_all_the_way_to_a_briefing(client: TestClient):
    """The point of the feature: a new file becomes a briefing with no code change."""
    before = client.get("/api/clients").json()["counts"]["clients"]

    response = _upload(client, [_new_client()])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["clients_added"] == 1
    assert body["refs"] == ["CASE-UP-01"]
    assert body["clients_total"] == before + 1

    # it is a first-class client
    rows = {row["ref"] for row in client.get("/api/clients").json()["rows"]}
    assert "CASE-UP-01" in rows
    assert client.get("/api/clients/CASE-UP-01").status_code == 200
    assert client.get("/api/clients/CASE-UP-01/portfolios/CASE-UP-01-01").status_code == 200

    # and the whole pipeline runs for it
    briefing = client.post("/api/briefing", json={"client_ref": "CASE-UP-01"})
    assert briefing.status_code == 200, briefing.text
    sections = [s["id"] for s in briefing.json()["briefing"]["sections"]]
    assert sections == ["recent_development", "health_check", "outlook_actions"]


def test_unknown_instrument_is_reported_not_dropped(client: TestClient):
    """reference.json is trimmed, so a new client may hold securities we have no row for."""
    body = _upload(client, [_new_client()]).json()
    unresolved = body["unresolved_positions"]
    assert [u["security_id"] for u in unresolved] == [UNKNOWN_SECURITY_ID]
    assert unresolved[0]["isin"] == "XX0000000000"
    assert body["data_gaps"], "an unresolved position must surface as a declared gap"
    # the resolved position still resolves
    portfolio = client.get("/api/clients/CASE-UP-01/portfolios/CASE-UP-01-01").json()
    assert any(p["security_id"] == KNOWN_SECURITY_ID for p in portfolio["positions"])


def test_colliding_client_ref_is_refused(client: TestClient):
    """An upload must never quietly override provided case data."""
    response = _upload(client, [_new_client("CASE-001")])
    assert response.status_code == 409
    assert "CASE-001" in json.dumps(response.json())
    # and the provided data is untouched
    assert client.get("/api/clients/CASE-001").json()["client"]["ref"] == "CASE-001"


@pytest.mark.parametrize("payload", ["{not json", "[]", json.dumps([{"FirstName": "no ref"}])])
def test_malformed_uploads_are_rejected(client: TestClient, payload: str):
    assert _upload(client, payload).status_code == 400


def test_delete_removes_the_client_again(client: TestClient):
    before = client.get("/api/clients").json()["counts"]["clients"]
    _upload(client, [_new_client()], filename="to-remove.json")
    assert client.get("/api/clients").json()["counts"]["clients"] == before + 1

    deleted = client.delete("/api/dataset/uploads/to-remove.json")
    assert deleted.status_code == 200
    assert deleted.json()["clients_total"] == before
    assert client.get("/api/clients/CASE-UP-01").status_code == 404
    assert client.delete("/api/dataset/uploads/to-remove.json").status_code == 404


def test_uploads_can_be_listed_with_their_contents(client: TestClient):
    _upload(client, [_new_client()], filename="listed.json")
    body = client.get("/api/dataset/uploads").json()
    listed = {f["file"]: f for f in body["files"]}
    assert listed["listed.json"]["valid"] is True
    assert listed["listed.json"]["refs"] == ["CASE-UP-01"]
    assert body["uploaded_clients"] == 1


def test_raw_body_upload_for_scripted_drills(client: TestClient):
    """The unseen-client drill runs from a shell, with no browser."""
    response = client.post("/api/dataset/clients/json?filename=drill.json",
                           content=json.dumps([_new_client()]).encode("utf-8"),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 200, response.text
    assert response.json()["refs"] == ["CASE-UP-01"]
