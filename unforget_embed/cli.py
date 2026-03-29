"""CLI for unforget-embed — start/stop/status the embedded server."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import click
import httpx

DEFAULT_DATA_DIR = Path.home() / ".unforget" / "data"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9077
PID_FILE = Path.home() / ".unforget" / "daemon.pid"


def _get_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _is_running(port: int) -> bool:
    """Check if the server is running and healthy."""
    try:
        resp = httpx.get(f"{_get_url(port)}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


@click.group()
def main():
    """Unforget Embed — zero-config embedded memory server."""
    pass


@main.command()
@click.option("--data-dir", default=str(DEFAULT_DATA_DIR), help="Data directory")
@click.option("--host", default=DEFAULT_HOST, help="Bind host")
@click.option("--port", default=DEFAULT_PORT, type=int, help="Bind port")
@click.option("--foreground", is_flag=True, help="Run in foreground (don't daemonize)")
def start(data_dir: str, host: str, port: int, foreground: bool):
    """Start the embedded Unforget server."""
    if _is_running(port):
        click.echo(f"Server already running on {_get_url(port)}")
        return

    if foreground:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
        from unforget_embed.server import UnforgetEmbed

        server = UnforgetEmbed(data_dir=data_dir, host=host, port=port)
        click.echo(f"Starting Unforget Embed on {host}:{port}...")
        server.start()
    else:
        # Daemonize: spawn as background process
        click.echo(f"Starting Unforget Embed daemon on {host}:{port}...")

        proc = subprocess.Popen(
            [
                sys.executable, "-m", "unforget_embed.cli",
                "start", "--foreground",
                "--data-dir", data_dir,
                "--host", host,
                "--port", str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Save PID
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid))

        # Wait for server to be ready
        for i in range(30):
            if _is_running(port):
                click.echo(f"Server ready: {_get_url(port)}")
                return
            time.sleep(1)

        click.echo("Server failed to start within 30 seconds", err=True)
        sys.exit(1)


@main.command()
def stop():
    """Stop the embedded Unforget server."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            click.echo(f"Stopped server (PID {pid})")
        except ProcessLookupError:
            click.echo("Server was not running")
        PID_FILE.unlink(missing_ok=True)
    else:
        click.echo("No PID file found — server may not be running")


@main.command()
@click.option("--port", default=DEFAULT_PORT, type=int, help="Server port")
def status(port: int):
    """Check if the server is running."""
    if _is_running(port):
        click.echo(f"Running on {_get_url(port)}")

        # Show some stats
        try:
            resp = httpx.get(f"{_get_url(port)}/health", timeout=2)
            click.echo(json.dumps(resp.json(), indent=2))
        except Exception:
            pass
    else:
        click.echo("Not running")

        # Check if PID file exists but process is dead
        if PID_FILE.exists():
            click.echo("(stale PID file found — cleaning up)")
            PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
