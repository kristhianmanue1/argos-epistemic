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
    fingerprinted_document,
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

# Casos tercerizados: se fija un SHA exacto y se hace fetch shallow de esa
# revisión (target revision pinned: elimina la deriva del checkout analizado,
# no depende de HEAD móvil ni de un path local). La reproducibilidad extremo a
# extremo exige además fijar revisión del evaluador, perfil semántico, política
# de frescura y presupuesto. Requieren red; los terceros se verifican
# explícitamente con `--target <slug> --check`.
#
# `pinned_revision` de an-kla-memory sigue la dependencia operativa vigente
# declarada en requirements.txt (tag v0.1.0-beta.6 -> f28341e), que coincide con
# el paquete instalado. No sigue a HEAD.
THIRD_PARTY_CASES = {
    "markupsafe": {
        "repo": "https://github.com/pallets/markupsafe.git",
        "pinned_revision": "b2e4d9c7687be25695fffbe93a37622302b24fb1",
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
        "pinned_revision": "f28341ea872f221d7462b6b2bb32b8c1db68ac28",
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


STATUS_FRESH = "fresh"
STATUS_STALE = "stale"
STATUS_UNAVAILABLE = "unavailable"
STATUS_INVALID_REVISION = "invalid_revision"

BUDGET_PROFILE = {"tokens": 200000, "tool": 2000}

FRESHNESS_PROFILES = {
    "fixed-clock-v1": {
        "timestamp_source": "fixed",
        "observed_at": "0",
        "freshness": "1.0",
    },
    "filesystem-mtime-v1": {
        "timestamp_source": "filesystem",
        "observed_at": "extraction_time",
        "freshness": "computed",
    },
}

CASE_FRESHNESS_PROFILE = {"argos": "fixed-clock-v1"}
DEFAULT_FRESHNESS_PROFILE = "filesystem-mtime-v1"


def evaluator_identity() -> dict[str, str]:
    """Evaluator identity recorded in the manifest.

    Deliberately the distribution version rather than the Git HEAD of this
    checkout: the self-study renders back into this repository, so embedding
    the evaluator commit would create a self-reference that can never
    stabilise - writing the file changes the commit the file would have to
    declare. Third-party target revisions are pinned separately and are stable.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return {"package": "argos-epistemic", "version": version("argos-epistemic")}
    except PackageNotFoundError:
        return {"package": "argos-epistemic", "version": "unknown"}


def case_manifest(slug: str, profile: str) -> dict:
    """Reproducible configuration consumed by the generator (plan §5.1).

    Pins semantic profile, target revision, evaluator, freshness policy and
    budget, and fingerprints the lot. The fingerprint covers the *inputs*, not
    the rendered output, so it stays stable while the pipeline's results legitimately change.
    """
    freshness_profile = CASE_FRESHNESS_PROFILE.get(slug, DEFAULT_FRESHNESS_PROFILE)
    case = THIRD_PARTY_CASES.get(slug)
    goal = ARGOS_GOAL if slug == "argos" else case["goal"]
    return fingerprinted_document(
        {
            "schema": "argos/case-study-manifest-v1",
            "case": slug,
            "semantic_profile": profile,
            "link_threshold": str(SEMANTIC_PROFILES[profile][1]),
            "target": "self" if slug == "argos" else case["repo"],
            "target_revision": "self" if slug == "argos" else case["pinned_revision"],
            "independence_class": "self_study"
            if slug == "argos"
            else case["independence_class"],
            "evaluator": evaluator_identity(),
            "freshness_profile": freshness_profile,
            "freshness_policy": FRESHNESS_PROFILES[freshness_profile],
            "budget": {
                "tokens": str(BUDGET_PROFILE["tokens"]),
                "tool": str(BUDGET_PROFILE["tool"]),
            },
            "goal": {
                "name": goal["name"],
                "aspects": list(goal["aspects"]),
                "non_functional": list(goal.get("non_functional", [])),
                "theta_coverage": str(goal["theta_coverage"]),
                "rho_risk": str(goal["rho_risk"]),
            },
        }
    )


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


def evaluate_argos(profile: str = "char-ngram-v1") -> dict:
    """Run the pipeline over this checkout. Pure data, no rendering."""
    goal = configured_goal(ARGOS_GOAL, profile)
    system, report = _run(
        ROOT,
        goal,
        extra_ignores=self_study_output_names(),
        normalize_freshness=True,
    )
    return {
        "slug": "argos",
        "profile": profile,
        "goal": goal,
        "system": system,
        "report": report,
        "manifest": case_manifest("argos", profile),
        "test_count": _test_count(),
    }


def render_argos(evaluation: dict) -> str:
    """Render an argos evaluation. Pure formatting, no pipeline execution."""
    profile = evaluation["profile"]
    goal = evaluation["goal"]
    system = evaluation["system"]
    report = evaluation["report"]
    cg = system.get("call_graph", {})
    bh = system.get("behavior", {})
    top = ", ".join(f"{n['id'].split('::')[-1]} ({n['impact']})" for n in cg.get("top_impact", [])[:4])
    raw = json.dumps({k: report[k] for k in ("evidence_count", "proposition_count", "coverage", "residual_risk", "complete")})
    relation_counts = Counter(item["relation"] for item in report["claims"])
    lines = [
        "# Caso de estudio: argos-epistemic (autoestudio)",
        "",
        "> Generado por `examples/regenerate_case_studies.py` desde el pipeline "
        "actual (no escrito a mano). El sistema analizado es el propio repositorio; "
        "es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).",
        "",
        f"Tests en verde: **{evaluation['test_count']}**. Objetivo "
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
        f"relations        : {dict(sorted(relation_counts.items()))}",
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
        "aspecto sobre relaciones `supports`; `mentions` orienta recuperación "
        "pero aporta cero cobertura. El "
        "costo **observado** (contenido real leído) se contabiliza contra el "
        "presupuesto y se compara con el estimado (stat).",
        "",
        "## Riesgo residual",
        "",
        "- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para "
        "evidencia independiente.",
        "- **Identidad Git no incrustada**: incluir el commit del propio archivo "
        "generado crearía una autorreferencia imposible de estabilizar. El manifest "
        "registra en su lugar la versión de la distribución evaluadora.",
        "- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), "
        "no denso; sesión del LLM/transformers queda pendiente.",
        "- **Discovery no presupuestado**: la lectura de archivos y el índice L3 "
        "se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo "
        "el contenido por-objetivo y los extractores subprocess son perezosos.",
        "- **Frescura normalizada**: este artefacto fija `freshness=1.0` y "
        "`timestamp=0` para no depender del `mtime` asignado por cada checkout; "
        "el pipeline normal conserva y evalúa los timestamps reales.",
        "",
        f"_Generado desde HEAD del pipeline. Manifest de entradas fijadas: "
        f"`{evaluation['manifest']['fingerprint']}` (perfil semántico, revisión del "
        f"target, evaluador, frescura y presupuesto). raw report: `{raw}`_",
        "",
    ]
    return "\n".join(lines)


def _argos_md(profile: str = "char-ngram-v1") -> str:
    return render_argos(evaluate_argos(profile))


def _fetch_pinned(repo: str, revision: str, dest: Path) -> str | None:
    """Fetch and check out an exact SHA (shallow), not a moving branch tip.

    Returns an error string on failure, None on success. This pins the *target
    revision* only: it removes drift from the analyzed checkout, unlike
    ``git clone --depth 1 <repo>`` which floats with the default branch. It
    does NOT by itself make a case reproducible end to end, which additionally
    requires pinning the evaluator revision, the semantic profile, the
    freshness policy and the budget.
    """
    init = subprocess.run(["git", "init", "-q", str(dest)], capture_output=True, text=True, timeout=30)
    if init.returncode != 0:
        return init.stderr.strip() or "git init failed"
    remote = subprocess.run(
        ["git", "-C", str(dest), "remote", "add", "origin", repo],
        capture_output=True, text=True, timeout=30,
    )
    if remote.returncode != 0:
        return remote.stderr.strip() or "git remote add failed"
    fetch = subprocess.run(
        ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", revision],
        capture_output=True, text=True, timeout=120,
    )
    if fetch.returncode != 0:
        return fetch.stderr.strip() or f"git fetch failed for revision {revision}"
    checkout = subprocess.run(
        ["git", "-C", str(dest), "checkout", "--quiet", "FETCH_HEAD"],
        capture_output=True, text=True, timeout=30,
    )
    if checkout.returncode != 0:
        return checkout.stderr.strip() or "git checkout FETCH_HEAD failed"
    return None


def evaluate_third_party(
    slug: str, case: dict, profile_override: str | None = None
) -> tuple[dict | None, str, str]:
    """Fetch the pinned revision and run the pipeline.

    Returns ``(evaluation, status, detail)``. ``status`` is one of
    ``STATUS_UNAVAILABLE`` (fetch/network failure), ``STATUS_INVALID_REVISION``
    (checkout landed elsewhere) or ``STATUS_FRESH`` (evaluation produced). An
    unavailable target is never rendered and never silently treated as success.
    """
    import shutil

    dest = Path(tempfile.mkdtemp(prefix=f"{slug}-"))
    try:
        revision = case["pinned_revision"]
        error = _fetch_pinned(case["repo"], revision, dest)
        if error is not None:
            return None, STATUS_UNAVAILABLE, (
                f"{slug}: fetch of pinned revision {revision} failed: {error}"
            )
        identity = git_identity(dest)
        if identity["revision"] != revision:
            return None, STATUS_INVALID_REVISION, (
                f"{slug}: checked-out revision {identity['revision']} does not match "
                f"pinned {revision}"
            )
        profile = profile_override or case["semantic_profile"]
        goal = configured_goal(case["goal"], profile)
        system, report = _run(dest, goal)
    finally:
        shutil.rmtree(dest, ignore_errors=True)
    return (
        {
            "slug": slug,
            "case": case,
            "profile": profile,
            "goal": goal,
            "system": system,
            "report": report,
            "identity": identity,
            "manifest": case_manifest(slug, profile),
        },
        STATUS_FRESH,
        "",
    )


def render_third_party(evaluation: dict) -> str:
    """Render a third-party evaluation. Pure formatting, no fetching."""
    slug = evaluation["slug"]
    case = evaluation["case"]
    profile = evaluation["profile"]
    goal = evaluation["goal"]
    system = evaluation["system"]
    report = evaluation["report"]
    identity = evaluation["identity"]
    cg = system.get("call_graph", {})
    bh = system.get("behavior", {})
    top = ", ".join(f"{n['id'].split('::')[-1]} ({n['impact']})" for n in cg.get("top_impact", [])[:4])
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
    lines += [
        "",
        f"_Manifest de entradas fijadas: `{evaluation['manifest']['fingerprint']}` "
        f"(perfil semántico, revisión del target, evaluador, frescura y presupuesto)._",
        "",
    ]
    return "\n".join(lines)


def _third_party_md(
    slug: str, case: dict, profile_override: str | None = None
) -> tuple[str | None, str | None]:
    """Back-compat shim over evaluate/render. Returns (markdown, error)."""
    evaluation, _status, detail = evaluate_third_party(slug, case, profile_override)
    if evaluation is None:
        return None, detail
    return render_third_party(evaluation), None


def case_path(slug: str) -> Path:
    return ROOT / "examples" / f"case-study-{slug}.md"


def generate_case(target: str, semantic_profile: str | None) -> tuple[str | None, str, str]:
    """Produce the markdown for one case. Returns (markdown, status, detail).

    Never returns markdown alongside a failure status: a case that could not be
    evaluated is not rendered, so a failed regeneration cannot overwrite a good
    file with a degraded one.
    """
    if target == "argos":
        return render_argos(evaluate_argos(semantic_profile or "char-ngram-v1")), STATUS_FRESH, ""
    case = THIRD_PARTY_CASES[target]
    evaluation, status, detail = evaluate_third_party(target, case, semantic_profile)
    if evaluation is None:
        return None, status, detail
    return render_third_party(evaluation), STATUS_FRESH, ""


def check_case(target: str, semantic_profile: str | None) -> tuple[str, str]:
    """Compare the committed case study against a fresh evaluation.

    Returns ``(status, message)`` where status is one of ``fresh``, ``stale``,
    ``unavailable`` or ``invalid_revision``. Only ``fresh`` is success: an
    unreachable target or a revision mismatch is reported as such and never
    downgraded into a pass, because that is precisely the drift the check
    exists to catch.
    """
    markdown, status, detail = generate_case(target, semantic_profile)
    if markdown is None:
        return status, f"case-study-{target}.md {status}: {detail}"
    path = case_path(target)
    if not path.exists():
        return STATUS_STALE, f"case-study-{target}.md is missing"
    if path.read_text(encoding="utf-8").strip() != markdown.strip():
        return STATUS_STALE, (
            f"case-study-{target}.md is stale; run "
            f"examples/regenerate_case_studies.py --target {target}"
        )
    return STATUS_FRESH, f"case-study-{target}.md is fresh"


def _check_one(target: str, semantic_profile: str | None) -> tuple[bool, str]:
    status, message = check_case(target, semantic_profile)
    return status == STATUS_FRESH, message


def _selected_targets(target_arg: str) -> list[str]:
    targets = []
    if target_arg in ("argos", "all"):
        targets.append("argos")
    targets += [slug for slug in THIRD_PARTY_CASES if target_arg in (slug, "all")]
    return targets


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["argos", *THIRD_PARTY_CASES, "all"], default="all")
    ap.add_argument("--semantic-profile", choices=sorted(SEMANTIC_PROFILES))
    ap.add_argument("--check", action="store_true", help="compare regenerated output to the committed file(s)")
    args = ap.parse_args()

    exit_code = 0
    for target in _selected_targets(args.target):
        if args.check:
            status, message = check_case(target, args.semantic_profile)
            ok = status == STATUS_FRESH
            print(message, file=sys.stdout if ok else sys.stderr)
            if not ok:
                exit_code = 1
            continue
        markdown, status, detail = generate_case(target, args.semantic_profile)
        if markdown is None:
            print(f"{target}: {status}: {detail}; left unchanged", file=sys.stderr)
            exit_code = 1
            continue
        case_path(target).write_text(markdown, encoding="utf-8")
        print(f"wrote examples/case-study-{target}.md")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
