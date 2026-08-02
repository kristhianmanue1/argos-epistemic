"""Extractores L0/L1/L2/L4 sobre un sistema de archivos real.

Produce un ``system`` consumible por ``analyze_system``. Es una capa minima y
declarada: implementa intencion (L0), topologia (L1), entorno reproducible (L2)
y codigo/pruebas (L4/L5-comportamiento-estatico). No implementa AST, grafo de
llamadas ni ejecucion (L3 simbolico, L5 dinamico), por lo que ``Impact`` y
``Centrality`` no se computan (ver readme.md §6.1).

La ``relevance`` de cada artefacto es la aproximacion publica de ``R(x|G)``:
heuristica por nombre/extension condicionada al objetivo ``G``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .callgraph import CallGraph, build_call_graph, build_multi_call_graph, module_metrics

DEFAULT_IGNORES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".an-kla",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
}

L0_NAMES = {
    "readme.md",
    "readme.rst",
    "readme.txt",
    "readme",
    "agents.md",
    "contributing.md",
    "changelog.md",
    "license",
    "license.md",
}

L2_NAMES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "cargo.toml",
    "go.mod",
    "go.sum",
    "gemfile",
    "gemfile.lock",
    "pom.xml",
    "build.gradle",
    "dockerfile",
    ".gitignore",
    "tsconfig.json",
    "composer.json",
}

L4_SUFFIXES = (".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".kt")
L2_SUFFIXES = (".toml", ".cfg", ".ini", ".yml", ".yaml", ".lock")

_READ_LIMIT = 8192
MAX_CODE_ARTIFACTS = 400


def _walk(root: Path, ignores: set[str]) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if any(part.lower() in ignores for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            out.append(path)
    return out


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read(path: Path, limit: int = _READ_LIMIT) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _relevance(rel_path: str, goal: dict[str, Any]) -> float:
    aspects = (
        " ".join(str(a).lower() for a in goal.get("aspects", []))
        + " "
        + str(goal.get("name", "")).lower()
    )
    name = rel_path.lower()
    score = 0.4
    for token in aspects.split():
        if len(token) >= 3 and token in name:
            score += 0.2
    return min(1.0, score)


def _tokens(text: str) -> set[str]:
    import re

    return {t for t in re.findall(r"[0-9a-záéíóúñ]+", text.lower()) if t}


def lexical_semantic(artifact_text: str, goal_text: str) -> float:
    """Default ``S_semantic`` surrogate: Jaccard over token sets.

    Declared non-faithful (readme.md §6.1): it measures lexical overlap, not
    semantic similarity. Inject an embedding/LLM-based callable for fidelity.
    """
    a, b = _tokens(artifact_text), _tokens(goal_text)
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _goal_text(goal: dict[str, Any]) -> str:
    return " ".join(str(a) for a in goal.get("aspects", [])) + " " + str(goal.get("name", ""))


def _blend_relevance(
    rel_path: str,
    content: str,
    goal: dict[str, Any],
    metrics: dict[str, dict[str, float]] | None,
    semantic_fn,
) -> tuple[float, float, float, float]:
    """Relevance blending: lexical + S_semantic + tool-measured L3 terms.

    Weights: lexical 0.45, S_semantic 0.20, impact 0.20, centrality 0.15.
    ``S_semantic`` uses ``semantic_fn`` (default ``lexical_semantic`` surrogate,
    non-faithful per §6.1). Returns (relevance, s_semantic, impact, centrality).
    """
    sim = semantic_fn or lexical_semantic
    lexical = _relevance(rel_path, goal)
    s_sem = sim(rel_path + "\n" + content[:512], _goal_text(goal))
    impact = 0.0
    centrality = 0.0
    if metrics and rel_path in metrics:
        impact = float(metrics[rel_path].get("impact", 0.0))
        centrality = float(metrics[rel_path].get("centrality", 0.0))
    relevance = min(1.0, 0.45 * lexical + 0.20 * s_sem + 0.20 * impact + 0.15 * centrality)
    return relevance, s_sem, impact, centrality


def _non_functional(rel_path: str) -> list[str]:
    name = rel_path.lower()
    nf: list[str] = []
    if any(k in name for k in ("auth", "secret", "password", "credential", "permission", "crypto", "token", "/sec")):
        nf.append("sec")
    return nf


def _topology(root: Path, files: list[Path]) -> str:
    return "\n".join(_rel(root, p) for p in files[:500])


def extract_system(
    root: Path | str,
    goal: dict[str, Any] | None = None,
    semantic_fn=None,
) -> dict[str, Any]:
    goal = goal or {}
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(root)
    ignores = set(DEFAULT_IGNORES)
    files = _walk(root, ignores)
    cg = build_multi_call_graph(root, files)
    metrics = module_metrics(cg)
    sim = semantic_fn or lexical_semantic
    artifacts: list[dict[str, Any]] = [
        {
            "id": "L1:topology",
            "content": _topology(root, files),
            "location": "(topology)",
            "level": 1,
            "relevance": 0.7,
            "kind": "topology",
        }
    ]
    artifacts.append(_callgraph_artifact(cg))
    code_seen = 0
    for path in files:
        rel = _rel(root, path)
        base = path.name.lower()
        content = _read(path)
        if base in L0_NAMES or (path.suffix == ".md" and base.startswith("readme")):
            artifacts.append(
                {
                    "id": rel,
                    "content": content,
                    "location": rel,
                    "level": 0,
                    "relevance": _relevance(rel, goal),
                    "kind": "doc",
                }
            )
        elif base in L2_NAMES or path.name.lower().endswith(L2_SUFFIXES):
            artifacts.append(
                {
                    "id": rel,
                    "content": content,
                    "location": rel,
                    "level": 2,
                    "relevance": _relevance(rel, goal),
                    "kind": "config",
                }
            )
        elif path.suffix in L4_SUFFIXES or path.suffix == ".md":
            if code_seen >= MAX_CODE_ARTIFACTS:
                continue
            code_seen += 1
            is_test = "test" in base or rel.lower().startswith(("tests/", "test/", "spec/"))
            kind = "test" if is_test else ("doc" if path.suffix == ".md" else "code")
            level = 5 if is_test else 4
            relevance, s_sem, impact, centrality = _blend_relevance(rel, content, goal, metrics, sim)
            artifact: dict[str, Any] = {
                "id": rel,
                "content": content,
                "location": rel,
                "level": level,
                "relevance": relevance,
                "kind": kind,
                "s_semantic": s_sem,
                "impact": impact,
                "centrality": centrality,
            }
            nf = _non_functional(rel)
            if nf:
                artifact["nf"] = nf
            artifacts.append(artifact)
    return {"name": root.name, "artifacts": artifacts, "call_graph": _callgraph_summary(cg)}


def _callgraph_artifact(cg: CallGraph) -> dict[str, Any]:
    prod = cg.production_subgraph()
    cent = prod.centrality()
    imp = prod.impact()
    ranked = sorted(prod.nodes.values(), key=lambda n: imp[n.id], reverse=True)[:20]
    lines = [
        f"production impact centrality node "
        f"({len(prod.nodes)} prod nodes, {len(prod.edges)} prod edges; "
        f"{len(cg.nodes) - len(prod.nodes)} test nodes excluded)"
    ]
    for node in ranked:
        lines.append(f"{imp[node.id]:.2f}    {cent[node.id]:.2f}    {node.id}")
    return {
        "id": "L3:callgraph",
        "content": "\n".join(lines),
        "location": "(callgraph)",
        "level": 3,
        "relevance": 0.8,
        "kind": "callgraph",
    }


def _callgraph_summary(cg: CallGraph) -> dict[str, Any]:
    prod = cg.production_subgraph()
    imp = prod.impact()
    return {
        "nodes": len(cg.nodes),
        "edges": len(cg.edges),
        "production_nodes": len(prod.nodes),
        "top_impact": [
            {"id": n.id, "impact": round(imp.get(n.id, 0.0), 3)}
            for n in sorted(prod.nodes.values(), key=lambda m: imp.get(m.id, 0.0), reverse=True)[:5]
        ],
    }


def _safe_impact(cg: CallGraph, node_id: str) -> float:
    return cg.production_subgraph().impact().get(node_id, 0.0)


def analyze_path(
    root: Path | str,
    goal: dict[str, Any] | None = None,
    budget: Any = None,
    run_dynamic: bool = False,
    run_history: bool = False,
    dynamic_timeout: int = 120,
    semantic_fn=None,
) -> dict[str, Any]:
    from .algorithm import Budget, analyze_system
    from .dynamic import dynamic_artifact
    from .history import history_artifact

    if budget is None:
        budget = Budget(tokens_remaining=200000, tool_remaining=2000)
    system = extract_system(root, goal, semantic_fn=semantic_fn)
    if run_history:
        artifact = history_artifact(root, goal)
        if artifact is not None:
            system["artifacts"].append(artifact)
            system["history"] = artifact.pop("run", None)
    if run_dynamic:
        artifact = dynamic_artifact(root, timeout=dynamic_timeout)
        if artifact is not None:
            system["artifacts"].append(artifact)
            system["dynamic"] = artifact.pop("run", None)
    return analyze_system(system, goal or {}, budget)
