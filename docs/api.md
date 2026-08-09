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

### Verificadores concretos: dependencias PEP 621 y PEP 508

`argos_epistemic.dependency_verifiers` implementa los dos primeros verificadores
sobre el protocolo de D.

- `DependencyTarget(name, specifier="", marker="", scope="core", extras=())`:
  el claim estrecho a comprobar. `scope="core"` son las dependencias centrales
  de `project.dependencies`; `scope=f"extra:{nombre}"` un grupo de
  `project.optional-dependencies`. Los `extras` son los sub-features
  solicitados por el propio requirement (`pkg[extra1]`), no el grupo.
- `make_pep621_verifier(target)`: comprueba `pyproject.toml` con `tomllib`.
  Ignora `build-system.requires` y toda tabla `tool.*` — ninguna representa una
  dependencia runtime bajo PEP 621. Si `dependencies` u
  `optional-dependencies` están en `project.dynamic`, nunca produce `refutes`
  desde ese campo; declararlo simultáneamente estático y dinámico se diagnostica
  como conflicto. Un `dynamic` con tipo inválido degrada todo el parseo.
- `make_pep508_verifier(target)`: comprueba un archivo estilo
  `requirements.txt` con `packaging.requirements.Requirement`. Distingue
  requisitos PEP 508 de directivas de pip (`-r`, `-c`, `-e`, `--index-url`,
  etc.); sólo `-r`/`--requirement` y `-c`/`--constraint` marcan el archivo como
  no completamente inspeccionado (pueden ocultar declaraciones en otro
  archivo), y sólo entonces una ausencia degrada a `unknown` con esa
  limitación explícita. El resto de directivas no son evidencia de ausencia ni
  de invalidez.

El claim es deliberadamente estrecho: *"el repositorio declara la dependencia X
bajo la restricción Y para el alcance Z en la revisión R."* Ningún verificador
afirma instalación, importabilidad, resolubilidad, compatibilidad de entorno ni
funcionamiento — son verificadores estáticos.

Semántica de resultado por objetivo:

- mismo nombre, alcance, specifier, marker y extras → `supports`;
- mismo nombre y alcance pero specifier, marker o extras distintos → `refutes`
  (el archivo contradice directamente el claim esperado);
- nombre/alcance ausente en un archivo completamente inspeccionado → `unknown`;
- nombre/alcance ausente con includes sin resolver → `unknown` con
  `unresolved_includes_may_hide_declaration`, nunca `refutes`;
- TOML o requirement PEP 508 inválido → `degraded`/`unknown` con diagnóstico
  estructurado, nunca excepción.

Una URL de referencia directa (`pkg @ https://user:token@host/...`) **nunca se
retiene**, ni siquiera saneada: userinfo, query string y fragmento pueden
llevar un secreto por igual (`?token=...`, `#token`), así que
`ParseOutcome` sólo conserva un contador (`direct_reference_count`) y el
diagnóstico `direct_reference_not_supported` — nunca la cadena de la URL. Ni
`repr(ParseOutcome)` ni ningún claim/límite/degradación/reporte pueden
contener una URL de manifiesto.

`looks_pip_compile_generated_from(content, source_filename)` es un heurístico
conservador: sólo detecta una cabecera de generación explícita que nombra el
archivo origen. El llamador que confirme derivación debe pasar
`derived_from=(parent_result.result_id,)` a `run_verifier` — la relación de D
liga por `result_id` del padre, no por huella de raíz. Sin cabecera detectada,
dos archivos cuentan como fuentes independientes por defecto: es el caso
positivo que D fue diseñado para reconocer.

- `proposition_from_verification(result, goal_name)`: **única** conversión de
  `VerificationResult` a `Proposition`. Devuelve `None` para resultados no
  probatorios y conserva toda la procedencia, incluido
  `verification_result_id`. Reconstruir proposiciones a mano reabriría el
  camino donde la procedencia se afirma en vez de transportarse.

#### Frontera automática: `analyze_path` invoca estos verificadores

`extract_system`/`analyze_path` **sí** invocan estos verificadores cuando el
`goal` opta explícitamente:

```python
goal = {
    "name": "dependency-audit",
    "aspects": ["requests"],                 # aspectos reales del goal
    "target_revision": "rev-abc123",          # obligatorio, no vacío
    "dependency_targets": [
        {"name": "requests", "specifier": ">=2.0", "scope": "core"},
        # o DependencyTarget(...) directamente
    ],
}
report = analyze_path(root, goal=goal, budget=budget)
```

- **Opt-in por presencia, no por verdad** (`"dependency_targets" in goal`):
  `dependency_targets=None/0/""` también activa la frontera — se clasifica
  como colección inválida (diagnóstico `invalid_dependency_targets_collection`)
  en vez de tratarse silenciosamente como «no solicitado». Una lista vacía
  válida activa la frontera sin diagnóstico y sin trabajo.
- **`target_revision` obligatorio y textual**: ausente, vacío o no textual
  produce `missing_target_revision` y ningún verificador se ejecuta. La admisión
  genérica tampoco usa `str()` para convertir revisiones hostiles: una revisión
  no textual se evalúa como ausente y no puede coincidir con un resultado.
- **Alcance real del goal, no el nombre propio del target**: cada target se
  compara contra los aspectos REALES del goal (`derive_goal_aspects`). Un
  target cuyo `canonical_name` no pertenece a esos aspectos nunca se ejecuta —
  produce `dependency_target_outside_goal:<nombre>` y no puede contaminar,
  como `refutes` o como `supports`, la cobertura/riesgo/completitud de un
  aspecto que nunca lo pidió.
- **Cada manifiesto se parsea una sola vez**; todos los targets aceptados se
  resuelven contra ese único `ParseOutcome` — no hay reparseo por target.
- **Deduplicación e identidad canónica**: targets con la misma identidad
  (nombre, alcance, specifier, marker, extras canónicos) colapsan a uno solo
  antes de ejecutar nada — 1000 copias del mismo target no producen 1000
  ejecuciones, 1000 unidades de costo ni cobertura duplicada. Un tope
  (`MAX_DEPENDENCY_TARGETS`) acota además el trabajo por llamada; el exceso se
  reporta explícitamente vía `dependency_targets_capped`, nunca se descarta en
  silencio.
- **Costo cobrado únicamente por trabajo real**: un manifiesto inexistente, un
  symlink rechazado o un target sin ningún manifiesto disponible para
  resolverse **cuestan cero** — no hay lectura, no hay ejecución, no hay cargo.
  Antes de leer, la frontera deriva del presupuesto actual el máximo de bytes
  asequible; sin una herramienta y el mínimo de 10 tokens, `os.read` ni siquiera
  se invoca. Un tamaño `fstat()` superior a esa capacidad se rechaza antes de
  leer, y un crecimiento concurrente se corta al superar el límite asequible.
  `fstat()` sobre el descriptor ya abierto permite rechazar temprano un tamaño
  declarado sobre el límite, pero el cargo usa el total de bytes realmente
  leído hasta EOF. La lectura es binaria, repite `os.read` ante short reads y
  se detiene en `MAX_MANIFEST_BYTES + 1`; crecimiento concurrente no se acepta
  ni se cobra con un tamaño obsoleto. Un target se cobra y ejecuta **todo o
  nada** contra el conjunto de manifiestos disponibles (0, 1 o 2): si el
  presupuesto no cubre el costo de resolverlo contra TODOS los manifiestos
  disponibles, el target completo se omite con diagnóstico
  `dependency_target_budget_exhausted:<nombre>` — nunca una ejecución parcial.
  `executions == len(results)` y `charged_tool` se reconstruye como lecturas de
  manifests cobradas más ejecuciones publicadas; el costo en tokens se
  reconstruye desde bytes leídos más el cargo fijo de esas ejecuciones.
- **Lectura symlink-safe y no bloqueante en una sola apertura fail-closed**:
  `os.open(..., O_NOFOLLOW | O_NONBLOCK)` hace que el rechazo de
  symlink sea parte del propio `open()` atómico — no hay una comprobación
  `is_symlink()` seguida de una apertura separada que un reemplazo
  concurrente pudiera colar. `fstat()` se hace sobre el descriptor ya abierto,
  nunca sobre una ruta stat-eada por separado. Symlinks internos, externos o
  rotos se rechazan igual — `<archivo>:symlink_rejected` — nunca se sigue un
  enlace en silencio. `O_NONBLOCK` evita que un FIFO nombrado como manifiesto
  bloquee antes de que `fstat()` lo descarte como no regular. Si la plataforma
  no ofrece alguno de esos flags, la lectura no se intenta y produce un
  diagnóstico explícito.
- **Costo íntegramente visible en el reporte**: `report["cost"]["phases"]
  ["dependency_verification"]` expone `tokens`, `tools`, `manifests_inspected`
  y `executions`; los totales `cost.estimated_tokens`/`observed_tokens`
  incluyen este cargo. El bucle de `analyze_system` comprueba los umbrales
  ANTES de comprobar la capacidad del presupuesto: si el propio verificador
  gastó la última unidad de presupuesto pero los umbrales ya estaban
  satisfechos, `termination_reason` es `thresholds_met`, nunca
  `budget_exhausted` sobrescribiendo un `complete=True` ya alcanzado.
- **`report["dependency_verification"]`**: sección pública y saneada, presente
  siempre (`{"enabled": False}` cuando el goal no opta). Cuando opta:
  `evaluated_target_revision`, `requested_targets`/`accepted_targets`/
  `rejected_targets`, `families_executed`, `manifests_inspected`,
  `manifest_bytes_read` (nombre y bytes, nunca contenido),
  `verification_result_count`, `results` (lista de `{result_id, outcome,
  aspect, limitations, degradations}` — nunca contenido de manifiesto ni URL),
  `diagnostics`, `cost`. Aparece incluso cuando ningún `VerificationResult`
  produjo una `Proposition` probatoria (todo `unknown`/`degraded`), para que
  un target inválido, sin espacio, sin presupuesto o fuera de alcance quede
  visible en vez de desaparecer. `goal_aspects` se valida estrictamente antes
  de iterarse (sólo `list`/`tuple` de strings no vacíos, sin truthiness ni
  coerción) — un valor hostil (`7`, `object()`, una cadena suelta, un `dict`)
  nunca lanza excepción y produce `invalid_goal_aspects` con cero targets
  aceptados y cero costo.
- **`analyze_system(..., verification_results=..., dependency_verification_outcome=...)`**:
  - `verification_results` transporta `VerificationResult` genéricos (de
    cualquier frontera de verificación externa, no sólo dependencias). Cada
    candidato pasa, en este orden estricto, por: (1) `validate_verification_result`
    — un objeto de otro tipo (incluida una `Proposition` construida a mano) o
    un `VerificationResult` cuya identidad ya no coincide con sus propios
    campos (alterado con `dataclasses.replace`) se descarta aquí; (2)
    pertenencia de `result.aspect` a los aspectos REALES de este goal — un
    resultado genuino y válido producido para OTRO goal nunca contamina éste;
    (3) `result.target_revision` debe coincidir EXACTAMENTE con
    `goal["target_revision"]` — un resultado genuino, válido y del aspecto
    correcto pero de una revisión vieja tampoco cuenta; (4) sólo entonces
    `proposition_from_verification`, la única conversión, que además rechaza
    lo no probatorio. `report["verification_admission"]` expone
    `verification_candidates_offered`/`verification_results_valid`/
    `verification_propositions_admitted`/`verification_candidates_rejected`/
    `verification_rejection_reasons` (`invalid_result`, `aspect_outside_goal`,
    `revision_mismatch`, `non_probative`, `duplicate_result`) — nunca se presenta basura
    rechazada (un `int`, un `dict`, una `Proposition` fabricada) como si fuera
    un "resultado de verificación" contado junto a los genuinos.
  - `dependency_verification_outcome` DEBE ser un
    `dependency_verifiers.DependencyVerificationOutcome` tipado — nunca un
    `dict`, pero el tipo exterior no basta. Se validan colecciones internas,
    cada `VerificationResult`, contadores, familias, manifests, consistencia de
    costo reconstruida desde `manifest_bytes_read + executions` y una identidad
    content-addressed del cargo. Cualquier inconsistencia
    falla cerrada con `invalid_dependency_verification_outcome`, sin renderizar
    campos hostiles ni admitir evidencia. El outcome es la **única fuente** de
    sus resultados, su reporte y su costo: `analyze_system` admite directamente
    sus `.results` por la ruta genérica y consume el cargo exactamente una vez
    en el mismo `Budget`. Un outcome ya cobrado a ese Budget es idempotente; uno
    externo debe ser asequible o produce
    `dependency_verification_budget_exhausted` con cero resultados admitidos.
    Repetir además sus resultados en `verification_results` no multiplica
    proposiciones porque se deduplican por `result_id`. El estado prepagado sólo
    puede consolidarse desde recibos internos creados al descontar realmente
    cada subcargo; un llamador no puede marcarlo pagado mediante una API pública.
    La identidad content-addressed prueba consistencia, **no autenticidad**:
    resultados/outcomes persistidos o de terceros requieren una attestation
    confiable antes de tratarlos como autoridad.

Los conflictos de la evidencia admitida inicialmente (`verification_results`)
se calculan **antes** de la primera comprobación de umbrales/capacidad del
bucle de `analyze_system`, no sólo después de que corra una acción: un
`supports` y un `refutes` genuinos sobre el mismo claim normalizado, admitidos
de entrada, producen un conflicto visible incluso con `budget=(0, 0)`, donde
el cuerpo del bucle nunca se ejecuta.

La independencia debe **demostrarse**: una fuente sin familia, ejecución,
revisión objetivo o raíz no aporta grupo adicional, y `min_sources > 1` no puede
satisfacerse sólo con fuentes legacy o incompletas. Los valores compuestos sólo
por espacios cuentan como ausentes. La versión del verificador liga la identidad
del resultado pero **no** crea un segundo testigo dentro de la misma familia.
`AUTHORIZED_INDEPENDENCE_CLASSES` está vacío por defecto: una clase arbitraria
no relaja la regla de familia. `goal["target_revision"]` alimenta el gate; sin
ella, `min_sources > 1` falla cerrado.

El gate de evidencia primaria distingue una mención periférica de una prueba:
cuando existe grafo L3, acepta soporte con `impact > 0` o un
`VerificationResult` validado y convertido por la frontera única. Esto permite
que una declaración de dependencia quede demostrada por sus manifests —su
fuente primaria real— sin permitir que documentación/config enlazada sólo por
relevancia satisfaga el gate.

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
