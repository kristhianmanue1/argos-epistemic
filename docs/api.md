# API Python actual

La API está en desarrollo y puede cambiar antes de `1.0`. Los schemas
versionados tienen reglas de compatibilidad más estrictas que las firmas Python.

## Análisis

### `analyze_system(system, goal, budget)`

Analiza una descripción de sistema ya construida.

- `system`: mapping con `name` y lista `artifacts`;
- `goal`: mapping con `name`, `aspects` y opciones de terminación;
- `budget`: `Budget(tokens_remaining, tool_remaining)`.

Devuelve un mapping con evidencia, claims, conflictos, cobertura, riesgo, costo,
inventory, completion y conclusiones de compatibilidad.

`residual_risk` se agrega sobre claims probatorios distintos, no sobre el número
de proposiciones: acumular relaciones `mentions` deja el valor sin cambio, y
añadir una refutación nunca lo reduce. Un objetivo cuyos aspectos requeridos
carecen de soporte positivo reporta `1.0` con independencia de cuánta evidencia
temática se haya recuperado. Sólo participan proposiciones cuyo aspecto
pertenece a los aspectos requeridos del objetivo. Ver
[MODEL.md §13.1](../MODEL.md#131-agregación-operativa-del-riesgo-residual).

### Capacidades de acción

Cada acción candidata declara `capability`, que describe lo que su extracción
**puede** producir para ese objetivo:

| Capacidad | Puede producir |
|---|---|
| `retrieval_only` | sólo `mentions` |
| `structural_relation` | `tests`, `implements`, `configures` |
| `probatory_static` | `supports` o `refutes` declarados sobre un aspecto requerido |
| `probatory_dynamic` | `supports` o `refutes` por ejecución autorizada |

La capacidad no se deriva del nivel L0–L5 ni de la confianza nominal del método,
y depende del objetivo: un `supports` declarado sobre un aspecto ajeno al
objetivo deja la acción en `retrieval_only`.

`probatory_dynamic` describe el método que produjo el artefacto; no afirma que
la ejecución estuviera autorizada ni concede autoridad para ejecutar nada. La
autorización dinámica se decide en `analyze_path(run_dynamic=...)`.

Las expectativas se modelan por separado —`expected_retrieval_gain`,
`expected_delta_coverage`, `expected_contradiction_discovery` y
`expected_delta_risk_reduction`— para que el planificador no optimice un
beneficio inalcanzable. Una acción `retrieval_only` o `structural_relation`
tiene cobertura y reducción de riesgo esperadas nulas; un artefacto que sólo
refuta tiene cobertura nula y reducción de riesgo no positiva, y su valor se
expresa como descubrimiento de contradicción. `expected_delta_confidence` se
conserva como metadato descriptivo y no participa en la utilidad.

Sólo `expected_retrieval_gain` escala con `relevance`. Las expectativas
probatorias proceden de un perfil de calibración versionado
(`calibration_profile`, seleccionable con `goal["probative_calibration"]`) que
declara su `expectation_uncertainty`. El perfil por defecto,
`uncalibrated-v0`, promete **cero** porque no existe calibración empírica; no
se asume un prior implícito.

Los campos `expected_delta_*` son deltas respecto del estado probatorio
vigente: un aspecto ya cubierto no aporta cobertura esperada adicional, y una
acción que también declara una refutación no promete reducción de riesgo.

Las declaraciones se validan antes de clasificarse. `strength` no finito o
fuera de `[0,1]`, aspectos no textuales y `claim`/`scope` malformados fallan
cerrado: la acción queda en `retrieval_only` y el motivo aparece en
`declaration_diagnostics`, sin excepciones accidentales.

#### Semántica transitoria de `strength`

- `0.0` significa **relación inexistente**: para `supports` y `refutes` la
  entrada se rechaza y se emite `<relación>:zero_strength_no_effect`;
- los valores en `(0, 1]` son admisibles;
- mientras F no redefina la agregación, `strength` es **únicamente un criterio
  de admisión**. No se aplica como ponderador de `coverage` y no debe
  presentarse como tal.

#### Limitación conocida de `coverage` (objetivo de corrección: PR F)

`coverage` todavía agrega por **volumen de proposiciones**, no por claim
normalizado: varias lecturas del mismo claim elevan el valor. `residual_risk`
ya agrega por claim y no presenta esa conducta. Es una **limitación conocida,
no una propiedad deseada**; la conducta objetivo es invariancia ante
duplicación del mismo claim y la misma raíz observada. Hasta entonces,
`complete` no debe descansar en esa inflación: el gate de independencia es lo
que impide que los duplicados satisfagan la corroboración.

### Perfiles semánticos y red

`default_semantic()` devuelve **siempre** `lexical_semantic`: es offline y
determinista. El backend denso descarga un modelo desde Hugging Face, por lo
que se selecciona de forma explícita (`semantic_fn=dense_semantic` o el perfil
`minilm-v1`) y sólo donde la red está autorizada. El camino por defecto no
accede a la red.

### `next_actions`

Cada propuesta declara `addresses_reason_codes`, `remaining_blockers`,
`expected_effect`, `capability_required`, `sufficient_if_successful` y
`authorization_required`. Ampliar presupuesto, lectura o caps nunca resuelve
`threshold_not_met`, `insufficient_sources` ni `missing_production_evidence`:
para eso el reporte propone `enable_probative_verifier`, que es una propuesta y
**no ejecuta nada**.

### `analyze_path(path, goal, budget, ...)`

Descubre un checkout y ejecuta el mismo pipeline. Las opciones dinámicas,
históricas, de logs, perfiles y cobertura habilitan evidencia adicional. No uses
ejecución dinámica sobre código no confiable sin aislamiento externo.

### `run()`

Demo determinista mínima para smoke tests. No es una interfaz de producción.

## Bundle

- `build_manifest(...)` y `verify_manifest(...)`;
- `build_envelope(...)` y `verify_envelope(...)`;
- `build_run_attestation(...)` y `verify_run_attestation(...)`;
- `verify_inventory(...)`;
- `verify_claim_record(...)`;
- `schema_names()` y `load_schema(name)`.

Los verificadores lanzan `BundleContractError`. Consulta
[contracts.md](contracts.md) antes de persistir o intercambiar documentos.

## Canonicalización

- `canonical_json_bytes(value)`;
- `sha256_fingerprint(document)`;
- `fingerprinted_document(document)`;
- `verify_fingerprinted_document(document)`;
- `content_id(namespace, value)`.

El perfil rechaza floats y claves no textuales para mantener portabilidad entre
runtimes. Los decimales contractuales se expresan como strings.

## Verificación estática e independencia

`argos_epistemic.verifiers` define la frontera entre candidato temático y
prueba.

- `VerifierClaim`: lo que un verificador afirma. **No** lleva campos de
  procedencia por diseño.
- `run_verifier(registration, payload, execution_id, derived_from=())`: ejecuta
  un verificador y estampa perfil versionado, método, ejecución, revisión del
  target y huellas de raíz desde entradas confiables. Devuelve
  `VerificationResult`. Una excepción, un `outcome` desconocido, un aspecto
  fuera del objetivo o un claim vacío producen `degraded`/`unknown` con
  confianza cero; nunca `supports`.
- `register_verifier` / `registered_verifiers` / `unregister_verifier`: registro
  explícito, versionado y de orden determinista. No hay descubrimiento de
  plugins ni acceso a red.
- `normalized_claim_id(aspect, claim_text, scope)`: identidad estable bajo un
  perfil de normalización que pliega mayúsculas y espacios en aspecto, texto
  **y alcance**. El alcance participa en la identidad tras esa normalización
  superficial, de modo que `"v1"` y `"V1"` son el mismo alcance pero `"v1"` y
  `"v2"` no se fusionan. La normalización **no** demuestra equivalencia
  semántica: dos redacciones distintas siguen siendo claims distintos.
- `verification_input(...)`: factoría confiable que calcula la raíz primaria
  desde el contenido. `run_verifier` exige que esa raíz esté presente, así que
  un llamador no puede suministrar raíces arbitrarias para fabricar
  independencia.
- `root_fingerprint(content)`: identidad direccionada por contenido, de modo que
  alias y copias resuelven a una sola raíz.
- `prepare_sources(sources, revision=None, claim=None)`: la **única**
  preparación conservadora, compartida por agrupación, conteo y reporte.
  Descarta fuentes malformadas, excluye ids con procedencias conflictivas e
  ignora las de otra revisión u otro claim. Es acíclica: no llama a las
  funciones de conteo.
- `independence_groups(sources, revision=None, claim=None)`: **vista topológica
  genérica**. Componentes conexos sobre raíz compartida, ejecución compartida,
  **familia de instrumento** compartida y derivación (incluido un padre externo
  ausente del conjunto). Aplica la misma preparación, de modo que una fuente
  malformada no alcanza las claves del union-find ni provoca excepciones. Sus
  filtros de revisión y claim son **opcionales**: omitirlos es una ausencia
  deliberada de restricción, no un fallo.
- `independent_source_count(sources, revision, claim)`: **API de
  corroboración**. Exige revisión y `normalized_claim_id` **válidos** para
  poder demostrar más de una fuente. La corroboración es por claim normalizado:
  sumar componentes de claims distintos contaría como acuerdo lo que son
  afirmaciones diferentes. Se cuentan componentes, no salidas.
- `independence_report(sources, required_sources, revision, claim)`: **API de
  corroboración**, con las mismas exigencias que el contador. Explicación
  auditable con `evaluated_target_revision`, `evaluated_normalized_claim_id`,
  `components_by_revision`, `ignored_revision_mismatch`,
  `ignored_claim_mismatch`, `conflicting_source_ids`, `invalid_sources`,
  `missing_scope_constraints`, `unevaluated_scope_sources` y los componentes
  utilizados; se publica en el reporte como `source_independence`. Es idéntico
  bajo permutación, duplicación, conflicto y cohortes con claims mezclados.
  - `missing_scope_constraints`: lista los códigos
    `missing_or_invalid_target_revision` y/o
    `missing_or_invalid_normalized_claim_id` cuando la restricción
    correspondiente falta o no es textual válida. Vacía cuando el alcance sí
    pudo evaluarse.
  - `unevaluated_scope_sources`: identificadores de las fuentes que no llegaron
    a evaluarse contra un alcance, precisamente porque no había alcance válido
    contra el cual evaluarlas.

**Restricción ausente o inválida en las APIs de corroboración**: el conteo se
limita a **uno** y el reporte **no publica componentes demostrados**
(`components` queda vacío y `components_by_revision` también), porque afirmar
componentes independientes sin haber podido comprobar el alcance contradiría el
propio conteo. El motivo se declara en `missing_scope_constraints` en lugar de
quedar implícito. Una restricción inválida **nunca** se reinterpreta como
«sin filtro»: un valor truthy pero no textual limita igual que su ausencia.
- `proposition_from_verification(result, goal_name)`: **única** conversión de
  `VerificationResult` a `Proposition`. Devuelve `None` para resultados no
  probatorios y conserva toda la procedencia, incluido
  `verification_result_id`. Reconstruir proposiciones a mano reabriría el
  camino donde la procedencia se afirma en vez de transportarse.

La independencia debe **demostrarse**: una fuente sin familia, ejecución,
revisión objetivo o raíz no aporta grupo adicional, y `min_sources > 1` no puede
satisfacerse sólo con fuentes legacy o incompletas. Los valores compuestos sólo
por espacios cuentan como ausentes. La versión del verificador liga la identidad
del resultado pero **no** crea un segundo testigo dentro de la misma familia.
`AUTHORIZED_INDEPENDENCE_CLASSES` está vacío por defecto: una clase arbitraria
no relaja la regla de familia. `goal["target_revision"]` alimenta el gate; sin
ella, `min_sources > 1` falla cerrado.

El target analizado no puede declarar con autoridad `verifier_profile`,
`execution_id`, `independence_group` ni huellas de raíz: los calcula la
frontera. `min_sources_per_aspect` se evalúa por claim normalizado sobre grupos
independientes, de modo que duplicados, alias y ejecuciones repetidas no pueden
satisfacer la corroboración aunque la cobertura legacy se sature. Ver
[MODEL.md §12.1](../MODEL.md#121-corroboración-e-independencia-entre-fuentes).

## Perfiles semánticos

`lexical_semantic`, `embedding_semantic` y el backend denso opcional producen
relevancia. Ninguno puede certificar soporte o refutación. El extra `semantic`
instala el backend denso; `languages` habilita extractores tree-sitter.

## Estabilidad

Antes de `1.0`:

- importa desde `argos_epistemic`, no desde módulos internos cuando exista una
  exportación pública;
- fija la versión del paquete;
- valida `schema` y `canonicalization` al consumir documentos;
- no interpretes campos desconocidos como autoridad;
- conserva documentos originales para auditoría.
