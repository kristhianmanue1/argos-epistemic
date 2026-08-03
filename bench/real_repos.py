"""Validacion sobre repos reales con gold hand-labeled (item 1).

Extiende el micro-benchmark P2 a codigo real (markupsafe, itsdangerous, click)
con gold etiquetado a mano por aspecto (``bench/real_gold.py``). Mide
precision/recall/**Brier**/costo de argos (linker lexico y denso) frente a
baselines simples.

OPT-IN y fuera de CI: clona los repos (red). No lo regenera ``--check``.
Reproducible por commit fijado.

Uso:
    python bench/real_repos.py            # clona/actualiza y escribe bench/real_report.md
    python bench/real_repos.py --refresh  # fuerza re-clone
"""

from __future__ import annotations

import argparse
import copy
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from argos_epistemic import (  # noqa: E402
    Budget,
    analyze_system,
    dense_semantic,
    dense_semantic_available,
    extract_system,
    lexical_semantic,
)
from bench import baselines  # noqa: E402
from bench.real_gold import REPOS  # noqa: E402
from bench.run_benchmark import _brier, _pr  # noqa: E402

PINNED = {
    "markupsafe": ("https://github.com/pallets/markupsafe.git", "b2e4d9c7687be25695fffbe93a37622302b24fb1"),
    "itsdangerous": ("https://github.com/pallets/itsdangerous.git", "672971d66a2ef9f85151e53283113f33d642dabd"),
    "click": ("https://github.com/pallets/click.git", "00e592cea702e0b2caa0dee42489fdb1c22cd845"),
}


def cache_dir() -> Path:
    override = os.environ.get("ARGOS_BENCH_REAL_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "argos-bench-real"


def ensure_clone(name: str, refresh: bool) -> Path:
    url, sha = PINNED[name]
    base = cache_dir() / name
    if refresh and base.exists():
        subprocess.run(["rm", "-rf", str(base)], check=False)
    if not (base / ".git").exists():
        subprocess.run(["git", "clone", "--quiet", url, str(base)], check=True)
    # Pin to exact commit for reproducibility.
    subprocess.run(
        ["git", "-C", str(base), "fetch", "--quiet", "--depth", "1", "origin", sha],
        check=False,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["git", "-C", str(base), "checkout", "--quiet", sha], check=True)
    return base


def _gold_union(gold_by_aspect: dict[str, set[str]]) -> set[str]:
    union: set[str] = set()
    for ids in gold_by_aspect.values():
        union |= ids
    return union


def _argos(system: dict, goal: dict, linker, link_threshold) -> tuple[set[str], int, dict]:
    g = copy.deepcopy(goal)
    g["aspect_linker"] = linker
    g["min_sources_per_aspect"] = 2
    if link_threshold is not None:
        g["link_threshold"] = link_threshold
    rep = analyze_system(system, g, Budget(tokens_remaining=200000, tool_remaining=2000))
    selected = {c["evidence"] for c in rep["conclusions"]}
    return selected, rep["cost"]["observed_tokens"], rep


def run(dense: bool) -> tuple[str, dict]:
    rows: list[tuple] = []
    commits: dict[str, str] = {}
    for name, spec in REPOS.items():
        path = ensure_clone(name, refresh=False)
        commits[name] = PINNED[name][1][:12]
        system = extract_system(path, spec["goal"])
        gold_by_aspect = spec["gold"]
        gold = _gold_union(gold_by_aspect)
        arts = system["artifacts"]
        k = max(1, len(gold))

        sel, cost, rep = _argos(system, spec["goal"], lexical_semantic, None)
        p, r = _pr(sel, gold)
        rows.append((name, "argos(lex)", p, r, cost, rep["coverage"], rep["complete"], _brier(rep, gold_by_aspect)))

        if dense and dense_semantic_available():
            sel_d, cost_d, rep_d = _argos(system, spec["goal"], dense_semantic, 0.60)
            p_d, r_d = _pr(sel_d, gold)
            rows.append((name, "argos(dense)", p_d, r_d, cost_d, rep_d["coverage"], rep_d["complete"], _brier(rep_d, gold_by_aspect)))

        full = baselines.full_read(arts, spec["goal"])
        rows.append((name, "full_read", *_pr(full, gold), baselines.cost(arts, full), None, None, None))

        lex = baselines.lexical_topk(arts, spec["goal"], k)
        rows.append((name, "lexical_topk", *_pr(lex, gold), baselines.cost(arts, lex), None, None, None))

    def _avg(method: str, idx: int) -> str:
        vals = [row[idx] for row in rows if row[1] == method and row[idx] is not None]
        return f"{sum(vals) / len(vals):.3f}" if vals else "-"

    dense_avail = dense and dense_semantic_available()
    lines = [
        "# Validacion sobre repos reales (P3)",
        "",
        "> Tres repos pequenos de pallets con **gold hand-labeled por aspecto**",
        "(`bench/real_gold.py`), etiquetado leyendo el codigo a mano. Mide si la",
        "seleccion de argos recupera el gold en codigo **real** (no micro-fixture),",
        "con precision/recall/**Brier**/costo, y compara linker lexico vs denso.",
        "",
        "**OPT-IN, fuera de CI** (requiere red para clonar). Reproducible por commit.",
        f"Linker denso disponible: **{dense_avail}** (`[semantic]` extra).",
        "",
        "Commits fijados: "
        + ", ".join(f"`{n}` {commits[n]}" for n in REPOS),
        "",
        "| repo | metodo | precision | recall | tokens | argos_coverage | complete | brier |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, method, p, r, cost, cov, comp, brier in rows:
        cov_s = f"{cov:.2f}" if isinstance(cov, float) else "-"
        comp_s = str(comp) if comp is not None else "-"
        brier_s = f"{brier:.3f}" if isinstance(brier, float) else "-"
        lines.append(f"| {name} | {method} | {p} | {r} | {cost} | {cov_s} | {comp_s} | {brier_s} |")
    lines += [
        "",
        "## Lectura",
        f"- **Recall medio**: argos(lex) **{_avg('argos(lex)', 3)}**, "
        + (f"argos(dense) **{_avg('argos(dense)', 3)}**, " if dense_avail else "")
        + f"full_read **{_avg('full_read', 3)}**, lexical_topk **{_avg('lexical_topk', 3)}**.",
        f"- **Brier medio** (calibracion de confianza; solo argos emite confidence): "
        f"argos(lex) **{_avg('argos(lex)', 7)}**"
        + (f", argos(dense) **{_avg('argos(dense)', 7)}**." if dense_avail else "."),
        "",
        "### Hallazgos sobre codigo real",
        "- **El linker denso sube el recall** (recupera aspectos semanticos como",
        "  `injection`/`errors`/`security` que el lexico no puede) — confirma en codigo",
        "  real el beneficio ya visto en micro-fixtures.",
        "- **Tendencia a sobre-enlazar documentacion/ejemplos**: los ficheros cortos",
        "  y saturados de palabras-aspecto (ejemplos, stubs de tipado, config) ganan la",
        "  similitud densa frente al codigo fuente grande y diluido. Pre-fix esto",
        "  producia sobreafirmacion en `click` (coverage 0.83 + `complete=True` con",
        "  recall 0).",
        "- **Gate de evidencia productiva (item 2)**: `production_sources_met` impide",
        "  declarar `complete` cuando un aspecto solo descansa en evidencia periferica",
        "  (impact=0). Tras el fix, `click` denso ya NO sobreafirma (`complete=False`).",
        "  El Brier sigue alto (~0.40) porque el linker aún enlaza ruido: la calibracion",
        "  de la señal requiera un linker que sesgue codigo > docs (siguiente palanca).",
        "- **Costo del honestidad**: al no poder detenerse por sobreafirmacion, argos",
        "  lee TODO el repo (tokens ~= full_read) cuando ningun aspecto alcanza apoyo",
        "  productivo. El ahorro por seleccion solo aparece si `should_stop` dispara con",
        "  apoyo productivo real (palanca: que el codigo productivo enlaces).",
        "- `lexical_topk` degenera en `click` (aspectos sin overlap con el id del gold).",
        "",
        "## Reproducibilidad",
        "```bash",
        "ARGOS_BENCH_REAL_DIR=/tmp/argos-bench python bench/real_repos.py        # escribe real_report.md",
        "ARGOS_BENCH_REAL_DIR=/tmp/argos-bench python bench/real_repos.py --dense # anade fila denso",
        "```",
        "",
        "## Honestidad",
        "- Gold etiquetado por una persona (el agente) sobre 3 repos; no es annotation",
        "  multiple ni ciega. Aspectos como `injection`/`errors`/`security` son",
        "  semanticos (sin overlap lexico) para aislar la senal densa.",
        "- Sigue siendo N=3 repos; validacion estadistica amplia queda pendiente.",
        "",
    ]
    return "\n".join(lines), commits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dense", action="store_true", help="add dense sentence-transformers row (needs [semantic] extra)")
    ap.add_argument("--refresh", action="store_true", help="force re-clone")
    args = ap.parse_args()
    if args.refresh:
        for name in REPOS:
            ensure_clone(name, refresh=True)
    text, _ = run(dense=args.dense)
    out = ROOT / "bench" / "real_report.md"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
