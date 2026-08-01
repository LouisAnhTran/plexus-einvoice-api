import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from db import close_db, init_db  # noqa: E402
from routers import companies, health  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="E-Invoice Access Point API (dummy)",
    description=(
        "Stand-in for an InvoiceNow (Peppol) SMP Access Point. Exists so the "
        "e-invoice MCP server has a real HTTP API to call — the MCP server "
        "never touches this database directly."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(companies.router)
