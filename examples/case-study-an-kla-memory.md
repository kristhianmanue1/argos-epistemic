# Caso de estudio: an-kla-memory (tercerizado)

> Generado por `examples/regenerate_case_studies.py`. Evaluación cruzada entre repositorios distintos con dependencia operativa declarada. Fuente `https://github.com/kristhianmanue1/an-kla-memory.git`, revisión completa `f28341ea872f221d7462b6b2bb32b8c1db68ac28`, dirty=`false`.

Objetivo `G=auditoria-memoria`, aspectos `['memory', 'write', 'retrieval', 'canonical', 'test']`. `independence_class=operational_dependency`, perfil semántico explícito `minilm-v1`.

## Extracción

- Artefactos: **97** (nivel `{0: 8, 1: 1, 2: 6, 3: 1, 4: 59, 5: 22}`, tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 6, 'doc': 49, 'code': 17, 'test': 22}`).
- Grafo L3 (producción): 364 nodos / 673 aristas (137 producción). Los tests se excluyen del cálculo de Impact (sesgo corregido). Top impacto: main (0.89), commit_write_plan (0.368), apply_upgrade (0.287), build_index (0.235).
- Comportamiento L4 (Σ_4): 59 levantan, 4 asserts, 15 mutan, 21 validan.

## Reporte

```text
evidence_count  : 97
proposition_count: 99
coverage        : 0.0
residual_risk   : 1.0
complete        : False
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'memory': 0.0, 'write': 0.0, 'retrieval': 0.0, 'canonical': 0.0, 'test': 0.0}
```

## Interpretación y riesgo residual

- Independiente en repositorio, pero an-kla-memory es **dependencia del propio argos** (es la memoria local que usa este repo): no es totalmente ajeno.
- L4 aquí es particularmente informativo: la lib implementa gobernanza de escritura (write-policy) y canonicalización JSON, por eso muchas funciones levantan `ValueError` (validates) y el top de impacto L3 cae sobre `commit_write_plan`/`main` (path crítico de la escritura gobernada).
- L3/L4 simbólicos best-effort (Python AST); `S_semantic` surrogate léxico. Sin L5 dinámico sobre terceros por defecto.

_Manifest de entradas fijadas: `sha256:0388de03b5dff81319aecf0257032e0e94e8b856e2685bbd14f3a060c801bf1d` (perfil semántico, revisión del target, evaluador, frescura y presupuesto)._
