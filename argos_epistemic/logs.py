"""Extractor L5 (runtime): colas de logs como evidencia de comportamiento.

L5 ejecución/historia (§4): además de tests y git, los logs del sistema aportan
evidencia dinámica de errores, warnings y trazas. Es de solo lectura y barato;
leo los ``*.log`` del repo (desarrollo) acotados en tamaño. Verificación
``historical`` (§9.1): confianza 0.8 cuando hay contenido.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_LOG_SUFFIXES = (".log",)
_MAX_FILES = 10
_MAX_BYTES = 4096


def tail_logs(root: Path | str) -> dict[str, Any] | None:
    root = Path(root)
    collected: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if any(part.lower() in ("node_modules", ".git", ".venv", "__pycache__") for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in _LOG_SUFFIXES:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            collected.append((str(path.relative_to(root)), content[-_MAX_BYTES:]))
        if len(collected) >= _MAX_FILES:
            break
    if not collected:
        return None
    errors = sum(1 for _, c in collected if "error" in c.lower() or "traceback" in c.lower())
    status = "contradicted" if errors else "supported"
    return {"files": len(collected), "error_signals": errors, "status": status, "samples": collected}


def logs_artifact(root: Path | str, goal: dict[str, Any] | None = None) -> dict[str, Any] | None:
    summary = tail_logs(root)
    if summary is None:
        return None
    lines = [f"logs files={summary['files']} error_signals={summary['error_signals']} status={summary['status']}"]
    for rel, content in summary["samples"][:3]:
        lines.append(f"--- {rel} (tail) ---")
        lines.extend(content.splitlines()[-8:])
    return {
        "id": "L5:logs",
        "content": "\n".join(lines),
        "location": "(logs)",
        "level": 5,
        "relevance": 0.6,
        "kind": "logs",
        "verification_method": "historical",
        "run": summary,
    }
