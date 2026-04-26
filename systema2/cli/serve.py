"""`systema2 serve` command: run the FastAPI app (server mode)."""

from __future__ import annotations

import typer

from systema2.config import get_host, get_port


def serve(
    host: str = typer.Option(
        None, "--host", "-h", help="Bind host (defaults to $SYSTEMA2_HOST)."
    ),
    port: int = typer.Option(
        None, "--port", "-p", help="Bind port (defaults to $SYSTEMA2_PORT)."
    ),
    reload: bool = typer.Option(
        False, "--reload", help="Enable uvicorn auto-reload (dev)."
    ),
) -> None:
    """Run the systema2 FastAPI server."""
    import uvicorn

    uvicorn.run(
        "systema2.app:app",
        host=host or get_host(),
        port=port or get_port(),
        reload=reload,
    )
