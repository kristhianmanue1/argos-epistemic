# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **43**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **23** (por nivel `{0: 3, 1: 1, 2: 4, 3: 1, 4: 13, 5: 1}`, por tipo `{'topology': 1, 'callgraph': 1, 'config': 4, 'doc': 6, 'code': 10, 'test': 1}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 158 nodos / 226 aristas (113 producción). Top impacto: analyze_path (0.714), main (0.634), _argos_md (0.616), _markupsafe_md (0.607).

## Reporte

```text
evidence_count  : 1
proposition_count: 4
conflict_count  : 0
coverage        : 0.9
residual_risk   : 0.0
complete        : True
levels_covered  : [2]
aspect_scores   : {'algorithm': 0.9, 'config': 0.9, 'test': 0.9, 'doc': 0.9}
cost            : estimated=10 observed=10
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por aspecto sobre proposiciones; la evidencia irrelevante aporta cero. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.

_Generado desde HEAD del pipeline. raw report: `{"evidence_count": 1, "proposition_count": 4, "coverage": 0.9, "residual_risk": 0.0, "complete": true}`_
