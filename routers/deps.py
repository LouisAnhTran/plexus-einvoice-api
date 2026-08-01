from fastapi import Header, HTTPException

from config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)):
    """Mirror the SMP Access Point's X-Api-Key auth.

    The MCP server holds this key; it never sees the database.
    """
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Key")
