"""Embedded PostgreSQL + Unforget API server.

Manages the lifecycle of an embedded PostgreSQL instance via pgbox
and runs the Unforget FastAPI server on top of it.
"""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pgbox import get_server

from unforget import MemoryStore
from unforget.api import create_memory_router

logger = logging.getLogger("unforget.embed")

DEFAULT_DATA_DIR = Path.home() / ".unforget" / "data"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9077


class UnforgetEmbed:
    """Manages embedded PostgreSQL + Unforget API server."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ):
        self.data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        self.host = host
        self.port = port
        self._pg = None
        self._store: MemoryStore | None = None

    @property
    def database_url(self) -> str | None:
        """Get the database URL from the embedded PostgreSQL instance."""
        if self._pg is None:
            return None
        return self._pg.get_uri()

    def _start_postgres(self) -> str:
        """Start embedded PostgreSQL and return the connection URI."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        pg_data = self.data_dir / "pgdata"

        logger.info("Starting embedded PostgreSQL at %s", pg_data)
        self._pg = get_server(str(pg_data), cleanup_mode="stop")

        db_uri = self._pg.get_uri()
        logger.info("PostgreSQL ready (port=%s, pid=%s)", self._pg.port, self._pg.pid)

        # Enable pgvector
        self._pg.enable_extension("vector")

        return db_uri

    def _create_app(self, db_uri: str) -> FastAPI:
        """Create the FastAPI app with Unforget memory router."""
        app = FastAPI(
            title="Unforget Embed",
            description="Zero-config embedded memory server",
            version="0.2.0",
        )

        @app.get("/health")
        async def health():
            return {
                "status": "ok",
                "database": "embedded",
                "postgres_version": "17.4",
                "pgvector_version": "0.8.0",
                "port": self._pg.port if self._pg else None,
            }

        app.state.db_uri = db_uri

        @app.on_event("startup")
        async def startup():
            store = MemoryStore(
                database_url=db_uri,
                max_writes_per_minute=100_000,
            )
            await store.initialize()
            app.state.store = store

            router = create_memory_router(store)
            app.include_router(router, prefix="/v1/memory")
            logger.info("Unforget API ready on http://%s:%d", self.host, self.port)

        @app.on_event("shutdown")
        async def shutdown():
            if hasattr(app.state, "store"):
                await app.state.store.close()

        return app

    def start(self):
        """Start the embedded server (blocking)."""
        db_uri = self._start_postgres()
        app = self._create_app(db_uri)

        def handle_signal(signum, frame):
            logger.info("Received signal %d, shutting down...", signum)
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        uvicorn.run(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )

    def stop(self):
        """Stop the embedded server and PostgreSQL."""
        if self._pg is not None:
            logger.info("Stopping embedded PostgreSQL...")
            self._pg.stop()
            self._pg = None
