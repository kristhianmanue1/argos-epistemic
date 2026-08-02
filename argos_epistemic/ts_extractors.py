"""Extractores L3 multi-lenguaje basados en tree-sitter (opcionales).

El MODELO es agnostico; estos son herramientas que aportan grafo de llamadas
para JavaScript/TypeScript/Go/Rust cuando los paquetes ``tree-sitter-*`` están
instalados (``pip install argos-epistemic[languages]``). Si un paquete no está
presente, su extractor no se registra y ese lenguaje queda como no-op graceful
(como cualquier otro lenguaje sin extractor).

Al igual que el extractor Python (``callgraph.py``), es verificacion simbolica
best-effort: resuelve llamadas por nombre corto y sobre-aproxima la atribucion
de llamadas a nivel de archivo. No hace analisis de tipos/flujo.
"""

from __future__ import annotations

from pathlib import Path

from .callgraph import CallGraph, register_l3_extractor


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _make_ts_extractor(get_language, suffix: str):
    def extractor(root: Path, files: list[Path]) -> CallGraph:
        from tree_sitter import Language, Parser

        try:
            language = Language(get_language())
        except Exception:
            return CallGraph()
        parser = Parser(language)
        cg = CallGraph()
        pending: list[tuple[str, str, list[str]]] = []
        for path in files:
            rel = _rel(root, path)
            try:
                src = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            tree = parser.parse(src.encode())
            funcs: list[str] = []
            calls: list[str] = []

            def walk(node, funcs, calls) -> None:
                t = node.type
                if "function" in t or "method" in t:
                    name = node.child_by_field_name("name")
                    if name is not None:
                        funcs.append(name.text.decode())
                if t == "call_expression":
                    fn = node.child_by_field_name("function")
                    if fn is not None:
                        calls.append(fn.text.decode().split(".")[-1])
                for child in node.children:
                    walk(child, funcs, calls)

            walk(tree.root_node, funcs, calls)
            for fname in funcs:
                node_id = f"{rel}::{fname}"
                cg.add_node(node_id, rel, fname)
                pending.append((node_id, rel, calls))
        for node_id, rel, calls in pending:
            for short in calls:
                targets = cg.by_short.get(short, set())
                if not targets:
                    continue
                same_module = {t for t in targets if cg.nodes[t].file == rel}
                for target in same_module or targets:
                    cg.add_edge(node_id, target)
        return cg

    return extractor


def _register_available() -> None:
    candidates = [
        (".js", "tree_sitter_javascript", "language"),
        (".jsx", "tree_sitter_javascript", "language"),
        (".ts", "tree_sitter_typescript", "language_typescript"),
        (".tsx", "tree_sitter_typescript", "language_tsx"),
        (".go", "tree_sitter_go", "language"),
        (".rs", "tree_sitter_rust", "language"),
    ]
    for suffix, module_name, attr in candidates:
        try:
            module = __import__(module_name)
        except ImportError:
            continue
        getter = getattr(module, attr, None)
        if getter is None:
            continue
        register_l3_extractor(suffix, _make_ts_extractor(getter, suffix))


_register_available()
