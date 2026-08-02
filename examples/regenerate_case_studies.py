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

from argos_epistemic import (
    Budget,
    analyze_system,
    dense_semantic,
    dense_semantic_available,
    embedding_semantic,
    extract_system,
    lexical_semantic,
)

# Linker para casos tercerizados: denso si [semantic] disponible (discriminativo),
# si no léxico. Se evita el surrogate embedding_semantic (suelo ~0.5): sobre-enlaza
# artefactos irrelevantes (.gitignore -> 'memory') e infla coverage.
_TP_LINKER = dense_semantic if dense_semantic_available() else lexical_semantic
_TP_THRESHOLD = 0.60 if dense_semantic_available() else 0.10

ARGOS_GOAL = {
    "name": "refactorizacion",
    "aspects": ["algorithm", "config", "test", "doc"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
    # embedding_semantic (surrogate) SÍ discrimina a threshold alto (0.55): el
    # suelo ~0.5 queda por debajo y no enlaza ruido (.gitignore). Determinista y
    # sin torch -> CI reproducible. (Denso se reserva para casos tercerizados.)
    "aspect_linker": embedding_semantic,
    "link_threshold": 0.55,
}
MARKUPSAFE_GOAL = {
    "name": "seguridad-y-refactor",
    "aspects": ["escape", "native", "exception", "test", "config"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
    "aspect_linker": _TP_LINKER,
    "link_threshold": _TP_THRESHOLD,
}
ANKLA_GOAL = {
    "name": "auditoria-memoria",
    "aspects": ["memory", "write", "retrieval", "canonical", "test"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
    "aspect_linker": _TP_LINKER,
    "link_threshold": _TP_THRESHOLD,
}

# Casos tercerizados: se clonan shallow desde su origin público (reproducible,
# no dependen de un path local). Regenerados oportunamente (requieren red); el
# único caso enforced en CI es `argos` (autoestudio determinista).
THIRD_PARTY_CASES = {
    "markupsafe": {
        "repo": "https://github.com/pallets/markupsafe.git",
        "goal": MARKUPSAFE_GOAL,
        "notes": [
            "Independiente: analizador y analizado son proyectos distintos.",
            "L3 es simbólico best-effort (no ve C-extensions nativas); `S_semantic` "
            "es surrogate léxico.",
            "Sin L5 dinámico sobre terceros por defecto (confianza + dependencias de "
            "build); el extractor está disponible bajo `analyze_path(run_dynamic=True)`.",
        ],
    },
    "an-kla-memory": {
        "repo": "https://github.com/kristhianmanue1/an-kla-memory.git",
        "goal": ANKLA_GOAL,
        "notes": [
            "Independiente en repositorio, pero an-kla-memory es **dependencia del propio "
            "argos** (es la memoria local que usa este repo): no es totalmente ajeno.",
            "L4 aquí es particularmente informativo: la lib implementa gobernanza de "
            "escritura (write-policy) y canonicalización JSON, por eso muchas funciones "
            "levantan `ValueError` (validates) y el top de impacto L3 cae sobre "
            "`commit_write_plan`/`main` (path crítico de la escritura gobernada).",
            "L3/L4 simbólicos best-effort (Python AST); `S_semantic` surrogate léxico. "
            "Sin L5 dinámico sobre terceros por defecto.",
        ],
    },
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
    linker = goal.get("aspect_linker") or lexical_semantic
    system = extract_system(root, goal=goal, semantic_fn=linker)
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


def _third_party_md(slug: str, case: dict) -> str | None:
    import shutil

    dest = Path(tempfile.mkdtemp(prefix=f"{slug}-"))
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", case["repo"], str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return None
        head = subprocess.run(
            ["git", "-C", str(dest), "log", "-1", "--format=%h %an (%ad)"],
            capture_output=True, text=True,
        ).stdout.strip()
        system, report = _run(dest, case["goal"])
        cg = system.get("call_graph", {})
        bh = system.get("behavior", {})
        top = ", ".join(f"{n['id'].split('::')[-1]} ({n['impact']})" for n in cg.get("top_impact", [])[:4])
    finally:
        shutil.rmtree(dest, ignore_errors=True)
    goal = case["goal"]
    lines = [
        f"# Caso de estudio: {slug} (tercerizado)",
        "",
        "> Generado por `examples/regenerate_case_studies.py`. Validación "
        "**independiente** sobre un repo público. Fuente "
        f"`{case['repo']}`, " + (head or "HEAD") + ".",
        "",
        f"Objetivo `G={goal['name']}`, aspectos `{goal['aspects']}`.",
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
    ]
    lines += [f"- {note}" for note in case.get("notes", [])]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["argos", *THIRD_PARTY_CASES, "all"], default="all")
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
    for slug, case in THIRD_PARTY_CASES.items():
        if args.target in (slug, "all"):
            md = _third_party_md(slug, case)
            if md is not None:
                (ROOT / f"examples/case-study-{slug}.md").write_text(md, encoding="utf-8")
                print(f"wrote examples/case-study-{slug}.md")
            else:
                print(f"{slug} clone failed; left unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
