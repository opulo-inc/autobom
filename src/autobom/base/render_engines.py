# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""Start/stop Docker render engines for local AutoBOM runs.

GitHub Actions manages containers in action.yaml; this module only runs locally.
"""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from .logger import Logger
from .socket_protocol import MCAD_SOCKET_PORT, ECAD_SOCKET_PORT

# Set to "1" to leave containers running after a local run (faster iteration).
KEEP_ENGINES_ENV = "AUTOBOM_KEEP_ENGINES"


def _ab_path() -> str:
    import autobom

    action_path = os.environ.get("GITHUB_ACTION_PATH")
    if action_path:
        return action_path
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(autobom.__file__))))


def _compose_file(ab_path: str) -> str:
    # Apple Silicon uses the local FreeCAD AppImage Dockerfile.
    if platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64"):
        candidate = os.path.join(ab_path, "docker-compose-local.yaml")
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(ab_path, "docker-compose.yaml")


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def engines_ready() -> bool:
    return _port_open(MCAD_SOCKET_PORT) and _port_open(ECAD_SOCKET_PORT)


def wait_for_engines(timeout_s: int = 360) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if engines_ready():
            Logger.info(
                f"Render engines ready on ports {MCAD_SOCKET_PORT} and {ECAD_SOCKET_PORT}"
            )
            return
        time.sleep(2)
    raise TimeoutError(
        f"Timed out waiting for render engines on ports "
        f"{MCAD_SOCKET_PORT} and {ECAD_SOCKET_PORT}. "
        "Check: docker compose -f <compose> logs"
    )


def _compose_cmd(ab_path: str, *args: str) -> list[str]:
    return ["docker", "compose", "-f", _compose_file(ab_path), *args]


def start_engines(ab_path: Optional[str] = None) -> None:
    ab_path = ab_path or _ab_path()
    compose = _compose_file(ab_path)
    Logger.info(f"Starting render engines ({compose})")
    subprocess.run(
        _compose_cmd(ab_path, "up", "-d", "--build"),
        cwd=ab_path,
        check=True,
    )
    wait_for_engines()


def stop_engines(ab_path: Optional[str] = None) -> None:
    ab_path = ab_path or _ab_path()
    Logger.info("Stopping render engines")
    subprocess.run(
        _compose_cmd(ab_path, "down"),
        cwd=ab_path,
        check=False,
    )


@contextmanager
def managed_render_engines() -> Iterator[None]:
    """Bring up render engines for local runs; no-op under GitHub Actions.

    If engines are already listening, they are left alone (not stopped afterward).
    Otherwise they are started and stopped when the context exits, unless
    AUTOBOM_KEEP_ENGINES=1.
    """
    if os.environ.get("GITHUB_ACTIONS"):
        # action.yaml owns the container lifecycle
        yield
        return

    started_by_us = False
    try:
        if engines_ready():
            Logger.info("Render engines already running; reusing them")
        else:
            start_engines()
            started_by_us = True
        yield
    finally:
        keep = os.environ.get(KEEP_ENGINES_ENV, "").strip() in ("1", "true", "yes")
        if started_by_us and not keep:
            stop_engines()
        elif started_by_us and keep:
            Logger.info(f"Leaving render engines up ({KEEP_ENGINES_ENV} set)")
