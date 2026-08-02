"""Aislamiento de subprocesos para extractores que ejecutan código (L5).

Los extractores L5 (``dynamic``, ``history``) lanzan subprocesos sobre el sistema
bajo análisis. Esto hardenece esa superficie:

* ``start_new_session=True``: el subproceso lidera su propio grupo, de modo que
  un timeout permite matar a toda su descendencia (no deja huérfanos).
* ``scrub_env``: elimina variables con credenciales antes de spawnear.
* aislamiento opcional (``isolation="strict"``): si hay ``firejail`` o
  ``bubblewrap`` disponibles, envuelve el comando para aislar red/sistema de
  archivos; si no, degrada a ``none`` y lo reporta en ``degradation``.
* ``RLIMIT_CPU``: techo de CPU del hijo como respaldo del timeout.

Esto NO equivale a un contenedor: el aislamiento real de red/filesystem
completo requiere un contenedor externo (Docker, firejail, bubblewrap). El
modo ``strict`` lo aprovecha cuando está presente; el modo por defecto
``none`` aplica sólo las medidas baratas (sesión + env scrub + CPU).
"""

from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any

_CREDENTIAL_HINTS = ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY", "PRIVATE_KEY")


def scrub_env(env: dict[str, str] | None = None) -> dict[str, str]:
    base = dict(env) if env is not None else dict(os.environ)
    for key in list(base):
        if any(hint in key.upper() for hint in _CREDENTIAL_HINTS):
            base.pop(key, None)
    return base


def _cpu_limit(seconds: int) -> None:
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
    except (ValueError, OSError):
        pass


def _wrap_isolation(cmd: list[str]) -> tuple[list[str], str | None]:
    if shutil.which("firejail"):
        return ["firejail", "--quiet", "--net=none", "--noprofile", "--", *cmd], "firejail"
    if shutil.which("bwrap"):
        return ["bwrap", "--unshare-net", "--die-with-parent", "--", *cmd], "bwrap"
    return cmd, None


def run_isolated(
    cmd: list[str],
    *,
    cwd: Path | str,
    timeout: int,
    env: dict[str, str] | None = None,
    isolation: str = "none",
    cpu_seconds: int | None = None,
) -> dict[str, Any]:
    """Run ``cmd`` with session isolation; kill the whole group on timeout.

    Returns dict with returncode/stdout/stderr/degradation/error. On timeout or
    missing binary, returncode is None and error is set.
    """
    runner_env = scrub_env(env)
    degradation: str | None = None
    final_cmd = cmd
    if isolation == "strict":
        final_cmd, wrapper = _wrap_isolation(cmd)
        if wrapper is None:
            degradation = "isolation_unavailable_no_firejail_or_bwrap"
    try:
        proc = subprocess.Popen(  # noqa: S603
            final_cmd,
            cwd=str(cwd),
            env=runner_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            preexec_fn=(lambda: _cpu_limit(cpu_seconds)) if cpu_seconds else None,
        )
    except FileNotFoundError as exc:
        return {"returncode": None, "stdout": "", "stderr": "", "degradation": degradation, "error": type(exc).__name__}
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.communicate()
        return {"returncode": None, "stdout": "", "stderr": "", "degradation": degradation, "error": "TimeoutExpired"}
    return {
        "returncode": proc.returncode,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "degradation": degradation,
        "error": None,
    }
