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

- **argos(lex, k=2)** (linker léxico + corroboration): recall medio
  **1.00**, precision media alta, a **83** tokens
  (≈100% de full_read). En estos fixtures
  alcanza **precision y recall 1.0** (sin leer `util.py`/`colors.py`/`noise.py`)
  → la calibración (corroboration + min_sources) funciona cuando el linker discrimina.
- **Ablación embedding**: argos(embed) cae a recall **0.75** porque el
  surrogate de char-n-gramas es NO discriminativo (~0.5 para todo, liga
  `util.py` a 'auth'). **La palanca real es la fidelidad de S_semantic**, no
  más knobs de calibración: un embedding denso real (sentence-transformers/API)
  es el siguiente paso para que la calibración se traduzca en recall sobre
  contenido menos obvio.
- `full_read` tiene recall 1.0 pero precision baja (lee basura); `lexical_topk`
  iguala a argos pero necesita `k` hardcodeado, argos lo decide adaptativamente.
