# Benchmark (P2): selección de evidencia contra gold

> Micro-benchmark con fixtures sintéticos de contenido realista y gold
definido a mano (sin `supports` declarado, para no ser circular). Mide
si la selección de argos recupera el gold y a qué costo, frente a
baselines simples, y el aporte de componentes (embedding vs léxico vs L3).
Honesto: esto NO es validación sobre repos reales con etiquetado amplio;
calibración de confianza (Brier) queda pendiente.

| fixture | método | precision | recall | tokens | argos_coverage | complete |
|---|---|---|---|---|---|---|
| auth_project | argos(embed) | 1.0 | 0.333 | 21 | 1.00 | True |
| auth_project | argos(lex) | 0.0 | 0.0 | 100 | - | - |
| auth_project | argos(noL3) | 1.0 | 0.333 | 21 | - | - |
| auth_project | full_read | 0.75 | 1.0 | 100 | - | - |
| auth_project | lexical_topk | 1.0 | 1.0 | 79 | - | - |
| auth_project | random_k | 0.833 | 0.833 | 75 | - | - |
| math_lib | argos(embed) | 0.75 | 0.75 | 41 | 1.00 | True |
| math_lib | argos(lex) | 0.0 | 0.0 | 66 | - | - |
| math_lib | argos(noL3) | 0.75 | 0.75 | 41 | - | - |
| math_lib | full_read | 0.667 | 1.0 | 66 | - | - |
| math_lib | lexical_topk | 1.0 | 1.0 | 45 | - | - |
| math_lib | random_k | 0.75 | 0.75 | 45 | - | - |

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

- argos(embed) alcanza recall medio **0.54** vs
  full_read **1.00**, pero leyendo **31** tokens vs
  **83** (≈37% del costo).
- La cobertura *surrogate* de argos llega a θ con 1–2 artefactos y declara
  `complete`, pero el recall contra gold queda bajo → **la cobertura
  surrogate está sobreconfiada** (miscalibración). Esta es exactamente la
  limitación que un benchmark debe señalar: el número de cobertura del
  modelo no es, aún, un predictor fiel del recall real.
- `lexical_topk` (baseline trivial) iguala el recall de full_read a menor
  costo que éste; argos debe cerrar la brecha de recall sin perder su
  ventaja de costo para ser competitivo.
