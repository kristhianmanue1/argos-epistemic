"""Extracción multinivel sobre un sistema de archivos real.

Produce un ``system`` consumible por ``analyze_system``. Integra intención
(L0), topología (L1), entorno reproducible (L2), grafo de llamadas enchufable
(L3), comportamiento estático (L4) y evidencia histórica o dinámica (L5).
``Impact`` y ``Centrality`` se computan cuando existe un extractor L3 para el
lenguaje observado (ver MODEL.md §6.1).

La ``relevance`` de cada artefacto es la aproximacion publica de ``R(x|G)``:
heuristica por nombre/extension condicionada al objetivo ``G``.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from .behavior import behavior_artifact, behavior_summary, extract_behavior
from .bundle import INVENTORY_SCHEMA
from .callgraph import CallGraph, build_multi_call_graph, module_metrics
from .canonical import CANONICALIZATION_PROFILE, fingerprinted_document
from .dense_semantic import dense_semantic, dense_semantic_available

DEFAULT_IGNORES = {
    ".ds_store",
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

# Tasas de decaimiento por nivel (MODEL.md §14): λ0 < λ1 < λ2 ≈ λ4 < λ3 < λ5.
# Tasas diarias: L0 (docs) decae más lento, L5 (runtime/logs) más rápido.
FRESHNESS_LAMBDA = {
    0: 1.0 / 365,
    1: 1.0 / 240,
    2: 1.0 / 120,
    3: 1.0 / 60,
    4: 1.0 / 120,
    5: 1.0 / 21,
}


def freshness(level: int, t_x: float, t_now: float) -> float:
    """Vigencia temporal de la evidencia (MODEL.md §14): ``e^{-λ_n(t - t_x)}``.

    Devuelve 1.0 (neutral, sin penalización) cuando los timestamps no están
    disponibles o la evidencia es futura, de modo que fixtures sintéticos sin
    mtime no se anulán espurios. La granularidad es por día entero: basta para
    un modelo de referencia y garantiza determinismo dentro del mismo día.
    """
    if t_x <= 0 or t_now <= 0 or t_now <= t_x:
        return 1.0
    lam = FRESHNESS_LAMBDA.get(level, 1.0 / 120)
    days = max(0, int((t_now - t_x) // 86400))
    return max(0.0, min(1.0, math.exp(-lam * days)))


def _walk(root: Path, ignores: set[str]) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel_parts = path.relative_to(root).parts
        if any(part.lower() in ignores for part in rel_parts):
            continue
        if any(part.lower().endswith(".egg-info") for part in rel_parts):
            continue
        if path.is_file():
            out.append(path)
    return out


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read(path: Path, limit: int = _READ_LIMIT) -> tuple[str, bool, int]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            observed = handle.read(limit + 1)
    except OSError:
        return "", False, 0
    content = observed[:limit]
    return content, len(observed) > limit, len(content.encode("utf-8"))


def _file_level_kind(path: Path, rel: str) -> tuple[int, str] | None:
    base = path.name.lower()
    if base in L0_NAMES or (path.suffix == ".md" and base.startswith("readme")):
        return 0, "doc"
    if base in L2_NAMES or base.endswith(L2_SUFFIXES):
        return 2, "config"
    if path.suffix in L4_SUFFIXES or path.suffix == ".md":
        is_test = "test" in base or rel.lower().startswith(("tests/", "test/", "spec/"))
        return (5, "test") if is_test else (4, "doc" if path.suffix == ".md" else "code")
    return None


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

    Declared non-faithful (MODEL.md §6.1): it measures lexical overlap, not
    semantic similarity. Inject an embedding/LLM-based callable for fidelity.
    """
    a, b = _tokens(artifact_text), _tokens(goal_text)
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


_EMBED_DIM = 256


def _hash_vec(text: str, n: int = 3, dim: int = _EMBED_DIM) -> list[float]:
    """Signed-hashing char-n-gram vector (lightweight embedding surrogate).

    Captures morphological relatedness (``auth`` ~ ``authentication``) without
    external models. Not a dense semantic embedding; inject sentence-transformers
    or an API embedder via ``semantic_fn`` for true semantics.
    """
    import hashlib

    vec = [0.0] * dim
    lowered = text.lower()
    grams = {lowered[i : i + n] for i in range(max(0, len(lowered) - n + 1))}
    grams |= _tokens(text)
    for gram in grams:
        if not gram:
            continue
        h = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % dim
        sign = 1.0 if (h[4] & 1) else -1.0
        vec[idx] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm:
        vec = [v / norm for v in vec]
    return vec


def embedding_semantic(artifact_text: str, goal_text: str) -> float:
    """Cosine over hashed char-n-gram embeddings. Stronger than ``lexical_semantic``.

    A dependency-free embedding surrogate; for dense semantics inject an external
    embedder (sentence-transformers / API) via ``semantic_fn``.
    """
    a, b = _hash_vec(artifact_text), _hash_vec(goal_text)
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return max(0.0, min(1.0, (dot + 1.0) / 2.0))


def default_semantic():
    """Linker semántico por defecto: denso (sentence-transformers) si está
    disponible, si no léxico. Nunca el surrogate de char-n-gramas
    (``embedding_semantic``), cuyo suelo ~0.5 lo hace no discriminativo y
    sobre-enlaza artefactos irrelevantes (.gitignore -> 'memory')."""
    return dense_semantic if dense_semantic_available() else lexical_semantic


def default_link_threshold(linker) -> float:
    """Threshold calibrado al linker: léxico (Jaccard) opera en [0,1] con valores
    bajos significativos; embedding/denso operan en ~[0.5,0.65] y necesitan un
    threshold alto (~0.55-0.60) o sobre-enlazan ruido. Identidad por función."""
    if linker is lexical_semantic:
        return 0.05
    if linker is dense_semantic:
        return 0.60
    if linker is embedding_semantic:
        return 0.55
    return 0.05


def _goal_text(goal: dict[str, Any]) -> str:
    return " ".join(str(a) for a in goal.get("aspects", [])) + " " + str(goal.get("name", ""))


def _blend_relevance(
    rel_path: str,
    content: str,
    goal: dict[str, Any],
    metrics: dict[str, dict[str, float]] | None,
    semantic_fn,
    level: int = 4,
    t_x: float = 0.0,
    t_now: float = 0.0,
) -> tuple[float, float, float, float, float]:
    """Relevance blending: lexical + S_semantic + tool-measured L3 + Freshness.

    Pesos: lexical 0.40, S_semantic 0.18, impact 0.18, centrality 0.12,
    freshness 0.12 (MODEL.md §6 + §14). ``S_semantic`` usa ``semantic_fn``
    (surrogate ``lexical_semantic`` por defecto, no fiel según §6.1);
    ``freshness`` es ``e^{-λ_n(t-t_x)}`` (§14, computable vía mtime/git).
    Devuelve (relevance, s_semantic, impact, centrality, freshness).
    """
    sim = semantic_fn or lexical_semantic
    lexical = _relevance(rel_path, goal)
    s_sem = sim(rel_path + "\n" + content[:512], _goal_text(goal))
    impact = 0.0
    centrality = 0.0
    if metrics and rel_path in metrics:
        impact = float(metrics[rel_path].get("impact", 0.0))
        centrality = float(metrics[rel_path].get("centrality", 0.0))
    fresh = freshness(level, t_x, t_now)
    relevance = min(
        1.0,
        0.40 * lexical + 0.18 * s_sem + 0.18 * impact + 0.12 * centrality + 0.12 * fresh,
    )
    return relevance, s_sem, impact, centrality, fresh


def _non_functional(rel_path: str) -> list[str]:
    name = rel_path.lower()
    nf: list[str] = []
    if any(k in name for k in ("auth", "secret", "password", "credential", "permission", "crypto", "token", "/sec")):
        nf.append("sec")
    return nf


def _topology(root: Path, files: list[Path]) -> str:
    return "\n".join(_rel(root, p) for p in files[:500])


def _file_artifact(
    rel: str,
    path: Path,
    content: str,
    level: int,
    kind: str,
    goal: dict[str, Any],
    metrics: dict[str, dict[str, float]] | None,
    sim,
    now: float,
) -> dict[str, Any]:
    """Artefacto de fichero real con el blend unificado de R (§6 + §14):
    lexical + S_semantic + impact + centrality + freshness. Impact/centrality
    son 0 cuando el fichero no está en el grafo de llamadas de producción
    (docs, configs, código no parseado) -> el blend es simétrico entre niveles."""
    mtime = path.stat().st_mtime
    relevance, s_sem, impact, centrality, fresh = _blend_relevance(
        rel, content, goal, metrics, sim, level=level, t_x=mtime, t_now=now
    )
    return {
        "id": rel,
        "content": content,
        "location": rel,
        "level": level,
        "relevance": relevance,
        "kind": kind,
        "s_semantic": s_sem,
        "impact": impact,
        "centrality": centrality,
        "freshness": fresh,
        "timestamp": int(mtime),
    }


def extract_system(
    root: Path | str,
    goal: dict[str, Any] | None = None,
    semantic_fn=None,
    extra_ignores: set[str] | None = None,
) -> dict[str, Any]:
    goal = goal or {}
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(root)
    ignores = set(DEFAULT_IGNORES)
    if extra_ignores:
        ignores |= set(extra_ignores)
    files = _walk(root, ignores)
    discovered_bytes = sum(path.stat().st_size for path in files)
    cg = build_multi_call_graph(root, files)
    metrics = module_metrics(cg)
    behaviors = extract_behavior(root, files)
    sim = semantic_fn or default_semantic()
    now = time.time()
    artifacts: list[dict[str, Any]] = [
        {
            "id": "L1:topology",
            "content": _topology(root, files),
            "location": "(topology)",
            "level": 1,
            "relevance": 0.7,
            "kind": "topology",
            "freshness": 1.0,
            "timestamp": int(now),
        }
    ]
    artifacts.append(_callgraph_artifact(cg, now))
    artifacts.append(behavior_artifact(behaviors, now))
    code_seen = 0
    files_eligible = 0
    files_selected = 0
    bytes_read = 0
    exclusions: list[dict[str, Any]] = []
    truncations: list[dict[str, Any]] = []
    for path in files:
        rel = _rel(root, path)
        classification = _file_level_kind(path, rel)
        if classification is None:
            continue
        files_eligible += 1
        level, kind = classification
        if level in (4, 5):
            if code_seen >= MAX_CODE_ARTIFACTS:
                exclusions.append(
                    {
                        "id": rel,
                        "reason": "artifact_cap",
                        "estimated_bytes": min(path.stat().st_size, _READ_LIMIT),
                    }
                )
                continue
            code_seen += 1
        content, content_truncated, observed_bytes = _read(path)
        bytes_read += observed_bytes
        files_selected += 1
        artifact = _file_artifact(rel, path, content, level, kind, goal, metrics, sim, now)
        artifact["content_truncated"] = content_truncated
        artifact["observed_bytes"] = observed_bytes
        if content_truncated:
            truncations.append({"id": rel, "reason": "read_limit", "observed_bytes": observed_bytes})
        if level in (4, 5):
            nf = _non_functional(rel)
            if nf:
                artifact["nf"] = nf
        artifacts.append(artifact)
    degradations: list[str] = []
    if exclusions:
        degradations.append("artifact_cap_reached")
    if truncations:
        degradations.append("content_truncated")
    inventory = fingerprinted_document({
        "schema": INVENTORY_SCHEMA,
        "canonicalization": CANONICALIZATION_PROFILE,
        "profile": "legacy-first-400-v1",
        "files_discovered": len(files),
        "files_eligible": files_eligible,
        "files_selected": files_selected,
        "files_ineligible": len(files) - files_eligible,
        "files_omitted_by_cap": len(exclusions),
        "read_truncations": len(truncations),
        "bytes_discovered": discovered_bytes,
        "bytes_read": bytes_read,
        "exclusions": exclusions,
        "truncations": truncations,
        "degradations": degradations,
    })
    return {
        "name": root.name,
        "artifacts": artifacts,
        "call_graph": _callgraph_summary(cg),
        "behavior": behavior_summary(behaviors),
        "inventory": inventory,
    }


def _callgraph_artifact(cg: CallGraph, now: float = 0.0) -> dict[str, Any]:
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
        "freshness": 1.0,
        "timestamp": int(now),
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
    run_logs: bool = False,
    run_coverage: bool = False,
    run_profile: bool = False,
    dynamic_timeout: int = 120,
    semantic_fn=None,
) -> dict[str, Any]:
    from .algorithm import Budget, analyze_system
    from .coverage import coverage_artifact
    from .dynamic import dynamic_artifact
    from .history import history_artifact
    from .logs import logs_artifact
    from .profile import profile_artifact

    root_path = Path(root)
    if budget is None:
        budget = Budget(tokens_remaining=200000, tool_remaining=2000)
    system = extract_system(root, goal, semantic_fn=semantic_fn)
    # L5 subprocess extractors are registered as DEFERRED actions (H4): a cheap
    # precondition is probed at discovery, but the expensive subprocess only
    # runs when the budgeted loop selects the action (loader). Cost is estimated
    # from a size hint and observed from the real output.
    from .dynamic import detect_runner

    def _deferred(aid, location, level, relevance, kind, method, loader):
        return {
            "id": aid, "content": "", "location": location, "level": level,
            "relevance": relevance, "kind": kind, "verification_method": method,
            "size": 200, "loader": loader,
        }

    def _unwrap(artifact):
        if not artifact:
            return {}
        return {"content": artifact.get("content", ""), "run": artifact.get("run")}

    if run_logs and any(root_path.rglob("*.log")):
        system["artifacts"].append(
            _deferred("L5:logs", "(logs)", 5, 0.6, "logs", "historical",
                      lambda: _unwrap(logs_artifact(root_path, goal)))
        )
    if run_history and (root_path / ".git").exists():
        system["artifacts"].append(
            _deferred("L5:gitlog", "(history)", 5, 0.7, "history", "historical",
                      lambda: _unwrap(history_artifact(root_path, goal)))
        )
    if run_coverage and (root_path / "coverage.xml").exists():
        system["artifacts"].append(
            _deferred("L5:coverage", "(coverage)", 5, 0.8, "coverage", "historical",
                      lambda: _unwrap(coverage_artifact(root_path, goal)))
        )
    if run_profile and any(root_path.rglob("*.prof")):
        system["artifacts"].append(
            _deferred("L5:profile", "(profile)", 5, 0.6, "profile", "historical",
                      lambda: _unwrap(profile_artifact(root_path, goal)))
        )
    if run_dynamic:
        label = detect_runner(root_path)[0]
        system["artifacts"].append(
            _deferred(f"L5:{label}", "(dynamic)", 5, 0.85, "test-run", "dynamic",
                      lambda: _unwrap(dynamic_artifact(root_path, timeout=dynamic_timeout)))
        )
    return analyze_system(system, goal or {}, budget)
