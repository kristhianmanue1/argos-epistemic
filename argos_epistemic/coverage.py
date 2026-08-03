"""Extractor L5 (ejecucion): cobertura de tests como evidencia de comportamiento.

§4 L5 ejecucion: ademas de tests/git/logs, el reporte de cobertura (p.ej.
``coverage run -m pytest && coverage xml``) es evidencia runtime de que codigo
ejercitan realmente las pruebas. Es de solo lectura y barato; lee ``coverage.xml``
(formato Cobertura estandar, portable entre lenguajes/herramientas). Verificacion
**historica** (§9.1): aporta confianza 0.8 cuando hay contenido.

No cuenta como evidencia productiva para el gate de ``production_sources_met``
(no es codigo del call graph): es medicion de comportamiento, no implementacion.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_XML_NAMES = ("coverage.xml",)


def _fnum(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def coverage_summary(root: Path | str) -> dict[str, Any] | None:
    root_p = Path(root)
    path = next((root_p / n for n in _XML_NAMES if (root_p / n).exists()), None)
    if path is None:
        return None
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return None
    cov = tree.getroot()
    if cov.tag != "coverage":
        return None
    total = _fnum(cov.get("line-rate"))
    per_file: dict[str, float] = {}
    for cls in cov.iter("class"):
        fn = cls.get("filename")
        if not fn:
            continue
        lr = _fnum(cls.get("line-rate"))
        if lr is not None:
            per_file[fn] = max(per_file.get(fn, 0.0), lr)
    covered = sum(1 for v in per_file.values() if v >= 0.8)
    status = "supported" if (total is not None and total >= 0.5) else "weak"
    top = dict(sorted(per_file.items(), key=lambda kv: kv[1], reverse=True)[:20])
    return {
        "status": status,
        "line_rate": total,
        "files": len(per_file),
        "covered_files": covered,
        "per_file": top,
    }


def coverage_artifact(root: Path | str, goal: dict[str, Any] | None = None) -> dict[str, Any] | None:
    summary = coverage_summary(root)
    if summary is None:
        return None
    lines = [
        f"coverage line_rate={summary['line_rate']} files={summary['files']} "
        f"covered(>=0.8)={summary['covered_files']} status={summary['status']}"
    ]
    for fn, lr in summary["per_file"].items():
        lines.append(f"{lr:.2f} {fn}")
    return {
        "id": "L5:coverage",
        "content": "\n".join(lines),
        "location": "(coverage)",
        "level": 5,
        "relevance": 0.8,
        "kind": "coverage",
        "verification_method": "historical",
        "run": summary,
    }
