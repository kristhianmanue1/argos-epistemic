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
import sys
from pathlib import Path
from typing import Any

_RUNNERS_BY_MANIFEST: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("package.json", "npm", ("npm", "test")),
    ("Cargo.toml", "cargo", ("cargo", "test", "--quiet")),
    ("go.mod", "go", ("go", "test", "./...")),
    ("Gemfile", "rspec", ("rspec", "--format", "progress")),
)


def detect_runner(root: Path | str) -> tuple[str, tuple[str, ...]]:
    """Pick a test command from manifests. Default is pytest (Python)."""
    root = Path(root)
    for manifest, label, cmd in _RUNNERS_BY_MANIFEST:
        if (root / manifest).exists():
            return label, cmd
    return "pytest", (sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "--tb=line")


def _parse_generic(out: str) -> dict[str, Any]:
    def first(pattern: str) -> int:
        m = re.search(pattern, out)
        return int(m.group(1)) if m else 0

    return {
        "passed": first(r"(\d+)\s+passed") or first(r"(\d+)\s+examples"),
        "failed": first(r"(\d+)\s+failed") or first(r"(\d+)\s+failures"),
        "errors": first(r"(\d+)\s+errors"),
        "duration_s": _parse_duration(out),
        "failures": [ln.strip() for ln in out.splitlines() if ln.startswith(("FAILED", "FAIL", "FAILURES"))][:10],
    }


def _parse_duration(out: str) -> float | None:
    m = re.search(r"in ([\d.]+)s", out)
    if m:
        return float(m.group(1))
    m = re.search(r"([\d.]+)s$", out.splitlines()[-1] if out.strip() else "")
    return float(m.group(1)) if m else None


def run_tests(
    root: Path | str,
    timeout: int = 120,
    *,
    runner: tuple[str, tuple[str, ...]] | None = None,
    env: dict[str, str] | None = None,
    isolation: str = "none",
) -> dict[str, Any]:
    """Run the project's test suite (detected by manifest). Best-effort parse.

    Verificación dinámica (§9.1): ``supported`` si rc==0 y hay señales de pase;
    ``contradicted`` si rc!=0; ``weak``/``unavailable`` según corresponda. El
    parseo de passed/failed es genérico (pytest/jest/cargo/go/rspec) y puede
    subreportar cuando el formato de salida difiere. Aislamiento vía
    ``sandbox.run_isolated`` (sesión + env scrub + PGKILL en timeout; ``strict``
    opcional con firejail/bwrap).
    """
    from .sandbox import run_isolated

    root = Path(root)
    label, cmd = runner or detect_runner(root)
    result = run_isolated(list(cmd), cwd=root, timeout=timeout, env=env, isolation=isolation, cpu_seconds=timeout + 5)
    if result["error"] in ("TimeoutExpired", "FileNotFoundError"):
        return {
            "runner": label,
            "status": "unavailable",
            "error": result["error"],
            "returncode": None,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "duration_s": None,
            "failures": [],
            "degradation": result.get("degradation"),
        }
    out = result["stdout"] + "\n" + result["stderr"]
    parsed = _parse_generic(out)
    if result["returncode"] == 0 and parsed["failed"] == 0 and parsed["errors"] == 0 and parsed["passed"] > 0:
        status = "supported"
    elif result["returncode"] != 0:
        status = "contradicted"
    else:
        status = "weak"
    return {
        "runner": label,
        "status": status,
        "returncode": result["returncode"],
        "degradation": result.get("degradation"),
        **parsed,
    }


def run_pytest(
    root: Path | str,
    timeout: int = 120,
    python: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible Python-only entry; delegates to run_tests."""
    cmd = (python or sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "--tb=line")
    return run_tests(root, timeout=timeout, runner=("pytest", cmd))


def dynamic_artifact(
    root: Path | str,
    goal: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any] | None:
    result = run_tests(root, timeout=timeout)
    lines = [
        f"runner={result['runner']} rc={result['returncode']} "
        f"passed={result['passed']} failed={result['failed']} "
        f"errors={result['errors']} status={result['status']}"
    ]
    if result.get("duration_s") is not None:
        lines.append(f"duration_s={result['duration_s']}")
    lines.extend(result.get("failures", []))
    return {
        "id": f"L5:{result['runner']}",
        "content": "\n".join(lines),
        "location": "(dynamic)",
        "level": 5,
        "relevance": 0.85,
        "kind": "test-run",
        "verification_method": "dynamic",
        "run": result,
    }
