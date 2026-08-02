# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **54**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **31** (por nivel `{0: 3, 1: 1, 2: 4, 3: 1, 4: 21, 5: 1}`, por tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 4, 'doc': 7, 'code': 16, 'test': 1}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 204 nodos / 283 aristas (147 producción). Top impacto: main (0.644), _argos_md (0.63), _markupsafe_md (0.623), analyze_path (0.616).
- Comportamiento L4 (AST best-effort, Σ_4): 1 fn levantan, 54 con asserts, 9 mutan self, 0 validan (157/216 producción).

## Reporte

```text
evidence_count  : 3
proposition_count: 12
conflict_count  : 4
coverage        : 1.0
residual_risk   : 0.0
complete        : True
levels_covered  : [2, 4]
aspect_scores   : {'algorithm': 1.0, 'config': 1.0, 'test': 1.0, 'doc': 1.0}
cost            : estimated=65 observed=65
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por aspecto sobre proposiciones; la evidencia irrelevante aporta cero. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.

_Generado desde HEAD del pipeline. raw report: `{"evidence_count": 3, "proposition_count": 12, "coverage": 1.0, "residual_risk": 0.0, "complete": true}`_
