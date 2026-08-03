# Benchmark (P2): selección de evidencia contra gold

> Micro-benchmark con fixtures sintéticos de contenido realista y gold
definido a mano (sin `supports` declarado, para no ser circular). Mide
si la selección de argos recupera el gold y a qué costo, frente a
baselines simples, y el aporte de componentes (embedding vs léxico vs L3).
Honesto: esto NO es validación sobre repos reales con etiquetado amplio;
calibración de confianza (Brier) queda pendiente.

| fixture | método | precision | recall | tokens | argos_coverage | complete | brier |
|---|---|---|---|---|---|---|---|
| auth_project | argos(lex,k=2) | 1.0 | 1.0 | 100 | 0.00 | False | 0.124 |
| auth_project | argos(lex,k=3) | 1.0 | 1.0 | 100 | 0.00 | False | 0.124 |
| auth_project | argos(embed) | 0.75 | 1.0 | 100 | 0.00 | False | 0.231 |
| auth_project | argos(noL3) | 1.0 | 1.0 | 79 | - | - | - |
| auth_project | full_read | 0.75 | 1.0 | 100 | - | - | - |
| auth_project | lexical_topk | 1.0 | 1.0 | 79 | - | - | - |
| auth_project | random_k | 0.833 | 0.833 | 75 | - | - | - |
| math_lib | argos(lex,k=2) | 1.0 | 1.0 | 66 | 0.00 | False | 0.085 |
| math_lib | argos(lex,k=3) | 1.0 | 1.0 | 66 | 0.00 | False | 0.085 |
| math_lib | argos(embed) | 0.667 | 1.0 | 66 | 0.00 | False | 0.268 |
| math_lib | argos(noL3) | 1.0 | 1.0 | 45 | - | - | - |
| math_lib | full_read | 0.667 | 1.0 | 66 | - | - | - |
| math_lib | lexical_topk | 1.0 | 1.0 | 45 | - | - | - |
| math_lib | random_k | 0.75 | 0.75 | 45 | - | - | - |
| semantic_commerce | argos(lex,k=2) | 0.0 | 0.0 | 123 | 0.00 | False | - |
| semantic_commerce | argos(lex,k=3) | 0.0 | 0.0 | 123 | 0.00 | False | - |
| semantic_commerce | argos(embed) | 0.75 | 1.0 | 123 | 0.00 | False | 0.366 |
| semantic_commerce | argos(noL3) | 0.0 | 0.0 | 0 | - | - | - |
| semantic_commerce | full_read | 0.75 | 1.0 | 123 | - | - | - |
| semantic_commerce | lexical_topk | 1.0 | 1.0 | 101 | - | - | - |
| semantic_commerce | random_k | 0.667 | 0.667 | 93 | - | - | - |
| semantic_lifecycle | argos(lex,k=2) | 0.0 | 0.0 | 123 | 0.00 | False | - |
| semantic_lifecycle | argos(lex,k=3) | 0.0 | 0.0 | 123 | 0.00 | False | - |
| semantic_lifecycle | argos(embed) | 0.75 | 1.0 | 123 | 0.00 | False | 0.366 |
| semantic_lifecycle | argos(noL3) | 0.0 | 0.0 | 0 | - | - | - |
| semantic_lifecycle | full_read | 0.75 | 1.0 | 123 | - | - | - |
| semantic_lifecycle | lexical_topk | 1.0 | 1.0 | 103 | - | - | - |
| semantic_lifecycle | random_k | 0.667 | 0.667 | 94 | - | - | - |

## Lectura
- **argos(embed)** debe igualar o superar a los baselines en recall al
  observar *menos* tokens que `full_read` (selección por utilidad).
- **Ablación L3**: sin grafo de llamadas, `R` pierde `Impact`/`Centrality`;
  la diferencia en selección mide su aporte.
- **Ablación léxica**: el linker de embeddings (char-n-gramas) vs Jaccard
  léxico mide el aporte del surrogate semántico.
- **Brier** (sólo variantes argos, que emiten `confidence` por conclusión):
  calibra la confianza frente al gold. `0.0` = calibrado; alto implica
  enlaces confiantes fuera del gold (sobreconfianza) o incertidumbre sobre
  gold real (subconfianza). P/R no lo detecta: dos métodos con recall 1.0
  pueden tener Brier muy distinto.

## Reproducibilidad
```bash
python bench/run_benchmark.py            # reescribe bench/report.md
python bench/run_benchmark.py --check    # CI: falla si el reporte está stale
```


## Hallazgo (validación falsable)

- **argos(lex, k=2)** (linker léxico): recall medio **0.50** —
  **1.0** en las fixtures token-obvias (auth/math, gold comparte tokens con el aspecto)
  pero **0.0** en las semánticas (semantic_commerce/lifecycle, gold por sinónimos sin
  overlap léxico). El linker léxico es frágil: sólo recupera con solapamiento de tokens.
  La calibración (corroboration + min_sources) funciona cuando el linker discrimina,
  pero no resuelve la ceguera léxica.
- **Ablación embedding**: argos(embed) (char-n-gramas) recall medio **1.00**;
  surrogate NO discriminativo (~0.5 para todo), enlaza distractors. Estos enlaces son
  `mentions`: amplían recuperación, pero ya no saturan coverage ni producen complete=True
  sin una relación probatoria explícita o verificación dinámica.
- **S_semantic denso real (medición auxiliar `--dense` + extra `[semantic]`, fuera de CI)**:
  `all-MiniLM-L6-v2` recall medio **0.92** (auth 0.67, math 1.0, commerce 1.0, lifecycle
  1.0) — el **único linker que funciona en ambas familias**. Donde el léxico colapsa
  (semantic_*, recall 0.0), el denso recupera **precision 1.0 / recall 1.0**. **Confirma
  el beneficio denso** que las fixtures token-obvias ocultaban: la ventaja aparece justo
  cuando falta overlap léxico. Costo: requiere torch (extra `[semantic]`, no en CI); esta
  fila no la regenera `--check`.
- `full_read` recall 1.0 pero precision baja (lee distractores); `lexical_topk` iguala a
  argos en token-obvias pero es degenerado en semánticas (scores 0) y necesita `k` hardcodeado.
- **Brier (calibración de confianza)**: argos(lex,k=2) medio **0.105**;
  argos(embed) medio **0.308**. El linker léxico, al no enlazar
  distractores en token-obvias, es más calibrado donde recupera; el surrogate de
  char-n-gramas sobre-enlaza (confianza alta fuera del gold) y por eso su Brier sube.
  Sigue siendo un micro-benchmark: la calibración real requiere `confidence` por
  método sobre repos con gold amplio (no sólo etiqueta binaria por aspecto).
