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


if __name__ == "__main__":
    # The container entrypoint. Going through config means EINVOICE_HOST and
    # EINVOICE_PORT actually take effect — a hardcoded `uvicorn --port` in the
    # Dockerfile CMD would silently ignore them.
    import uvicorn

    from config import settings

    uvicorn.run(app, host=settings.host, port=settings.port)
