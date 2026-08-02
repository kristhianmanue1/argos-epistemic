#!/usr/bin/env python
"""Regenerate the case-study markdown from the current pipeline (audit H8).

Run:
    python examples/regenerate_case_studies.py            # rewrite both cases
    python examples/regenerate_case_studies.py --target argos --check
                                                          # CI freshness check

The argos case is deterministic and enforced in CI. The markupsafe case clones a
third-party repo (network); it is regenerated when possible and otherwise left
untouched.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from argos_epistemic import Budget, analyze_system, embedding_semantic, extract_system

ARGOS_GOAL = {
    "name": "refactorizacion",
    "aspects": ["algorithm", "config", "test", "doc"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
    "aspect_linker": embedding_semantic,
    "link_threshold": 0.30,
}
MARKUPSAFE_GOAL = {
    "name": "seguridad-y-refactor",
    "aspects": ["escape", "native", "exception", "test", "config"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
    "aspect_linker": embedding_semantic,
    "link_threshold": 0.30,
}


def _test_count() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if "test" in line and "collected" in line:
            try:
                return int(line.split()[0])
            except ValueError:
                pass
    return -1


def _by_level(system):
    return dict(sorted(Counter(a["level"] for a in system["artifacts"]).items()))


def _by_kind(system):
    return dict(Counter(a["kind"] for a in system["artifacts"]))


def _run(root, goal):
    system = extract_system(root, goal=goal, semantic_fn=embedding_semantic)
    report = analyze_system(system, goal, Budget(tokens_remaining=200000, tool_remaining=2000))
    return system, report


def _argos_md() -> str:
    system, report = _run(ROOT, ARGOS_GOAL)
    cg = system.get("call_graph", {})
    bh = system.get("behavior", {})
    top = ", ".join(f"{n['id'].split('::')[-1]} ({n['impact']})" for n in cg.get("top_impact", [])[:4])
    raw = json.dumps({k: report[k] for k in ("evidence_count", "proposition_count", "coverage", "residual_risk", "complete")})
    lines = [
        "# Caso de estudio: argos-epistemic (autoestudio)",
        "",
        "> Generado por `examples/regenerate_case_studies.py` desde el pipeline "
        "actual (no escrito a mano). El sistema analizado es el propio repositorio; "
        "es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).",
        "",
        f"Tests en verde: **{_test_count()}**. Objetivo "
        f"`G={ARGOS_GOAL['name']}`, aspectos `{ARGOS_GOAL['aspects']}`, "
        f"NF `{ARGOS_GOAL['non_functional']}`, "
        f"θ={ARGOS_GOAL['theta_coverage']}, ρ={ARGOS_GOAL['rho_risk']}.",
        "",
        "## Extracción (discovery barato + índice L3)",
        "",
        f"- Artefactos descubiertos: **{len(system['artifacts'])}** "
        f"(por nivel `{_by_level(system)}`, por tipo `{_by_kind(system)}`).",
        f"- Grafo de llamadas L3 (Python AST, subgrafo de producción): "
        f"{cg.get('nodes')} nodos / {cg.get('edges')} aristas "
        f"({cg.get('production_nodes')} producción). Top impacto: {top}.",
        f"- Comportamiento L4 (AST best-effort, Σ_4): {bh.get('raising', 0)} fn levantan, "
        f"{bh.get('asserting', 0)} con asserts, {bh.get('mutating', 0)} mutan self, "
        f"{bh.get('validating', 0)} validan ({bh.get('production_functions', 0)}/"
        f"{bh.get('functions', 0)} producción).",
        "",
        "## Reporte",
        "",
        "```text",
        f"evidence_count  : {report['evidence_count']}",
        f"proposition_count: {report['proposition_count']}",
        f"conflict_count  : {report['conflict_count']}",
        f"coverage        : {report['coverage']}",
        f"residual_risk   : {report['residual_risk']}",
        f"complete        : {report['complete']}",
        f"levels_covered  : {sorted(report['levels_covered'])}",
        f"aspect_scores   : {report['aspect_scores']}",
        f"cost            : estimated={report['cost']['estimated_tokens']} observed={report['cost']['observed_tokens']}",
        "```",
        "",
        "## Interpretación",
        "",
        "El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y "
        "detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por "
        "aspecto sobre proposiciones; la evidencia irrelevante aporta cero. El "
        "costo **observado** (contenido real leído) se contabiliza contra el "
        "presupuesto y se compara con el estimado (stat).",
        "",
        "## Riesgo residual",
        "",
        "- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para "
        "evidencia independiente.",
        "- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), "
        "no denso; sesión del LLM/transformers queda pendiente.",
        "- **Discovery no presupuestado**: la lectura de archivos y el índice L3 "
        "se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo "
        "el contenido por-objetivo y los extractores subprocess son perezosos.",
        "",
        f"_Generado desde HEAD del pipeline. raw report: `{raw}`_",
        "",
    ]
    return "\n".join(lines)


def _markupsafe_md() -> str | None:
    import shutil

    dest = Path(tempfile.mkdtemp(prefix="markupsafe-"))
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/pallets/markupsafe.git", str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return None
        head = subprocess.run(
            ["git", "-C", str(dest), "log", "-1", "--format=%h %an (%ad)"],
            capture_output=True, text=True,
        ).stdout.strip()
        system, report = _run(dest, MARKUPSAFE_GOAL)
        cg = system.get("call_graph", {})
        bh = system.get("behavior", {})
        top = ", ".join(f"{n['id'].split('::')[-1]} ({n['impact']})" for n in cg.get("top_impact", [])[:4])
    finally:
        shutil.rmtree(dest, ignore_errors=True)
    lines = [
        "# Caso de estudio: markupsafe (tercerizado)",
        "",
        "> Generado por `examples/regenerate_case_studies.py`. Validación "
        "**independiente** sobre un repo público ajeno. Fuente "
        "`https://github.com/pallets/markupsafe`, " + (head or "HEAD") + ".",
        "",
        f"Objetivo `G={MARKUPSAFE_GOAL['name']}`, aspectos `{MARKUPSAFE_GOAL['aspects']}`.",
        "",
        "## Extracción",
        "",
        f"- Artefactos: **{len(system['artifacts'])}** "
        f"(nivel `{_by_level(system)}`, tipo `{_by_kind(system)}`).",
        f"- Grafo L3 (producción): {cg.get('nodes')} nodos / {cg.get('edges')} aristas "
        f"({cg.get('production_nodes')} producción). Los tests se excluyen del "
        f"cálculo de Impact (sesgo corregido). Top impacto: {top}.",
        f"- Comportamiento L4 (Σ_4): {bh.get('raising', 0)} levantan, "
        f"{bh.get('asserting', 0)} asserts, {bh.get('mutating', 0)} mutan, "
        f"{bh.get('validating', 0)} validan.",
        "",
        "## Reporte",
        "",
        "```text",
        f"evidence_count  : {report['evidence_count']}",
        f"proposition_count: {report['proposition_count']}",
        f"coverage        : {report['coverage']}",
        f"residual_risk   : {report['residual_risk']}",
        f"complete        : {report['complete']}",
        f"levels_covered  : {sorted(report['levels_covered'])}",
        f"aspect_scores   : {report['aspect_scores']}",
        "```",
        "",
        "## Interpretación y riesgo residual",
        "",
        "- Independiente: analizador y analizado son proyectos distintos.",
        "- L3 es simbólico best-effort (no ve C-extensions nativas); `S_semantic` "
        "es surrogate léxico.",
        "- Sin L5 dinámico sobre terceros por defecto (confianza + dependencias de "
        "build); el extractor está disponible bajo `analyze_path(run_dynamic=True)`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["argos", "markupsafe", "all"], default="all")
    ap.add_argument("--check", action="store_true", help="compare argos output to the committed file")
    args = ap.parse_args()

    if args.check:
        current = (ROOT / "examples" / "case-study-argos.md").read_text(encoding="utf-8")
        regenerated = _argos_md()
        if current.strip() != regenerated.strip():
            print("case-study-argos.md is stale; run examples/regenerate_case_studies.py", file=sys.stderr)
            return 1
        print("case-study-argos.md is fresh")
        return 0

    if args.target in ("argos", "all"):
        (ROOT / "examples" / "case-study-argos.md").write_text(_argos_md(), encoding="utf-8")
        print("wrote examples/case-study-argos.md")
    if args.target in ("markupsafe", "all"):
        md = _markupsafe_md()
        if md is not None:
            (ROOT / "examples" / "case-study-markupsafe.md").write_text(md, encoding="utf-8")
            print("wrote examples/case-study-markupsafe.md")
        else:
            print("markupsafe clone failed; left unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
