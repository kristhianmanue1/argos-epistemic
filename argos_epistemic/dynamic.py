"""Extractor L5 (dinamico): ejecuta la suite de tests y captura evidencia.

A diferencia de los extractores L0-L4 (pura lectura), L5 **ejecuta** codigo del
sistema bajo analisis. Es opt-in (``analyze_path(run_dynamic=True)``) porque tiene
efectos secundarios y costo, y porque un agente no debe ejecutar codigo de
terceros sin considerar confianza y presupuesto (§9.1, verificacion dinamica).

La salida es un artefacto ``L5:pytest`` con ``verification_method="dynamic"``: la
confianza la fija el algoritmo al metodo (passing suite -> 0.9, ``supported``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_SUMMARY = re.compile(
    r"(\d+) passed(?:[,\s]+(\d+) failed)?(?:[,\s]+(\d+) errors)?(?:[,\s]+(\d+) skipped)?"
    r"(?:.*?in ([\d.]+)s)?"
)


def run_pytest(
    root: Path | str,
    timeout: int = 120,
    python: str | None = None,
) -> dict[str, Any]:
    root = Path(root)
    cmd = [
        python or sys.executable,
        "-m",
        "pytest",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        "--tb=line",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return {
            "status": "unavailable",
            "error": type(exc).__name__,
            "returncode": None,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "duration_s": None,
            "failures": [],
        }
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = _SUMMARY.search(out)
    passed = int(m.group(1)) if m and m.group(1) else 0
    failed = int(m.group(2)) if m and m.group(2) else 0
    errors = int(m.group(3)) if m and m.group(3) else 0
    duration = float(m.group(5)) if m and m.group(5) else None
    failures = [ln.strip() for ln in out.splitlines() if ln.startswith("FAILED")][:10]
    if proc.returncode == 0 and failed == 0 and errors == 0 and passed > 0:
        status = "supported"
    elif failed or errors:
        status = "contradicted"
    else:
        status = "weak"
    return {
        "status": status,
        "returncode": proc.returncode,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "duration_s": duration,
        "failures": failures,
    }


def dynamic_artifact(
    root: Path | str,
    goal: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any] | None:
    result = run_pytest(root, timeout=timeout)
    lines = [
        f"pytest rc={result['returncode']} passed={result['passed']} "
        f"failed={result['failed']} errors={result['errors']} status={result['status']}"
    ]
    if result.get("duration_s") is not None:
        lines.append(f"duration_s={result['duration_s']}")
    lines.extend(result.get("failures", []))
    return {
        "id": "L5:pytest",
        "content": "\n".join(lines),
        "location": "(dynamic)",
        "level": 5,
        "relevance": 0.85,
        "kind": "test-run",
        "verification_method": "dynamic",
        "run": result,
    }
