# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **709**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25. Perfil semántico explícito: `char-ngram-v1`.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **60** (por nivel `{0: 5, 1: 1, 2: 8, 3: 1, 4: 39, 5: 6}`, por tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 8, 'doc': 18, 'code': 25, 'test': 6}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 568 nodos / 963 aristas (262 producción). Top impacto: main (0.586), _check_one (0.582), check_case (0.579), generate_case (0.571).
- Comportamiento L4 (AST best-effort, Σ_4): 28 fn levantan, 253 con asserts, 10 mutan self, 2 validan (273/590 producción).

## Reporte

```text
evidence_count  : 60
proposition_count: 23
relations        : {'mentions': 23}
conflict_count  : 0
coverage        : 0.0
residual_risk   : 1.0
complete        : False
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'algorithm': 0.0, 'config': 0.0, 'test': 0.0, 'doc': 0.0}
cost            : estimated=62932 observed=62932
inventory       : {'profile': 'legacy-first-400-v1', 'files_discovered': 63, 'files_eligible': 57, 'files_selected': 57, 'files_omitted_by_cap': 0, 'read_truncations': 15, 'bytes_discovered': 590717, 'bytes_read': 245179, 'degradations': ['content_truncated'], 'fingerprint': 'sha256:0c1380fc66000101fe4b0cf1de3caffe667f37c8dcd9dbe860cccfc06c3e39c7'}
completion      : {'procedure_complete': False, 'thresholds_met': False, 'degradations': ['content_truncated'], 'blocking_degradations': ['content_truncated'], 'reason_codes': ['threshold_not_met', 'insufficient_sources', 'missing_production_evidence', 'content_truncated', 'no_eligible_actions'], 'termination_reason': 'no_eligible_actions', 'next_actions': [{'action': 'increase_read_limit', 'reason': 'content_truncated', 'authorization_required': True, 'addresses_reason_codes': ['content_truncated'], 'remaining_blockers': ['insufficient_sources', 'missing_production_evidence', 'no_eligible_actions', 'threshold_not_met'], 'expected_effect': 'read truncated artifacts in full; diagnostic only, it cannot turn retrieval into supports or refutes', 'capability_required': 'retrieval_only', 'parameter': 'read_limit_bytes', 'target_value': 590717, 'sufficient_if_successful': False}, {'action': 'enable_probative_verifier', 'authorization_required': True, 'reason': 'no_probative_evidence_available', 'aspects': ['algorithm', 'config', 'doc', 'test'], 'aspects_without_support': ['algorithm', 'config', 'test', 'doc'], 'aspects_under_corroborated': [], 'aspects_without_production_evidence': [], 'contradicted_claims': [], 'min_sources_per_aspect': 2, 'addresses_reason_codes': ['insufficient_sources', 'missing_production_evidence', 'threshold_not_met'], 'remaining_blockers': ['content_truncated', 'no_eligible_actions'], 'expected_effect': 'register a deterministic verifier able to emit supports or refutes for the named targets; proposal only, nothing is executed', 'capability_required': 'probatory_static', 'sufficient_if_successful': False}]}
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por aspecto sobre relaciones `supports`; `mentions` orienta recuperación pero aporta cero cobertura. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **Identidad Git no incrustada**: incluir el commit del propio archivo generado crearía una autorreferencia imposible de estabilizar. El manifest registra en su lugar la versión de la distribución evaluadora.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.
- **Frescura normalizada**: este artefacto fija `freshness=1.0` y `timestamp=0` para no depender del `mtime` asignado por cada checkout; el pipeline normal conserva y evalúa los timestamps reales.

_Generado desde HEAD del pipeline. Manifest de entradas fijadas: `sha256:3f654555197b56f9b403b448b1bade788bd685082e90b34f1b3f6cd41d5472ab` (perfil semántico, revisión del target, evaluador, frescura y presupuesto). raw report: `{"evidence_count": 60, "proposition_count": 23, "coverage": 0.0, "residual_risk": 1.0, "complete": false}`_
