# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **992**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25. Perfil semántico explícito: `char-ngram-v1`.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **68** (por nivel `{0: 5, 1: 1, 2: 8, 3: 1, 4: 43, 5: 10}`, por tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 8, 'doc': 19, 'code': 28, 'test': 10}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 806 nodos / 1359 aristas (328 producción). Top impacto: analyze_path (0.578), main (0.535), _check_one (0.532), check_case (0.529).
- Comportamiento L4 (AST best-effort, Σ_4): 46 fn levantan, 401 con asserts, 10 mutan self, 2 validan (342/834 producción).

## Reporte

```text
evidence_count  : 68
proposition_count: 29
relations        : {'mentions': 29}
conflict_count  : 0
coverage        : 0.0
retrieval       : 0.75
structural      : 0.0
capability      : unavailable
coverage_profile: argos/claim-component-coverage-v1
residual_risk   : 1.0
complete        : False
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'algorithm': 0.0, 'config': 0.0, 'test': 0.0, 'doc': 0.0}
cost            : estimated=74317 observed=74317
inventory       : {'profile': 'legacy-first-400-v1', 'files_discovered': 72, 'files_eligible': 65, 'files_selected': 65, 'files_omitted_by_cap': 0, 'read_truncations': 18, 'bytes_discovered': 840568, 'bytes_read': 290585, 'degradations': ['content_truncated'], 'fingerprint': 'sha256:e708c907e41ef022e39b2da35a8f92dd7f816fc52d3142483f1f63d4e0b9498d'}
completion      : {'procedure_complete': False, 'thresholds_met': False, 'degradations': ['content_truncated'], 'blocking_degradations': ['content_truncated'], 'reason_codes': ['threshold_not_met', 'insufficient_sources', 'missing_production_evidence', 'coverage_capability_unavailable', 'content_truncated', 'no_eligible_actions'], 'termination_reason': 'no_eligible_actions', 'next_actions': [{'action': 'increase_read_limit', 'reason': 'content_truncated', 'authorization_required': True, 'addresses_reason_codes': ['content_truncated'], 'remaining_blockers': ['coverage_capability_unavailable', 'insufficient_sources', 'missing_production_evidence', 'no_eligible_actions', 'threshold_not_met'], 'expected_effect': 'read truncated artifacts in full; diagnostic only, it cannot turn retrieval into supports or refutes', 'capability_required': 'retrieval_only', 'parameter': 'read_limit_bytes', 'target_value': 840568, 'sufficient_if_successful': False}, {'action': 'enable_probative_verifier', 'authorization_required': True, 'reason': 'no_probative_evidence_available', 'aspects': ['algorithm', 'config', 'doc', 'test'], 'aspects_without_support': ['algorithm', 'config', 'test', 'doc'], 'aspects_under_corroborated': [], 'aspects_without_production_evidence': [], 'contradicted_claims': [], 'min_sources_per_aspect': 2, 'addresses_reason_codes': ['coverage_capability_unavailable', 'insufficient_sources', 'missing_production_evidence', 'threshold_not_met'], 'remaining_blockers': ['content_truncated', 'no_eligible_actions'], 'expected_effect': 'register a deterministic verifier able to emit supports or refutes for the named targets; proposal only, nothing is executed', 'capability_required': 'probatory_static', 'sufficient_if_successful': False}]}
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura probatoria agrega componentes independientes del mismo claim; recuperación y estructura se publican aparte y no habilitan completion. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **Identidad Git no incrustada**: incluir el commit del propio archivo generado crearía una autorreferencia imposible de estabilizar. El manifest registra en su lugar la versión de la distribución evaluadora.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.
- **Frescura normalizada**: este artefacto fija `freshness=1.0` y `timestamp=0` para no depender del `mtime` asignado por cada checkout; el pipeline normal conserva y evalúa los timestamps reales.

_Generado desde HEAD del pipeline. Manifest de entradas fijadas: `sha256:8aaeab737279270cc5a5dba9d2230228686bc8710f1c06ebdf2169a0c090838d` (perfiles semántico y de cobertura, revisión del target, evaluador, frescura y presupuesto). raw report: `{"evidence_count": 68, "proposition_count": 29, "coverage": 0.0, "evidential_coverage": 0.0, "retrieval_coverage": 0.75, "structural_coverage": 0.0, "coverage_capability": "unavailable", "residual_risk": 1.0, "complete": false}`_
