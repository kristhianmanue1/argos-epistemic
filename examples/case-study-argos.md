# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **82**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25. Perfil semántico explícito: `char-ngram-v1`.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **40** (por nivel `{0: 3, 1: 1, 2: 4, 3: 1, 4: 28, 5: 3}`, por tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 4, 'doc': 6, 'code': 24, 'test': 3}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 282 nodos / 431 aristas (192 producción). Top impacto: main (0.607), _argos_md (0.592), _third_party_md (0.581), analyze_path (0.565).
- Comportamiento L4 (AST best-effort, Σ_4): 17 fn levantan, 82 con asserts, 9 mutan self, 2 validan (202/294 producción).

## Reporte

```text
evidence_count  : 40
proposition_count: 19
conflict_count  : 2
coverage        : 0.5833
residual_risk   : 0.175
complete        : False
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'algorithm': 0.8333, 'config': 1.0, 'test': 0.0, 'doc': 0.5}
cost            : estimated=44004 observed=44004
inventory       : {'profile': 'legacy-first-400-v1', 'files_discovered': 46, 'files_eligible': 37, 'files_selected': 37, 'files_omitted_by_cap': 0, 'read_truncations': 9, 'bytes_discovered': 339309, 'bytes_read': 169345, 'degradations': ['content_truncated'], 'fingerprint': 'sha256:6f703296baf56d07e60eb7914969f144548b75997cb00d5cb478d60e54c2387d'}
completion      : {'procedure_complete': False, 'thresholds_met': False, 'degradations': ['content_truncated'], 'blocking_degradations': ['content_truncated'], 'reason_codes': ['threshold_not_met', 'insufficient_sources', 'missing_production_evidence', 'content_truncated', 'no_eligible_actions'], 'termination_reason': 'no_eligible_actions', 'next_actions': [{'action': 'increase_read_limit', 'reason': 'content_truncated', 'authorization_required': True}]}
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por aspecto sobre proposiciones; la evidencia irrelevante aporta cero. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **Identidad Git no incrustada**: incluir el commit del propio archivo generado crearía una autorreferencia imposible de estabilizar. La identidad del evaluador pertenecerá al manifest externo del bundle.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.
- **Frescura normalizada**: este artefacto fija `freshness=1.0` y `timestamp=0` para no depender del `mtime` asignado por cada checkout; el pipeline normal conserva y evalúa los timestamps reales.

_Generado desde HEAD del pipeline. raw report: `{"evidence_count": 40, "proposition_count": 19, "coverage": 0.5833, "residual_risk": 0.175, "complete": false}`_
