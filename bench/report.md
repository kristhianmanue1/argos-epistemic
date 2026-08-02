# Benchmark (P2): selección de evidencia contra gold

> Micro-benchmark con fixtures sintéticos de contenido realista y gold
definido a mano (sin `supports` declarado, para no ser circular). Mide
si la selección de argos recupera el gold y a qué costo, frente a
baselines simples, y el aporte de componentes (embedding vs léxico vs L3).
Honesto: esto NO es validación sobre repos reales con etiquetado amplio;
calibración de confianza (Brier) queda pendiente.

| fixture | método | precision | recall | tokens | argos_coverage | complete |
|---|---|---|---|---|---|---|
| auth_project | argos(lex,k=2) | 1.0 | 1.0 | 100 | 0.83 | False |
| auth_project | argos(lex,k=3) | 1.0 | 1.0 | 100 | 0.83 | False |
| auth_project | argos(embed) | 0.75 | 0.5 | 45 | 1.00 | True |
| auth_project | argos(noL3) | 1.0 | 1.0 | 79 | - | - |
| auth_project | full_read | 0.75 | 1.0 | 100 | - | - |
| auth_project | lexical_topk | 1.0 | 1.0 | 79 | - | - |
| auth_project | random_k | 0.833 | 0.833 | 75 | - | - |
| math_lib | argos(lex,k=2) | 1.0 | 1.0 | 66 | 0.67 | False |
| math_lib | argos(lex,k=3) | 1.0 | 1.0 | 66 | 0.67 | False |
| math_lib | argos(embed) | 0.8 | 1.0 | 55 | 1.00 | True |
| math_lib | argos(noL3) | 1.0 | 1.0 | 45 | - | - |
| math_lib | full_read | 0.667 | 1.0 | 66 | - | - |
| math_lib | lexical_topk | 1.0 | 1.0 | 45 | - | - |
| math_lib | random_k | 0.75 | 0.75 | 45 | - | - |
| semantic_commerce | argos(lex,k=2) | 0.0 | 0.0 | 123 | 0.00 | False |
| semantic_commerce | argos(lex,k=3) | 0.0 | 0.0 | 123 | 0.00 | False |
| semantic_commerce | argos(embed) | 0.75 | 0.5 | 55 | 1.00 | True |
| semantic_commerce | argos(noL3) | 0.0 | 0.0 | 0 | - | - |
| semantic_commerce | full_read | 0.75 | 1.0 | 123 | - | - |
| semantic_commerce | lexical_topk | 1.0 | 1.0 | 101 | - | - |
| semantic_commerce | random_k | 0.667 | 0.667 | 93 | - | - |
| semantic_lifecycle | argos(lex,k=2) | 0.0 | 0.0 | 123 | 0.00 | False |
| semantic_lifecycle | argos(lex,k=3) | 0.0 | 0.0 | 123 | 0.00 | False |
| semantic_lifecycle | argos(embed) | 0.5 | 0.333 | 47 | 1.00 | True |
| semantic_lifecycle | argos(noL3) | 0.0 | 0.0 | 0 | - | - |
| semantic_lifecycle | full_read | 0.75 | 1.0 | 123 | - | - |
| semantic_lifecycle | lexical_topk | 1.0 | 1.0 | 103 | - | - |
| semantic_lifecycle | random_k | 0.667 | 0.667 | 94 | - | - |

## Lectura
- **argos(embed)** debe igualar o superar a los baselines en recall al
  observar *menos* tokens que `full_read` (selección por utilidad).
- **Ablación L3**: sin grafo de llamadas, `R` pierde `Impact`/`Centrality`;
  la diferencia en selección mide su aporte.
- **Ablación léxica**: el linker de embeddings (char-n-gramas) vs Jaccard
  léxico mide el aporte del surrogate semántico.

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
- **Ablación embedding**: argos(embed) (char-n-gramas) recall medio **0.58**;
  surrogate NO discriminativo (~0.5 para todo), enlaza distractors y satura coverage
  (1.00 / complete=True) sin recuperar el gold mejor que el léxico.
- **S_semantic denso real (medición auxiliar `--dense` + extra `[semantic]`, fuera de CI)**:
  `all-MiniLM-L6-v2` recall medio **0.92** (auth 0.67, math 1.0, commerce 1.0, lifecycle
  1.0) — el **único linker que funciona en ambas familias**. Donde el léxico colapsa
  (semantic_*, recall 0.0), el denso recupera **precision 1.0 / recall 1.0**. **Confirma
  el beneficio denso** que las fixtures token-obvias ocultaban: la ventaja aparece justo
  cuando falta overlap léxico. Costo: requiere torch (extra `[semantic]`, no en CI); esta
  fila no la regenera `--check`.
- `full_read` recall 1.0 pero precision baja (lee distractores); `lexical_topk` iguala a
  argos en token-obvias pero es degenerado en semánticas (scores 0) y necesita `k` hardcodeado.
