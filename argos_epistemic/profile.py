"""Extractor L5 (runtime): perfilado de rendimiento como evidencia de hotpaths.

§4 L5 ejecucion: un volcado de profiling (``cProfile``/``pstats``, ``*.prof``)
es evidencia runtime de que funciones consumen mas tiempo. Es de solo lectura y
barato; lee ficheros ``*.prof`` con ``pstats`` (formato estandar de CPython).
Verificacion **historica** (§9.1): confianza 0.8 cuando hay contenido.

Best-effort: ``pstats`` puede fallar si el volcado es de otra version/platforma;
en ese caso se devuelve None (sin trazar). No ejecuta codigo del sistema.
"""

from __future__ import annotations

import pstats
from pathlib import Path
from typing import Any

_PROF_SUFFIX = ".prof"
_MAX_FILES = 5
_TOP_N = 15


def _load_stats(path: Path) -> pstats.Stats | None:
    try:
        return pstats.Stats(str(path))
    except Exception:
        return None


def profile_summary(root: Path | str) -> dict[str, Any] | None:
    root_p = Path(root)
    collected: list[tuple[str, pstats.Stats]] = []
    for path in sorted(root_p.rglob(f"*{_PROF_SUFFIX}")):
        if any(part.lower() in (".venv", "venv", "__pycache__", ".git", "node_modules") for part in path.parts):
            continue
        stats = _load_stats(path)
        if stats is not None:
            collected.append((str(path.relative_to(root_p)), stats))
        if len(collected) >= _MAX_FILES:
            break
    if not collected:
        return None
    rel, stats = collected[0]
    total = getattr(stats, "total_tt", None)
    entries: list[dict[str, Any]] = []
    try:
        # sort by cumulative time; capture top hotpaths
        stats.sort_stats("cumulative")
        for func, (_cc, nc, tt, ct, _callers) in list(stats.stats.items())[:_TOP_N]:  # type: ignore[attr-defined]
            filename, lineno, name = func
            entries.append({
                "function": f"{Path(filename).name}:{lineno}:{name}",
                "cumulative": round(float(ct), 5),
                "total": round(float(tt), 5),
                "calls": int(nc),
            })
    except Exception:
        pass
    status = "supported" if total is not None else "weak"
    return {
        "status": status,
        "profile": rel,
        "files": len(collected),
        "total_tt": round(float(total), 5) if total is not None else None,
        "hotpaths": entries,
    }


def profile_artifact(root: Path | str, goal: dict[str, Any] | None = None) -> dict[str, Any] | None:
    summary = profile_summary(root)
    if summary is None:
        return None
    lines = [
        f"profile file={summary['profile']} total_tt={summary['total_tt']} "
        f"status={summary['status']}"
    ]
    for e in summary["hotpaths"]:
        lines.append(f"{e['cumulative']} cum {e['calls']}x {e['function']}")
    return {
        "id": "L5:profile",
        "content": "\n".join(lines),
        "location": "(profile)",
        "level": 5,
        "relevance": 0.6,
        "kind": "profile",
        "verification_method": "historical",
        "run": summary,
    }
