# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **1003**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25. Perfil semántico explícito: `char-ngram-v1`.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **72** (por nivel `{0: 5, 1: 1, 2: 9, 3: 1, 4: 44, 5: 12}`, por tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 9, 'doc': 19, 'code': 29, 'test': 12}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 823 nodos / 1382 aristas (331 producción). Top impacto: analyze_path (0.573), main (0.53), _check_one (0.527), check_case (0.524).
- Comportamiento L4 (AST best-effort, Σ_4): 47 fn levantan, 412 con asserts, 10 mutan self, 2 validan (345/851 producción).

## Reporte

```text
evidence_count  : 72
proposition_count: 33
relations        : {'mentions': 33}
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
cost            : estimated=77637 observed=77637
inventory       : {'profile': 'legacy-first-400-v1', 'files_discovered': 76, 'files_eligible': 69, 'files_selected': 69, 'files_omitted_by_cap': 0, 'read_truncations': 18, 'bytes_discovered': 854554, 'bytes_read': 303860, 'degradations': ['content_truncated'], 'fingerprint': 'sha256:98c2e869f3016dda288926548544781c6258f5a075f3d6285746e1953a5eac30'}
completion      : {'procedure_complete': False, 'thresholds_met': False, 'degradations': ['content_truncated'], 'blocking_degradations': ['content_truncated'], 'reason_codes': ['threshold_not_met', 'insufficient_sources', 'missing_production_evidence', 'coverage_capability_unavailable', 'content_truncated', 'no_eligible_actions'], 'termination_reason': 'no_eligible_actions', 'next_actions': [{'action': 'increase_read_limit', 'reason': 'content_truncated', 'authorization_required': True, 'addresses_reason_codes': ['content_truncated'], 'remaining_blockers': ['coverage_capability_unavailable', 'insufficient_sources', 'missing_production_evidence', 'no_eligible_actions', 'threshold_not_met'], 'expected_effect': 'read truncated artifacts in full; diagnostic only, it cannot turn retrieval into supports or refutes', 'capability_required': 'retrieval_only', 'parameter': 'read_limit_bytes', 'target_value': 854554, 'sufficient_if_successful': False}, {'action': 'enable_probative_verifier', 'authorization_required': True, 'reason': 'no_probative_evidence_available', 'aspects': ['algorithm', 'config', 'doc', 'test'], 'aspects_without_support': ['algorithm', 'config', 'test', 'doc'], 'aspects_under_corroborated': [], 'aspects_without_production_evidence': [], 'contradicted_claims': [], 'min_sources_per_aspect': 2, 'addresses_reason_codes': ['coverage_capability_unavailable', 'insufficient_sources', 'missing_production_evidence', 'threshold_not_met'], 'remaining_blockers': ['content_truncated', 'no_eligible_actions'], 'expected_effect': 'register a deterministic verifier able to emit supports or refutes for the named targets; proposal only, nothing is executed', 'capability_required': 'probatory_static', 'sufficient_if_successful': False}]}
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura probatoria agrega componentes independientes del mismo claim; recuperación y estructura se publican aparte y no habilitan completion. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **Identidad Git no incrustada**: incluir el commit del propio archivo generado crearía una autorreferencia imposible de estabilizar. El manifest registra en su lugar la versión de la distribución evaluadora.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.
- **Frescura normalizada**: este artefacto fija `freshness=1.0` y `timestamp=0` para no depender del `mtime` asignado por cada checkout; el pipeline normal conserva y evalúa los timestamps reales.

_Generado desde HEAD del pipeline. Manifest de entradas fijadas: `sha256:04afa7458aea6571f9c1a1bf888f30cdfb0830093ede474ea0c1892c0ece33bc` (perfiles semántico y de cobertura, revisión del target, evaluador, frescura y presupuesto). raw report: `{"evidence_count": 72, "proposition_count": 33, "coverage": 0.0, "evidential_coverage": 0.0, "retrieval_coverage": 0.75, "structural_coverage": 0.0, "coverage_capability": "unavailable", "residual_risk": 1.0, "complete": false}`_
