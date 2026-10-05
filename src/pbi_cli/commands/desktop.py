"""Power BI Desktop lifecycle commands (open, close, status)."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import click

from pbi_cli.core.output import print_error, print_info, print_json, print_success
from pbi_cli.main import PbiContext, pass_context


@click.group()
def desktop() -> None:
    """Manage the Power BI Desktop process lifecycle."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_processes(name: str) -> list[dict[str, str]]:
    """Return running processes matching *name* (e.g. ``PBIDesktop``)."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/fi", f"imagename eq {name}.exe", "/fo", "csv", "/nh"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    procs: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0]:
            procs.append({"name": parts[0], "pid": parts[1]})
    return procs


def _kill_all(*names: str) -> int:
    """Force-kill all processes matching any of *names*. Returns kill count."""
    killed = 0
    for name in names:
        for p in _list_processes(name):
            try:
                subprocess.run(
                    ["taskkill", "/f", "/pid", p["pid"]],
                    capture_output=True,
                    check=False,
                )
                killed += 1
            except Exception:
                pass
    return killed


def _snapshot_ports() -> set[int]:
    """Return the set of AS ports currently in use."""
    from pbi_cli.utils.platform import discover_pbi_port

    port = discover_pbi_port()
    return {port} if port else set()


def _poll_for_port(pre_existing: set[int], timeout: int = 120) -> int | None:
    """Wait for a NEW AS port to appear (not in *pre_existing*)."""
    from pbi_cli.utils.platform import discover_pbi_port

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        port = discover_pbi_port()
        if port and port not in pre_existing:
            return port
        time.sleep(3)
    return None


def _say(ctx: PbiContext, fn: Callable[[str], None], msg: str) -> None:
    """Print a human-readable message only when not in JSON mode."""
    if not ctx.json_output:
        fn(msg)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@desktop.command()
@click.argument("pbip_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--timeout", default=120, help="Max seconds to wait for AS engine port.")
@click.option(
    "--kill-existing",
    is_flag=True,
    help="Kill any existing PBI Desktop / msmdsrv instances first.",
)
@click.option("--no-connect", is_flag=True, help="Launch without auto-connecting pbi-cli.")
@click.option("--no-wait-model", is_flag=True, help="Don't wait for the model to be ready.")
@pass_context
def open(
    ctx: PbiContext,
    pbip_path: str,
    timeout: int,
    kill_existing: bool,
    no_connect: bool,
    no_wait_model: bool,
) -> None:
    """Launch Power BI Desktop with a .pbip file and connect.

    Auto-discovers the Analysis Services port and connects pbi-cli so
    subsequent commands (table, measure, dax, etc.) work immediately.
    """
    pbip = Path(pbip_path).resolve()

    if kill_existing:
        n = _kill_all("PBIDesktop", "msmdsrv")
        if n:
            _say(ctx, print_info, f"Killed {n} existing PBI Desktop / msmdsrv process(es)")
            time.sleep(3)

    existing_procs = _list_processes("PBIDesktop")
    if existing_procs and not kill_existing:
        print_error(
            f"Power BI Desktop is already running (PID {existing_procs[0]['pid']}).\n"
            "  Use --kill-existing to replace it, or 'pbi connect' to attach."
        )
        raise SystemExit(1)

    pre_ports = _snapshot_ports()

    _say(ctx, print_info, f"Launching {pbip.name}...")
    startfile = getattr(os, "startfile", None)  # Windows-only; absent on other platforms
    if startfile is None:
        print_error("`pbi desktop open` requires Windows (os.startfile is unavailable).")
        raise SystemExit(1)
    startfile(str(pbip))

    port = _poll_for_port(pre_ports, timeout=timeout)
    if port is None:
        print_error(f"Analysis Services engine did not start within {timeout}s")
        raise SystemExit(1)

    _say(ctx, print_success, f"AS port discovered: {port}")

    connected = False
    if not no_connect:
        from pbi_cli.core.session import connect as session_connect

        conn_deadline = time.monotonic() + 90
        while time.monotonic() < conn_deadline and not connected:
            try:
                session = session_connect(f"localhost:{port}")
                connected = True
            except Exception:
                time.sleep(5)

        if connected:
            from pbi_cli.core.connection_store import (
                ConnectionInfo,
                add_connection,
                load_connections,
                save_connections,
            )

            info = ConnectionInfo(
                name=session.connection_name,
                data_source=f"localhost:{port}",
                initial_catalog="",
            )
            store = load_connections()
            store = add_connection(store, info)
            save_connections(store)
            _say(ctx, print_success, f"Connected to localhost:{port}")
        else:
            print_error(f"Could not connect to localhost:{port} within 90s")

    if connected and not no_wait_model:
        _say(ctx, print_info, "Waiting for model...")
        ready = _wait_for_model(timeout=60)
        _say(
            ctx,
            print_success if ready else print_info,
            "Model ready" if ready else "Model not ready yet — proceeding anyway",
        )

    if ctx.json_output:
        print_json(
            {
                "status": "open",
                "pbipPath": str(pbip),
                "port": port,
                "connected": connected,
            }
        )


@desktop.command()
@click.option("--force", is_flag=True, help="Force-kill without graceful close.")
@pass_context
def close(ctx: PbiContext, force: bool) -> None:
    """Disconnect pbi-cli and close Power BI Desktop + msmdsrv."""
    try:
        from pbi_cli.core.session import disconnect as session_disconnect

        session_disconnect()
        _say(ctx, print_info, "Disconnected pbi-cli session")
    except Exception:
        pass

    names = ("PBIDesktop", "msmdsrv")
    if not force:
        for p in _list_processes("PBIDesktop"):
            try:
                subprocess.run(["taskkill", "/pid", p["pid"]], capture_output=True, check=False)
            except Exception:
                pass
        time.sleep(5)

    killed = _kill_all(*names)
    if killed:
        _say(ctx, print_success, f"Stopped {killed} PBI Desktop / msmdsrv process(es)")
    else:
        _say(ctx, print_info, "No PBI Desktop / msmdsrv processes found")

    if ctx.json_output:
        print_json({"status": "closed", "processesKilled": killed})


@desktop.command()
@pass_context
def status(ctx: PbiContext) -> None:
    """Show running Power BI Desktop processes and discovered ports."""
    from pbi_cli.utils.platform import discover_pbi_port

    pbi_procs = _list_processes("PBIDesktop")
    msm_procs = _list_processes("msmdsrv")
    port = discover_pbi_port()

    if ctx.json_output:
        print_json({"pbiDesktop": pbi_procs, "msmdsrv": msm_procs, "port": port})
        return

    if pbi_procs:
        for p in pbi_procs:
            print_success(f"PBIDesktop  PID {p['pid']}")
    else:
        print_info("PBIDesktop not running")

    if msm_procs:
        for p in msm_procs:
            print_success(f"msmdsrv     PID {p['pid']}")
    else:
        print_info("msmdsrv not running")

    if port:
        print_success(f"AS port: {port}")
    else:
        print_info("No AS port discovered")


# ---------------------------------------------------------------------------
# Internal: model-readiness poll
# ---------------------------------------------------------------------------


def _wait_for_model(timeout: int = 60) -> bool:
    """Poll until the connected model responds to ``table list``."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            from pbi_cli.core.session import get_session_for_command
            from pbi_cli.core.tom_backend import table_list

            session = get_session_for_command(PbiContext())
            if table_list(session.model):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False
