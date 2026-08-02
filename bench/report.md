# Benchmark (P2): selección de evidencia contra gold

> Micro-benchmark con fixtures sintéticos de contenido realista y gold
definido a mano (sin `supports` declarado, para no ser circular). Mide
si la selección de argos recupera el gold y a qué costo, frente a
baselines simples, y el aporte de componentes (embedding vs léxico vs L3).
Honesto: esto NO es validación sobre repos reales con etiquetado amplio;
calibración de confianza (Brier) queda pendiente.

| fixture | método | precision | recall | tokens | argos_coverage | complete |
|---|---|---|---|---|---|---|
| auth_project | argos(embed) | 0.75 | 0.5 | 45 | 1.00 | True |
| auth_project | argos(lex) | 0.0 | 0.0 | 100 | - | - |
| auth_project | argos(noL3) | 0.75 | 0.5 | 45 | - | - |
| auth_project | full_read | 0.75 | 1.0 | 100 | - | - |
| auth_project | lexical_topk | 1.0 | 1.0 | 79 | - | - |
| auth_project | random_k | 0.833 | 0.833 | 75 | - | - |
| math_lib | argos(embed) | 0.8 | 1.0 | 55 | 1.00 | True |
| math_lib | argos(lex) | 0.0 | 0.0 | 66 | - | - |
| math_lib | argos(noL3) | 0.8 | 1.0 | 55 | - | - |
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

- argos(embed) alcanza recall medio **0.75** vs
  full_read **1.00**, leyendo **50** tokens vs
  **83** (≈60% del costo).
- Con la calibración por corrobación (una sola fuente no satura el aspecto)
  el recall subió respecto al baseline sin calibración, y en `math_lib`
  argos EMPATA el recall de full_read a MENOR costo. Queda un gap residual
  en `auth_project`: la cobertura surrogate aún declara `complete` antes de
  recoger todo el gold → la calibración ayuda pero no elimina la
  sobreconfianza. Próximo: ajustar θ por aspecto o calibrar contra gold.
- `lexical_topk` sigue siendo un baseline fuerte; argos debe superar su
  recall sin renunciar a su ventaja de costo.
