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

from argos_epistemic import (  # noqa: E402
    Budget,
    analyze_system,
    dense_semantic,
    embedding_semantic,
    extract_system,
    lexical_semantic,
)

SEMANTIC_PROFILES = {
    "lexical-v1": (lexical_semantic, 0.10),
    "char-ngram-v1": (embedding_semantic, 0.55),
    "minilm-v1": (dense_semantic, 0.60),
}


def semantic_profile(name: str):
    linker, threshold = SEMANTIC_PROFILES[name]
    if linker is None:
        raise RuntimeError(f"semantic profile unavailable: {name}")
    return linker, threshold


def configured_goal(base: dict, profile: str) -> dict:
    linker, threshold = semantic_profile(profile)
    return {**base, "aspect_linker": linker, "link_threshold": threshold}

ARGOS_GOAL = {
    "name": "refactorizacion",
    "aspects": ["algorithm", "config", "test", "doc"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
}
MARKUPSAFE_GOAL = {
    "name": "seguridad-y-refactor",
    "aspects": ["escape", "native", "exception", "test", "config"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
}
ANKLA_GOAL = {
    "name": "auditoria-memoria",
    "aspects": ["memory", "write", "retrieval", "canonical", "test"],
    "non_functional": ["sec"],
    "theta_coverage": 0.8,
    "rho_risk": 0.25,
}

# Casos tercerizados: se clonan shallow desde su origin público (reproducible,
# no dependen de un path local). Regenerados oportunamente (requieren red); el
# único caso enforced en CI es `argos` (autoestudio determinista).
THIRD_PARTY_CASES = {
    "markupsafe": {
        "repo": "https://github.com/pallets/markupsafe.git",
        "goal": MARKUPSAFE_GOAL,
        "semantic_profile": "minilm-v1",
        "independence_class": "independent",
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
        "semantic_profile": "minilm-v1",
        "independence_class": "operational_dependency",
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


def _inventory_summary(system):
    inventory = system.get("inventory", {})
    fields = (
        "profile",
        "files_discovered",
        "files_eligible",
        "files_selected",
        "files_omitted_by_cap",
        "read_truncations",
        "bytes_discovered",
        "bytes_read",
        "degradations",
        "fingerprint",
    )
    return {field: inventory.get(field) for field in fields}


def _run(root, goal, extra_ignores=None, normalize_freshness=False):
    linker = goal["aspect_linker"]
    system = extract_system(root, goal=goal, semantic_fn=linker, extra_ignores=extra_ignores)
    if normalize_freshness:
        for artifact in system["artifacts"]:
            artifact["freshness"] = 1.0
            artifact["timestamp"] = 0
    report = analyze_system(system, goal, Budget(tokens_remaining=200000, tool_remaining=2000))
    return system, report


_OUTPUT_PREFIXES = ("case-study-", "reporte-tecnico-", "plan-mejoras-")
_OUTPUT_NAMES = {"an-kla-memory-response-to-issue10.md"}


def self_study_output_names(root: Path = ROOT) -> set[str]:
    examples = root / "examples"
    if not examples.is_dir():
        return set()
    return {
        path.name
        for path in examples.iterdir()
        if path.is_file()
        and (path.name in _OUTPUT_NAMES or path.name.startswith(_OUTPUT_PREFIXES))
    }


def git_identity(root: Path) -> dict[str, str | bool]:
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip())
    return {"revision": revision, "dirty": dirty}


def _argos_md(profile: str = "char-ngram-v1") -> str:
    goal = configured_goal(ARGOS_GOAL, profile)
    system, report = _run(
        ROOT,
        goal,
        extra_ignores=self_study_output_names(),
        normalize_freshness=True,
    )
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
        f"`G={goal['name']}`, aspectos `{goal['aspects']}`, "
        f"NF `{goal['non_functional']}`, "
        f"θ={goal['theta_coverage']}, ρ={goal['rho_risk']}. Perfil semántico "  # noqa: RUF001
        f"explícito: `{profile}`.",
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
        f"inventory       : {_inventory_summary(system)}",
        f"completion      : {report.get('completion', {})}",
        "```",
        "",
        "## Interpretación",
        "",
        "El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y "
        "detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por "  # noqa: RUF001
        "aspecto sobre proposiciones; la evidencia irrelevante aporta cero. El "
        "costo **observado** (contenido real leído) se contabiliza contra el "
        "presupuesto y se compara con el estimado (stat).",
        "",
        "## Riesgo residual",
        "",
        "- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para "
        "evidencia independiente.",
        "- **Identidad Git no incrustada**: incluir el commit del propio archivo "
        "generado crearía una autorreferencia imposible de estabilizar. La identidad "
        "del evaluador pertenecerá al manifest externo del bundle.",
        "- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), "
        "no denso; sesión del LLM/transformers queda pendiente.",
        "- **Discovery no presupuestado**: la lectura de archivos y el índice L3 "
        "se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo "
        "el contenido por-objetivo y los extractores subprocess son perezosos.",
        "- **Frescura normalizada**: este artefacto fija `freshness=1.0` y "
        "`timestamp=0` para no depender del `mtime` asignado por cada checkout; "
        "el pipeline normal conserva y evalúa los timestamps reales.",
        "",
        f"_Generado desde HEAD del pipeline. raw report: `{raw}`_",
        "",
    ]
    return "\n".join(lines)


def _third_party_md(slug: str, case: dict, profile_override: str | None = None) -> str | None:
    import shutil

    dest = Path(tempfile.mkdtemp(prefix=f"{slug}-"))
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", case["repo"], str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return None
        identity = git_identity(dest)
        profile = profile_override or case["semantic_profile"]
        goal = configured_goal(case["goal"], profile)
        system, report = _run(dest, goal)
        cg = system.get("call_graph", {})
        bh = system.get("behavior", {})
        top = ", ".join(f"{n['id'].split('::')[-1]} ({n['impact']})" for n in cg.get("top_impact", [])[:4])
    finally:
        shutil.rmtree(dest, ignore_errors=True)
    independence_class = case["independence_class"]
    relationship = {
        "independent": "repositorios distintos sin dependencia operativa declarada",
        "operational_dependency": "repositorios distintos con dependencia operativa declarada",
    }[independence_class]
    lines = [
        f"# Caso de estudio: {slug} (tercerizado)",
        "",
        "> Generado por `examples/regenerate_case_studies.py`. Evaluación cruzada "
        f"entre {relationship}. Fuente `{case['repo']}`, revisión completa "
        f"`{identity['revision']}`, dirty=`{str(identity['dirty']).lower()}`.",
        "",
        f"Objetivo `G={goal['name']}`, aspectos `{goal['aspects']}`. "
        f"`independence_class={independence_class}`, perfil semántico explícito "
        f"`{profile}`.",
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
    ap.add_argument("--semantic-profile", choices=sorted(SEMANTIC_PROFILES))
    ap.add_argument("--check", action="store_true", help="compare argos output to the committed file")
    args = ap.parse_args()

    if args.check:
        current = (ROOT / "examples" / "case-study-argos.md").read_text(encoding="utf-8")
        regenerated = _argos_md(args.semantic_profile or "char-ngram-v1")
        if current.strip() != regenerated.strip():
            print("case-study-argos.md is stale; run examples/regenerate_case_studies.py", file=sys.stderr)
            return 1
        print("case-study-argos.md is fresh")
        return 0

    if args.target in ("argos", "all"):
        (ROOT / "examples" / "case-study-argos.md").write_text(
            _argos_md(args.semantic_profile or "char-ngram-v1"), encoding="utf-8"
        )
        print("wrote examples/case-study-argos.md")
    for slug, case in THIRD_PARTY_CASES.items():
        if args.target in (slug, "all"):
            md = _third_party_md(slug, case, args.semantic_profile)
            if md is not None:
                (ROOT / f"examples/case-study-{slug}.md").write_text(md, encoding="utf-8")
                print(f"wrote examples/case-study-{slug}.md")
            else:
                print(f"{slug} clone failed; left unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
