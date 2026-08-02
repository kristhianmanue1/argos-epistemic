"""Extractor L3 (contratos y grafo de llamadas) sobre código Python.

Construye un grafo de llamadas simbólico y best-effort con ``ast``: para cada
función/método registra las llamadas que realiza y resuelve, por nombre corto,
a otras funciones definidas en el codebase. Es verificación **simbólica** (§9.1):
no hace análisis de flujo, aliasing ni resolución de tipos; ``self.x()`` se
resuelve por nombre de atributo. Suficiente para estimar ``Centrality`` e
``Impact`` como términos ``tool-measured`` de ``R`` (§6.1), no como verdad del
grafo real.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CallNode:
    id: str
    file: str
    name: str


@dataclass
class CallGraph:
    nodes: dict[str, CallNode] = field(default_factory=dict)
    edges: set[tuple[str, str]] = field(default_factory=set)
    by_short: dict[str, set[str]] = field(default_factory=dict)

    def add_node(self, node_id: str, file: str, name: str) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = CallNode(node_id, file, name)
            self.by_short.setdefault(name, set()).add(node_id)

    def add_edge(self, caller: str, callee: str) -> None:
        if caller != callee and callee in self.nodes:
            self.edges.add((caller, callee))

    def neighbors(self) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = {n: set() for n in self.nodes}
        for caller, callee in self.edges:
            adj[caller].add(callee)
            adj[callee].add(caller)
        return adj

    def reachable(self, src: str) -> set[str]:
        forward: dict[str, set[str]] = {n: set() for n in self.nodes}
        for caller, callee in self.edges:
            forward[caller].add(callee)
        seen: set[str] = set()
        stack = [src]
        while stack:
            current = stack.pop()
            for nxt in forward.get(current, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def centrality(self) -> dict[str, float]:
        adj = self.neighbors()
        n = len(self.nodes)
        if n <= 1:
            return {n_id: 0.0 for n_id in self.nodes}
        denom = n - 1
        return {n_id: len(adj[n_id]) / denom for n_id in self.nodes}

    def impact(self) -> dict[str, float]:
        n = len(self.nodes)
        if n <= 1:
            return {n_id: 0.0 for n_id in self.nodes}
        return {n_id: len(self.reachable(n_id)) / (n - 1) for n_id in self.nodes}

    def production_subgraph(self) -> CallGraph:
        """Subgraph excluding test files (production-only view for R metrics)."""
        sub = CallGraph()
        for node_id, node in self.nodes.items():
            if is_test_file(node.file):
                continue
            sub.add_node(node_id, node.file, node.name)
        for caller, callee in self.edges:
            if caller in sub.nodes and callee in sub.nodes:
                sub.edges.add((caller, callee))
        return sub

    def merge(self, other: CallGraph) -> None:
        for node_id, node in other.nodes.items():
            if node_id not in self.nodes:
                self.add_node(node_id, node.file, node.name)
        self.edges |= other.edges


class _CallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name):
            self.calls.append(func.id)
        elif isinstance(func, ast.Attribute):
            self.calls.append(func.attr)
        self.generic_visit(node)


def _iter_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def build_call_graph(root: Path, py_files: list[Path]) -> CallGraph:
    cg = CallGraph()
    parsed: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for path in py_files:
        rel = _rel(root, path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        for func in _iter_functions(tree):
            node_id = f"{rel}::{func.name}"
            cg.add_node(node_id, rel, func.name)
            parsed.append((node_id, func))
    for node_id, func in parsed:
        collector = _CallCollector()
        collector.visit(func)
        file = cg.nodes[node_id].file
        for short in collector.calls:
            targets = cg.by_short.get(short, set())
            if not targets:
                continue
            same_module = {t for t in targets if cg.nodes[t].file == file}
            chosen = same_module or targets
            for target in chosen:
                cg.add_edge(node_id, target)
    return cg


# Pluggable L3 extractors: the MODEL is language-agnostic; each entry is a tool
# that builds a CallGraph for one language from its files. Python's AST extractor
# is bundled; other languages are registered externally (e.g. tree-sitter).
L3_EXTRACTORS: dict[str, Callable[..., CallGraph]] = {".py": build_call_graph}


def register_l3_extractor(suffix: str, extractor) -> None:
    """Register a CallGraph extractor for a source suffix (e.g. '.js')."""
    L3_EXTRACTORS[suffix.lower()] = extractor


def build_multi_call_graph(root: Path, files: list[Path]) -> CallGraph:
    """Dispatch to per-language L3 extractors and merge their CallGraphs.

    Files whose suffix has no registered extractor are skipped (graceful no-op),
    so the pipeline runs on any repo and simply yields no L3 for unsupported
    languages.
    """
    merged = CallGraph()
    by_suffix: dict[str, list[Path]] = {}
    for path in files:
        by_suffix.setdefault(path.suffix.lower(), []).append(path)
    for suffix, extractor in L3_EXTRACTORS.items():
        candidates = by_suffix.get(suffix, [])
        if not candidates:
            continue
        partial = extractor(root, candidates)
        if partial is not None:
            merged.merge(partial)
    return merged


def is_test_file(file: str) -> bool:
    lower = file.lower()
    base = lower.rsplit("/", 1)[-1]
    return (
        lower.startswith(("tests/", "test/", "spec/"))
        or "/tests/" in lower
        or "/test/" in lower
        or base.startswith("test_")
        or base.startswith("conftest")
    )


def module_metrics(cg: CallGraph) -> dict[str, dict[str, float]]:
    """Per-module max centrality/impact over the **production** subgraph.

    Test files are excluded from the metric so they don't inflate production
    impact (tests are sinks that call many symbols). Test files get 0.0 here;
    they enter the pipeline as L5 evidence, not as production nodes of ``R``.
    """
    prod = cg.production_subgraph()
    cent = prod.centrality()
    imp = prod.impact()
    out: dict[str, dict[str, float]] = {}
    for node in prod.nodes.values():
        bucket = out.setdefault(node.file, {"centrality": 0.0, "impact": 0.0, "functions": 0.0})
        bucket["centrality"] = max(bucket["centrality"], cent[node.id])
        bucket["impact"] = max(bucket["impact"], imp[node.id])
        bucket["functions"] += 1.0
    return out


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
