"""Extractor L4 (comportamiento e invariantes) sobre código Python.

Best-effort simbólico con ``ast`` (análogo a ``callgraph.py`` para L3): para
cada función/método registra las excepciones que levanta (``raise``), los
``assert``/guardas (invariantes declarados), si muta estado (``self.x = ...``)
y si valida entrada (``raise ValueError/TypeError``). Puebla Σ_4 (excepciones,
invariantes, efectos) y da contenido simbólico real a L4, que antes era sólo
lectura de fichero.

Verificación **simbólica** (§9.1): NO hace análisis de flujo, aliasing,
inferencia de contratos ni distingue comportamiento implementado del
probado/accidental (§4 deja esa distinción como objetivo, no como garantía).
Sólo Python (como el L3 por AST); otros lenguajes requerirían un extractor
registrado, igual que el patrón plugable de L3.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .callgraph import _iter_functions, is_test_file

# Excepciones canónicas de validación de entrada (§4 "validaciones").
_VALIDATION_TYPES = frozenset({"ValueError", "TypeError"})


@dataclass
class FuncBehavior:
    id: str
    file: str
    name: str
    raises: set[str] = field(default_factory=set)
    asserts: int = 0
    mutates_self: bool = False

    @property
    def validates(self) -> bool:
        return bool(self.raises & _VALIDATION_TYPES)


class _BehaviorCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.raises: set[str] = set()
        self.asserts: int = 0
        self.mutates_self: bool = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # no desciende a anidadas
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Raise(self, node: ast.Raise) -> None:
        exc = node.exc
        func = exc.func if isinstance(exc, ast.Call) else exc
        if isinstance(func, ast.Name):
            self.raises.add(func.id)
        elif isinstance(func, ast.Attribute):
            self.raises.add(func.attr)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.asserts += 1
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for tgt in node.targets:
            if (
                isinstance(tgt, ast.Attribute)
                and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "self"
            ):
                self.mutates_self = True
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        tgt = node.target
        if (
            isinstance(tgt, ast.Attribute)
            and isinstance(tgt.value, ast.Name)
            and tgt.value.id == "self"
        ):
            self.mutates_self = True
        self.generic_visit(node)


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def extract_behavior(root: Path, py_files: list[Path]) -> list[FuncBehavior]:
    """Recorre funciones Python y extrae señales de comportamiento (Σ_4)."""
    out: list[FuncBehavior] = []
    for path in py_files:
        rel = _rel(root, path)
        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8", errors="replace"), filename=str(path)
            )
        except SyntaxError:
            continue
        for func in _iter_functions(tree):
            collector = _BehaviorCollector()
            for stmt in func.body:
                collector.visit(stmt)
            out.append(
                FuncBehavior(
                    id=f"{rel}::{func.name}",
                    file=rel,
                    name=func.name,
                    raises=collector.raises,
                    asserts=collector.asserts,
                    mutates_self=collector.mutates_self,
                )
            )
    return out


def behavior_summary(behaviors: list[FuncBehavior]) -> dict[str, Any]:
    prod = [b for b in behaviors if not is_test_file(b.file)]
    return {
        "functions": len(behaviors),
        "production_functions": len(prod),
        "raising": sum(1 for b in behaviors if b.raises),
        "asserting": sum(1 for b in behaviors if b.asserts > 0),
        "mutating": sum(1 for b in behaviors if b.mutates_self),
        "validating": sum(1 for b in behaviors if b.validates),
        "top_raises": [
            {"id": b.id, "raises": sorted(b.raises)}
            for b in sorted(behaviors, key=lambda x: len(x.raises), reverse=True)
            if b.raises
        ][:10],
    }


def behavior_artifact(behaviors: list[FuncBehavior], now: float = 0.0) -> dict[str, Any]:
    s = behavior_summary(behaviors)
    lines = [
        f"L4 behavior (best-effort AST): {s['raising']} raising, {s['asserting']} "
        f"asserting, {s['mutating']} mutating-self, {s['validating']} validating "
        f"({s['production_functions']}/{s['functions']} production)"
    ]
    notable = sorted(behaviors, key=lambda x: (len(x.raises), x.asserts), reverse=True)
    for b in notable:
        if not b.raises and not b.asserts and not b.mutates_self:
            continue
        tags = []
        if b.raises:
            tags.append("raises:" + ",".join(sorted(b.raises)))
        if b.asserts:
            tags.append(f"asserts:{b.asserts}")
        if b.mutates_self:
            tags.append("mutates-self")
        if b.validates:
            tags.append("validates")
        lines.append(f"{b.id}  {' '.join(tags)}")
    return {
        "id": "L4:behavior",
        "content": "\n".join(lines[:60]),
        "location": "(behavior)",
        "level": 4,
        "relevance": 0.75,
        "kind": "behavior",
        "freshness": 1.0,
        "timestamp": int(now),
    }
