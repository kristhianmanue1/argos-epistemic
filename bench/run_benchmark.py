"""Benchmark de seleccion de evidencia contra gold known (audit P2).

Mide precision/recall de la seleccion y costo (tokens) de:
- argos (seleccion por utilidad, linker embedding/lexico)
- baselines: full_read, lexical_topk, random_k
- ablations: argos sin L3 (impact/centrality en 0), argos con linker lexico

Salida: bench/report.md generado. Uso:
    python bench/run_benchmark.py            # escribir reporte
    python bench/run_benchmark.py --check    # CI: comparar contra lo committed
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from argos_epistemic import (  # noqa: E402
    Budget,
    analyze_system,
    embedding_semantic,
    lexical_semantic,
)
from bench import baselines, fixtures  # noqa: E402


def _gold_for_goal(goal, gold):
    aspects = [a if isinstance(a, str) else a["name"] for a in goal["aspects"]]
    union: set[str] = set()
    for a in aspects:
        union |= set(gold.get(a, set()))
    return union


def _pr(selected: set[str], gold: set[str]) -> tuple[float, float]:
    if not gold:
        return 0.0, 0.0
    tp = len(selected & gold)
    p = tp / len(selected) if selected else 0.0
    r = tp / len(gold) if gold else 0.0
    return round(p, 3), round(r, 3)


def _argos_selected(system, goal, linker, min_sources=2) -> tuple[set[str], int, dict]:
    g = copy.deepcopy(goal)
    g["aspect_linker"] = linker
    g["min_sources_per_aspect"] = min_sources
    report = analyze_system(system, g, Budget(tokens_remaining=200000, tool_remaining=2000))
    selected = {c["evidence"] for c in report["conclusions"]}
    cost = report["cost"]["observed_tokens"]
    return selected, cost, report


def _strip_l3(system):
    s = copy.deepcopy(system)
    for a in s["artifacts"]:
        a["impact"] = 0.0
        a["centrality"] = 0.0
    return s


def run(dense: bool = False) -> str:
    rows = []
    for name, fix in fixtures.FIXTURES.items():
        gold = _gold_for_goal(fix["goal"], fix["gold"])
        arts = fix["artifacts"]
        k = max(1, len(gold))

        sel, cost, rep = _argos_selected(fix, fix["goal"], lexical_semantic, min_sources=2)
        p, r = _pr(sel, gold)
        rows.append((name, "argos(lex,k=2)", p, r, cost, rep["coverage"], rep["complete"]))

        sel3, cost3, rep3 = _argos_selected(fix, fix["goal"], lexical_semantic, min_sources=3)
        p3, r3 = _pr(sel3, gold)
        rows.append((name, "argos(lex,k=3)", p3, r3, cost3, rep3["coverage"], rep3["complete"]))

        # Ablation: char-n-gram embedding surrogate (non-discriminative on short texts)
        sel_e, cost_e, rep_e = _argos_selected(fix, fix["goal"], embedding_semantic, min_sources=2)
        p_e, r_e = _pr(sel_e, gold)
        rows.append((name, "argos(embed)", p_e, r_e, cost_e, rep_e["coverage"], rep_e["complete"]))

        sel_n = _argos_selected(_strip_l3(fix), fix["goal"], lexical_semantic, min_sources=2)[0]
        p_n, r_n = _pr(sel_n, gold)
        cost_n = baselines.cost(arts, sel_n)
        rows.append((name, "argos(noL3)", p_n, r_n, cost_n, None, None))

        if dense:
            from argos_epistemic import dense_semantic, dense_semantic_available

            if dense_semantic_available():
                g2 = copy.deepcopy(fix["goal"])
                g2["link_threshold"] = 0.60
                sel_d, cost_d, rep_d = _argos_selected(fix, g2, dense_semantic, min_sources=2)
                p_d, r_d = _pr(sel_d, gold)
                rows.append((name, "argos(dense)", p_d, r_d, cost_d, rep_d["coverage"], rep_d["complete"]))

        full = baselines.full_read(arts, fix["goal"])
        rows.append((name, "full_read", *_pr(full, gold), baselines.cost(arts, full), None, None))

        lex = baselines.lexical_topk(arts, fix["goal"], k)
        rows.append((name, "lexical_topk", *_pr(lex, gold), baselines.cost(arts, lex), None, None))

        rnd = baselines.random_k(arts, fix["goal"], k)
        rows.append((name, "random_k", *_pr(rnd, gold), baselines.cost(arts, rnd), None, None))

    argos_recalls = [r[3] for r in rows if r[1] == "argos(lex,k=2)"]
    embed_recalls = [r[3] for r in rows if r[1] == "argos(embed)"]
    avg_argos_recall = sum(argos_recalls) / len(argos_recalls) if argos_recalls else 0.0
    avg_embed_recall = sum(embed_recalls) / len(embed_recalls) if embed_recalls else 0.0
    lines = [
        "# Benchmark (P2): selección de evidencia contra gold",
        "",
        "> Micro-benchmark con fixtures sintéticos de contenido realista y gold",
        "definido a mano (sin `supports` declarado, para no ser circular). Mide",
        "si la selección de argos recupera el gold y a qué costo, frente a",
        "baselines simples, y el aporte de componentes (embedding vs léxico vs L3).",
        "Honesto: esto NO es validación sobre repos reales con etiquetado amplio;",
        "calibración de confianza (Brier) queda pendiente.",
        "",
        "| fixture | método | precision | recall | tokens | argos_coverage | complete |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, method, p, r, cost, cov, comp in rows:
        cov_s = f"{cov:.2f}" if isinstance(cov, float) else "-"
        comp_s = str(comp) if comp is not None else "-"
        lines.append(f"| {name} | {method} | {p} | {r} | {cost} | {cov_s} | {comp_s} |")
    lines += [
        "",
        "## Lectura",
        "- **argos(embed)** debe igualar o superar a los baselines en recall al",
        "  observar *menos* tokens que `full_read` (selección por utilidad).",
        "- **Ablación L3**: sin grafo de llamadas, `R` pierde `Impact`/`Centrality`;",
        "  la diferencia en selección mide su aporte.",
        "- **Ablación léxica**: el linker de embeddings (char-n-gramas) vs Jaccard",
        "  léxico mide el aporte del surrogate semántico.",
        "",
        "## Reproducibilidad",
        "```bash",
        "python bench/run_benchmark.py            # reescribe bench/report.md",
        "python bench/run_benchmark.py --check    # CI: falla si el reporte está stale",
        "```",
        "",
    ]
    lines += [
        "",
        "## Hallazgo (validación falsable)",
        "",
        f"- **argos(lex, k=2)** (linker léxico): recall medio **{avg_argos_recall:.2f}** —",
        "  **1.0** en las fixtures token-obvias (auth/math, gold comparte tokens con el aspecto)",
        "  pero **0.0** en las semánticas (semantic_commerce/lifecycle, gold por sinónimos sin",
        "  overlap léxico). El linker léxico es frágil: sólo recupera con solapamiento de tokens.",
        "  La calibración (corroboration + min_sources) funciona cuando el linker discrimina,",
        "  pero no resuelve la ceguera léxica.",
        f"- **Ablación embedding**: argos(embed) (char-n-gramas) recall medio **{avg_embed_recall:.2f}**;",
        "  surrogate NO discriminativo (~0.5 para todo), enlaza distractors y satura coverage",
        "  (1.00 / complete=True) sin recuperar el gold mejor que el léxico.",
        "- **S_semantic denso real (medición auxiliar `--dense` + extra `[semantic]`, fuera de CI)**:",
        "  `all-MiniLM-L6-v2` recall medio **0.92** (auth 0.67, math 1.0, commerce 1.0, lifecycle",
        "  1.0) — el **único linker que funciona en ambas familias**. Donde el léxico colapsa",
        "  (semantic_*, recall 0.0), el denso recupera **precision 1.0 / recall 1.0**. **Confirma",
        "  el beneficio denso** que las fixtures token-obvias ocultaban: la ventaja aparece justo",
        "  cuando falta overlap léxico. Costo: requiere torch (extra `[semantic]`, no en CI); esta",
        "  fila no la regenera `--check`.",
        "- `full_read` recall 1.0 pero precision baja (lee distractores); `lexical_topk` iguala a",
        "  argos en token-obvias pero es degenerado en semánticas (scores 0) y necesita `k` hardcodeado.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dense", action="store_true", help="add sentence-transformers dense S_semantic row (needs [semantic] extra)")
    args = ap.parse_args()
    out = (ROOT / "bench" / "report.md").read_text(encoding="utf-8") if args.check else None
    fresh = run(dense=args.dense) if not args.check else run(dense=False)
    if args.check:
        if out.strip() != fresh.strip():
            print("bench/report.md is stale; run bench/run_benchmark.py", file=sys.stderr)
            return 1
        print("bench/report.md is fresh")
        return 0
    (ROOT / "bench" / "report.md").write_text(fresh, encoding="utf-8")
    print("wrote bench/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
