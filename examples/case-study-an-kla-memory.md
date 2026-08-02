# Caso de estudio: an-kla-memory (tercerizado)

> Generado por `examples/regenerate_case_studies.py`. Validación **independiente** sobre un repo público. Fuente `https://github.com/kristhianmanue1/an-kla-memory.git`, 67f6ee4 KRISTHIAN MANUEL (Sat Aug 1 19:54:55 2026 -0600).

Objetivo `G=auditoria-memoria`, aspectos `['memory', 'write', 'retrieval', 'canonical', 'test']`.

## Extracción

- Artefactos: **56** (nivel `{0: 5, 1: 1, 2: 3, 3: 1, 4: 32, 5: 14}`, tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 3, 'doc': 23, 'code': 13, 'test': 14}`).
- Grafo L3 (producción): 260 nodos / 499 aristas (113 producción). Los tests se excluyen del cálculo de Impact (sesgo corregido). Top impacto: main (0.839), commit_write_plan (0.375), main (0.268), handle (0.259).
- Comportamiento L4 (Σ_4): 51 levantan, 2 asserts, 8 mutan, 13 validan.

## Reporte

```text
evidence_count  : 49
proposition_count: 55
coverage        : 0.8
residual_risk   : 0.0
complete        : True
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'memory': 1.0, 'write': 0.6667, 'retrieval': 1.0, 'canonical': 0.3333, 'test': 1.0}
```

## Interpretación y riesgo residual

- Independiente en repositorio, pero an-kla-memory es **dependencia del propio argos** (es la memoria local que usa este repo): no es totalmente ajeno.
- L4 aquí es particularmente informativo: la lib implementa gobernanza de escritura (write-policy) y canonicalización JSON, por eso muchas funciones levantan `ValueError` (validates) y el top de impacto L3 cae sobre `commit_write_plan`/`main` (path crítico de la escritura gobernada).
- L3/L4 simbólicos best-effort (Python AST); `S_semantic` surrogate léxico. Sin L5 dinámico sobre terceros por defecto.
