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

from argos_epistemic import Budget, analyze_system, embedding_semantic, lexical_semantic

from bench import baselines, fixtures


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


def _argos_selected(system, goal, linker) -> tuple[set[str], int, dict]:
    g = copy.deepcopy(goal)
    g["aspect_linker"] = linker
    report = analyze_system(system, g, Budget(tokens_remaining=200000, tool_remaining=2000))
    # selected = artifacts whose evidence was extracted (id in evidence via conclusions' evidence)
    selected = {c["evidence"] for c in report["conclusions"]}
    cost = report["cost"]["observed_tokens"]
    return selected, cost, report


def _strip_l3(system):
    s = copy.deepcopy(system)
    for a in s["artifacts"]:
        a["impact"] = 0.0
        a["centrality"] = 0.0
    return s


def run() -> str:
    rows = []
    for name, fix in fixtures.FIXTURES.items():
        gold = _gold_for_goal(fix["goal"], fix["gold"])
        arts = fix["artifacts"]
        n = len(arts)
        k = max(1, len(gold))

        sel, cost, rep = _argos_selected(fix, fix["goal"], embedding_semantic)
        p, r = _pr(sel, gold)
        rows.append((name, "argos(embed)", p, r, cost, rep["coverage"], rep["complete"]))

        sel_l, cost_l, _ = _argos_selected(fix, fix["goal"], lexical_semantic)
        p_l, r_l = _pr(sel_l, gold)
        rows.append((name, "argos(lex)", p_l, r_l, cost_l, None, None))

        sel_n = _argos_selected(_strip_l3(fix), fix["goal"], embedding_semantic)[0]
        p_n, r_n = _pr(sel_n, gold)
        cost_n = baselines.cost(arts, sel_n)
        rows.append((name, "argos(noL3)", p_n, r_n, cost_n, None, None))

        full = baselines.full_read(arts, fix["goal"])
        rows.append((name, "full_read", *_pr(full, gold), baselines.cost(arts, full), None, None))

        lex = baselines.lexical_topk(arts, fix["goal"], k)
        rows.append((name, "lexical_topk", *_pr(lex, gold), baselines.cost(arts, lex), None, None))

        rnd = baselines.random_k(arts, fix["goal"], k)
        rows.append((name, "random_k", *_pr(rnd, gold), baselines.cost(arts, rnd), None, None))

    argos_recalls = [r[3] for r in rows if r[1] == "argos(embed)"]
    argos_costs = [r[4] for r in rows if r[1] == "argos(embed)"]
    full_costs = [r[4] for r in rows if r[1] == "full_read"]
    avg_argos_recall = sum(argos_recalls) / len(argos_recalls) if argos_recalls else 0.0
    avg_argos_cost = sum(argos_costs) / len(argos_costs) if argos_costs else 0.0
    avg_full_cost = sum(full_costs) / len(full_costs) if full_costs else 1.0
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
        f"- argos(embed) alcanza recall medio **{avg_argos_recall:.2f}** vs",
        f"  full_read **1.00**, leyendo **{avg_argos_cost:.0f}** tokens vs",
        f"  **{avg_full_cost:.0f}** (≈{avg_argos_cost / max(1, avg_full_cost) * 100:.0f}% del costo).",
        "- Con la calibración por corrobación (una sola fuente no satura el aspecto)",
        "  el recall subió respecto al baseline sin calibración, y en `math_lib`",
        "  argos EMPATA el recall de full_read a MENOR costo. Queda un gap residual",
        "  en `auth_project`: la cobertura surrogate aún declara `complete` antes de",
        "  recoger todo el gold → la calibración ayuda pero no elimina la",
        "  sobreconfianza. Próximo: ajustar θ por aspecto o calibrar contra gold.",
        "- `lexical_topk` sigue siendo un baseline fuerte; argos debe superar su",
        "  recall sin renunciar a su ventaja de costo.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = (ROOT / "bench" / "report.md").read_text(encoding="utf-8") if args.check else None
    fresh = run()
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
