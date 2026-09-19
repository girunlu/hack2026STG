"""UNRISKOMEGA prototype backend — FastAPI application.

Run from ``src/backend``::

    python -m uvicorn app.main:app --reload --port 8000

This is a standalone prototype. It is never deployed inside the live URO environment.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import briefing, clients, dataset, health, imports, market, qa
from .domain import index

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the dataset once. A missing or malformed file fails loudly here, not per request."""
    dataset = index.load(force=True)
    print(
        f"[F5] loaded {len(dataset.clients)} clients, {len(dataset.portfolios)} portfolios, "
        f"{len(dataset.securities)} securities — data_as_of={dataset.data_as_of()}"
    )
    yield


app = FastAPI(
    title="UNRISKOMEGA prototype backend",
    version="0.1.0",
    description="Mocked URO Advisor Pro backing services. Prototype only — never run against live URO.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(clients.router)
app.include_router(briefing.router)
app.include_router(imports.router)
app.include_router(market.router)
app.include_router(qa.router)
app.include_router(dataset.router)
