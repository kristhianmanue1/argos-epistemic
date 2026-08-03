# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **68**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25. Perfil semántico explícito: `char-ngram-v1`.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **35** (por nivel `{0: 3, 1: 1, 2: 4, 3: 1, 4: 25, 5: 1}`, por tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 4, 'doc': 6, 'code': 21, 'test': 1}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 246 nodos / 361 aristas (171 producción). Top impacto: main (0.641), _argos_md (0.624), _third_party_md (0.618), analyze_path (0.6).
- Comportamiento L4 (AST best-effort, Σ_4): 3 fn levantan, 68 con asserts, 9 mutan self, 1 validan (181/258 producción).

## Reporte

```text
evidence_count  : 35
proposition_count: 16
conflict_count  : 2
coverage        : 0.5833
residual_risk   : 0.0
complete        : False
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'algorithm': 0.6667, 'config': 1.0, 'test': 0.1667, 'doc': 0.5}
cost            : estimated=38101 observed=38101
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por aspecto sobre proposiciones; la evidencia irrelevante aporta cero. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **Identidad Git no incrustada**: incluir el commit del propio archivo generado crearía una autorreferencia imposible de estabilizar. La identidad del evaluador pertenecerá al manifest externo del bundle.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.
- **Frescura normalizada**: este artefacto fija `freshness=1.0` y `timestamp=0` para no depender del `mtime` asignado por cada checkout; el pipeline normal conserva y evalúa los timestamps reales.

_Generado desde HEAD del pipeline. raw report: `{"evidence_count": 35, "proposition_count": 16, "coverage": 0.5833, "residual_risk": 0.0, "complete": false}`_
