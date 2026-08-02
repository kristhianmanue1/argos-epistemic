# Caso de estudio: markupsafe (tercerizado)

> Generado por `examples/regenerate_case_studies.py`. Validación **independiente** sobre un repo público. Fuente `https://github.com/pallets/markupsafe.git`, b2e4d9c David Lord (Sat Sep 27 11:45:34 2025 -0700).

Objetivo `G=seguridad-y-refactor`, aspectos `['escape', 'native', 'exception', 'test', 'config']`.

## Extracción

- Artefactos: **29** (nivel `{0: 1, 1: 1, 2: 11, 3: 1, 4: 8, 5: 7}`, tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'doc': 4, 'config': 11, 'code': 4, 'test': 7}`).
- Grafo L3 (producción): 88 nodos / 78 aristas (52 producción). Los tests se excluyen del cálculo de Impact (sesgo corregido). Top impacto: __radd__ (0.098), format_field (0.098), escape (0.078), escape_silent (0.078).
- Comportamiento L4 (Σ_4): 6 levantan, 25 asserts, 4 mutan, 4 validan.

## Reporte

```text
evidence_count  : 29
proposition_count: 13
coverage        : 0.6333
residual_risk   : 0.14
complete        : False
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'escape': 0.8333, 'native': 0.0, 'exception': 0.8333, 'test': 0.5, 'config': 1.0}
```

## Interpretación y riesgo residual

- Independiente: analizador y analizado son proyectos distintos.
- L3 es simbólico best-effort (no ve C-extensions nativas); `S_semantic` es surrogate léxico.
- Sin L5 dinámico sobre terceros por defecto (confianza + dependencias de build); el extractor está disponible bajo `analyze_path(run_dynamic=True)`.
