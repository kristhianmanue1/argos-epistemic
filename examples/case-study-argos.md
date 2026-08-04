# Caso de estudio: argos-epistemic (autoestudio)

> Generado por `examples/regenerate_case_studies.py` desde el pipeline actual (no escrito a mano). El sistema analizado es el propio repositorio; es un *autoestudio*, lo que limita la independencia (ver caso markupsafe).

Tests en verde: **88**. Objetivo `G=refactorizacion`, aspectos `['algorithm', 'config', 'test', 'doc']`, NF `['sec']`, θ=0.8, ρ=0.25. Perfil semántico explícito: `char-ngram-v1`.

## Extracción (discovery barato + índice L3)

- Artefactos descubiertos: **56** (por nivel `{0: 5, 1: 1, 2: 7, 3: 1, 4: 38, 5: 4}`, por tipo `{'topology': 1, 'callgraph': 1, 'behavior': 1, 'config': 7, 'doc': 18, 'code': 24, 'test': 4}`).
- Grafo de llamadas L3 (Python AST, subgrafo de producción): 294 nodos / 447 aristas (197 producción). Top impacto: main (0.612), _argos_md (0.597), _third_party_md (0.587), analyze_path (0.571).
- Comportamiento L4 (AST best-effort, Σ_4): 18 fn levantan, 87 con asserts, 9 mutan self, 2 validan (207/306 producción).

## Reporte

```text
evidence_count  : 56
proposition_count: 28
relations        : {'mentions': 28}
conflict_count  : 0
coverage        : 0.0
residual_risk   : 0.7
complete        : False
levels_covered  : [0, 1, 2, 3, 4, 5]
aspect_scores   : {'algorithm': 0.0, 'config': 0.0, 'test': 0.0, 'doc': 0.0}
cost            : estimated=53218 observed=53218
inventory       : {'profile': 'legacy-first-400-v1', 'files_discovered': 64, 'files_eligible': 53, 'files_selected': 53, 'files_omitted_by_cap': 0, 'read_truncations': 9, 'bytes_discovered': 355770, 'bytes_read': 206144, 'degradations': ['content_truncated'], 'fingerprint': 'sha256:6435e30b1fffb152a655edf89dfaa95cdbbf4a9d81610078684d8a6fa07d1a45'}
completion      : {'procedure_complete': False, 'thresholds_met': False, 'degradations': ['content_truncated'], 'blocking_degradations': ['content_truncated'], 'reason_codes': ['threshold_not_met', 'insufficient_sources', 'missing_production_evidence', 'content_truncated', 'no_eligible_actions'], 'termination_reason': 'no_eligible_actions', 'next_actions': [{'action': 'increase_read_limit', 'reason': 'content_truncated', 'authorization_required': True}]}
```

## Interpretación

El bucle presupuestado selecciona evidencia por utilidad (valor/costo) y detiene al alcanzar `coverage ≥ θ` y `risk ≤ ρ`. La cobertura es por aspecto sobre relaciones `supports`; `mentions` orienta recuperación pero aporta cero cobertura. El costo **observado** (contenido real leído) se contabiliza contra el presupuesto y se compara con el estimado (stat).

## Riesgo residual

- **Autoestudio**: analizador y analizado coinciden; ver markupsafe para evidencia independiente.
- **Identidad Git no incrustada**: incluir el commit del propio archivo generado crearía una autorreferencia imposible de estabilizar. La identidad del evaluador pertenecerá al manifest externo del bundle.
- **`S_semantic` surrogate**: se usa el embedding léxico (char-n-gramas), no denso; sesión del LLM/transformers queda pendiente.
- **Discovery no presupuestado**: la lectura de archivos y el índice L3 se pagan antes del bucle (el grafo alimenta `R` para la selección); sólo el contenido por-objetivo y los extractores subprocess son perezosos.
- **Frescura normalizada**: este artefacto fija `freshness=1.0` y `timestamp=0` para no depender del `mtime` asignado por cada checkout; el pipeline normal conserva y evalúa los timestamps reales.

_Generado desde HEAD del pipeline. raw report: `{"evidence_count": 56, "proposition_count": 28, "coverage": 0.0, "residual_risk": 0.7, "complete": false}`_
