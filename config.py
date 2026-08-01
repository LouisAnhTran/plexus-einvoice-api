from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings are env-driven so this service can be deployed on its own.

    Every field maps to an EINVOICE_-prefixed environment variable, e.g.
    `auto_advance_seconds` <- EINVOICE_AUTO_ADVANCE_SECONDS. Real environment
    variables take precedence over the .env file, so a container platform can
    inject them without the file being present at all.
    """

    # SQLite is a library inside this process, not a server — there is nothing
    # to host and no port to connect to. ":memory:" keeps everything in RAM and
    # wipes it on shutdown, which is what we want for a dummy: no file to clean
    # up, no volume to mount when deployed. Point at a path like
    # "einvoice.db" or "/data/einvoice.db" if you ever want it to survive
    # restarts.
    database_path: str = ":memory:"

    # Callers authenticate with this value in the X-Api-Key header, mirroring
    # the real SMP Access Point API. The MCP server holds it; it never gets a
    # database credential.
    api_key: str = "dev-smp-key"

    # Seconds a company sits in each pending state before the network
    # "accepts" it. The real network takes minutes to hours; this keeps the
    # shape without the wait.
    auto_advance_seconds: int = 30

    class Config:
        env_file = ".env"
        env_prefix = "EINVOICE_"
        extra = "ignore"


settings = Settings()
