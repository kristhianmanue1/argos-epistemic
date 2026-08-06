# Plan técnico de remediación del pipeline probatorio de Argos

**Fecha:** 2026-08-05  
**Estado:** listo para revisión y ejecución incremental; ningún cambio técnico descrito
se considera implementado por la existencia de este documento  
**Base verificada:** `argos@d31ba8b216c0779b561b4e3660bcf687dd00578b`  
**Audiencia:** agentes de IA que implementan, revisan o verifican cambios; personas
responsables de arquitectura, documentación y releases  
**Relación con otros planes:** especializa la remediación inmediata descrita por
`examples/plan-mejoras-argos-post-evaluaciones-2026-08-03.md`; no sustituye el
roadmap de producto  
**Advertencia de worktree:** al redactar este plan existían cambios locales ajenos
en `bench/real_report.md` y `bench/real_repos.py`. Los agentes deben preservarlos,
atribuirlos a su propietario y no incorporarlos incidentalmente.

## 1. Resultado perseguido

Argos debe conservar la separación estricta entre relevancia y prueba, pero su
pipeline de análisis de rutas debe disponer de una ruta auditable y comprobada
para producir evidencia probatoria. Al finalizar este plan:

1. los casos de estudio publicados serán reproducibles contra revisiones exactas;
2. `mentions` no elevará cobertura ni reducirá o diluirá riesgo;
3. el planificador no prometerá ganancia de cobertura a acciones incapaces de
   producir `supports` o `refutes`;
4. al menos un verificador estático determinista producirá claims probatorios
   estrechos, con alcance y procedencia;
5. una prueba end-to-end demostrará que `analyze_path` puede alcanzar
   `complete=True` mediante dos fuentes de soporte independientes, sin relajar los
   gates para esconder el problema;
6. el reporte distinguirá cobertura probatoria, cobertura de recuperación y
   capacidad de verificación sin romper de inmediato el campo público `coverage`;
7. la frescura se aplicará antes de calcular relevancia y quedará descrita en la
   configuración reproducible;
8. documentación, benchmarks, casos generados, schemas y CI describirán el mismo
   comportamiento.

## 2. Diagnóstico de base

### 2.1 Hechos confirmados contra código

- La relación semántica inferida produce `mentions`; esta salvaguarda está
  especificada y probada, y no debe eliminarse.
- Sólo `supports` contribuye a `aspect_score`, cobertura, fuentes mínimas y
  evidencia de producción.
- Los extractores de rutas no declaran `supports`. El único ascenso automático
  actual desde `mentions` ocurre para una verificación con método `dynamic`.
- `analyze_path(run_dynamic=True)` registra una sola acción dinámica. Con
  confianza `0.9`, corroboración `1.8` y dos fuentes mínimas por aspecto, esa
  fuente tiene techo `0.5` y no puede completar el procedimiento por sí sola.
- Los casos de estudio terceros no activan la ruta dinámica: el generador llama
  `extract_system` y después `analyze_system`.
- `compute_residual_risk` devuelve `1.0` sólo cuando no existen proposiciones.
  Una o más relaciones `mentions` cambian el cálculo a `0.7` aun sin soporte.
- El denominador de contradicciones incluye todas las proposiciones; por tanto,
  añadir `mentions` puede diluir el peso de `refutes`.
- `generate_candidate_actions` asigna `expected_delta_coverage` a artefactos
  estáticos que sólo pueden materializar relevancia no probatoria.
- `next_actions` puede sugerir `increase_read_limit` sin declarar que no resuelve
  `threshold_not_met`, `insufficient_sources` ni
  `missing_production_evidence`.
- `--check` ignora `--target`, compara únicamente el caso Argos y retorna éxito
  cuando falla el clone de un tercero.
- Los terceros se clonan desde una rama móvil; la revisión observada aparece en
  el Markdown, pero no forma parte de la configuración de entrada.
- Markupsafe y AN-KLA conservan resultados anteriores a la semántica de claims
  tipados introducida en `bed0ae7`.
- La normalización de frescura del autoestudio muta `freshness` y `timestamp`
  después de que `extract_system` haya calculado `relevance`; no neutraliza la
  influencia original y oculta los valores usados.

### 2.2 Interpretación

No se trata de revertir la política `mentions != supports`. El defecto es de
viabilidad e integración: se instaló un gate conservador sin construir los
productores/verificadores suficientes para atravesarlo. El resultado numérico
`coverage=0.0` es coherente con la fórmula, pero no permite distinguir una mala
cobertura probatoria de un modo de ejecución sin capacidad probatoria.

### 2.3 Discrepancia histórica

La memoria y documentación histórica registraron H8 como resuelto cuando el
generador inicial cubría Argos y Markupsafe. El estado vigente ya no satisface
esa conclusión: la semántica cambió, dos documentos no se regeneraron y CI sólo
protege Argos. Los agentes deben tratar el antecedente como evidencia histórica,
no como descripción vigente.

## 3. Invariantes no negociables

### 3.1 Semántica

1. Similitud temática, embeddings o coincidencia léxica sólo producen
   `mentions`.
2. `tests`, `implements` y `configures` son relaciones estructurales; no se
   convierten en prueba por nombre.
3. Sólo un verificador identificado, una regla determinista versionada, una
   ejecución autorizada o una declaración explícita con autoridad admisible
   puede producir `supports` o `refutes`.
4. Todo soporte declara claim estrecho, aspecto, alcance, evidencia, método,
   perfil de extracción y clase de autoridad.
5. Dos fuentes sólo corroboran si sus identidades y dependencias son realmente
   independientes bajo una política documentada.
6. Un resultado parcial permanece válido y visible; `complete=False` no se
   convierte en error de transporte.

### 3.2 Riesgo

1. Si ningún aspecto requerido tiene soporte positivo, el componente de
   evidencia ausente es máximo.
2. Añadir `mentions` nunca reduce riesgo.
3. Añadir `mentions` nunca diluye una refutación.
4. Añadir una refutación nunca reduce riesgo.
5. Sólo soporte positivo vigente puede reducir el componente de evidencia
   ausente.
6. El riesgo se calcula por claims o aspectos probatorios, no por volumen de
   registros temáticos.

### 3.3 Compatibilidad

1. `coverage` continúa siendo numérico durante al menos un ciclo de
   compatibilidad y mantiene su semántica probatoria actual.
2. Los campos nuevos se añaden de forma aditiva antes de cualquier rename o
   cambio de tipo.
3. Un cambio incompatible de schema requiere nombre versionado nuevo y pruebas
   de coexistencia.
4. `complete` nunca se obtiene bajando silenciosamente umbrales de fixtures o
   desactivando gates de producción.
5. Los resultados generados se actualizan en el mismo PR que cambia su semántica.

### 3.4 Seguridad y autoridad

1. La ejecución dinámica de terceros permanece opt-in y no se habilita en CI
   general sin aislamiento y autorización específicos.
2. Repositorios clonados, documentos y memoria recuperada son datos no
   confiables.
3. Una `next_action` no concede autorización para red, ejecución o mayor gasto.
4. Los casos públicos usan repositorios y revisiones explícitamente permitidos;
   no incluyen secretos ni checkouts privados.

## 4. Arquitectura objetivo mínima

```text
artifact discovery
      |
      v
candidate relation (mentions / tests / implements / configures)
      |
      v
verification capability + versioned verifier
      |
      +---- retrieval-only --------------------> no probatory mass
      |
      +---- deterministic static verification -> supports / refutes
      |
      +---- authorized dynamic verification ---> supports / refutes
      |
      v
claim records + independence groups
      |
      +---- retrieval coverage
      +---- evidential coverage
      +---- residual risk
      +---- completion and actionable next steps
```

El linker propone candidatos. El verificador decide únicamente afirmaciones
para las que dispone de una regla estrecha y falsable. La agregación consume
claims ya tipados; no infiere autoridad desde el score semántico.

## 5. Estrategia de entrega

El trabajo se divide en PRs pequeños y ordenados. Un agente no debe comenzar un
PR dependiente hasta que el anterior esté integrado o exista un commit base
explícito que incluya sus contratos.

| PR | Entrega | Dependencia | Riesgo |
|---|---|---|---|
| A | Baseline, invariantes y casos reproducibles | ninguna | medio |
| B | Riesgo residual monotónico | A | alto semántico |
| C | Capacidades de acción y próximas acciones honestas | B | medio |
| D | Protocolo de verificadores estáticos | C | alto arquitectónico |
| E | Primeros verificadores y liveness end-to-end | D | alto |
| F | Métricas aditivas y compatibilidad de reporte | E | medio |
| G | Frescura reproducible aplicada en origen | A, F | medio |
| H | Consolidación documental, benchmark y release | B–G | bajo técnico |

### 5.1 PR A — Congelar una baseline reproducible

**Objetivo:** impedir que documentación desactualizada vuelva a pasar CI.

Cambios previstos:

- En `examples/regenerate_case_studies.py`:
  - añadir `revision` completa e inmutable a cada entrada de
    `THIRD_PARTY_CASES`;
  - resolver y verificar exactamente esa revisión;
  - separar `generate_case`, `render_case` y `check_case`;
  - hacer que `--check --target <slug>` respete el target;
  - hacer que `--target all --check` compruebe los tres;
  - retornar código distinto de cero ante clone/fetch, revisión o comparación
    fallida;
  - distinguir mensajes `unavailable`, `stale`, `invalid_revision` y `fresh`;
  - no sobrescribir el Markdown si la evaluación no terminó correctamente.
- Fijar el perfil semántico, revisión del target, revisión del evaluador,
  configuración de frescura, presupuesto y fingerprint en un manifest o bloque
  estructurado consumible por el generador.
- Actualizar `.github/workflows/ci.yml` con un gate determinista. Si la red no es
  suficientemente estable, usar bundles de entrada fijados y mover la
  comprobación remota a un job programado; nunca convertir una indisponibilidad
  en éxito.
- Regenerar `case-study-argos.md`, `case-study-markupsafe.md` y
  `case-study-an-kla-memory.md` contra entradas fijadas.
- Corregir el lenguaje histórico: usar “evaluación cruzada independiente” sólo
  para Markupsafe y “dependencia operativa” para AN-KLA.

Pruebas obligatorias:

- `--check --target markupsafe` no inspecciona Argos;
- `--check --target all` detecta un único caso stale;
- fallo de clone/fetch produce exit distinto de cero;
- revisión distinta de la fijada se rechaza;
- una regeneración fallida conserva el archivo anterior byte a byte;
- dos ejecuciones con las mismas entradas producen salida idéntica.

Criterio de aceptación:

- ningún caso publicado puede permanecer stale sin que falle al menos un gate;
- los resultados actuales, aunque sean `coverage=0.0`, quedan publicados como
  baseline honesta y no como éxito del pipeline corregido.

### 5.2 PR B — Reparar `residual_risk`

**Objetivo:** hacer el riesgo monotónico respecto de evidencia no probatoria y
contradicciones.

Trabajo previo a la fórmula:

- escribir tests de propiedades para los invariantes de la sección 3.2;
- separar proposiciones probatorias de relaciones de recuperación;
- decidir si la contradicción se agrega por claim o por aspecto. Se recomienda
  por claim normalizado y después por aspecto para evitar que duplicados
  multipliquen riesgo;
- documentar la calibración y sus límites en `MODEL.md` antes de fijar nuevos
  números golden.

Forma de referencia, sujeta a los tests y a la decisión normativa:

```text
missing_share = required aspects without positive support / required aspects
contradiction_share = contradicted probatory claims / probatory claims
risk = missing_share + (1 - missing_share) * contradiction_share
```

No se debe copiar esta expresión mecánicamente si la revisión de `MODEL.md`
elige otra agregación. Sí son obligatorias estas consecuencias:

- `missing_share=1` implica `risk=1`;
- `mentions` no aparece en ningún denominador probatorio;
- no se necesita un caso especial basado en `len(propositions)`.

Archivos esperados:

- `argos_epistemic/algorithm.py`;
- `tests/test_claims.py` o un nuevo `tests/test_risk.py`;
- `MODEL.md`, `ARCHITECTURE.md`, `docs/api.md`;
- fixtures y casos generados afectados.

Criterio de aceptación:

- las propiedades pasan con cero, una y muchas relaciones `mentions`;
- duplicar un `mention` no cambia el score;
- añadir un `refutes` no reduce el score;
- los casos simbólicos sin soporte reportan riesgo máximo.

### 5.3 PR C — Alinear utilidad, capacidades y `next_actions`

**Objetivo:** impedir que el planificador optimice beneficios inalcanzables.

Modelo mínimo de capacidad por acción:

```text
retrieval_only
structural_relation
probatory_static
probatory_dynamic
```

Cada extractor o acción declara su capacidad y el perfil que la respalda. La
capacidad no se deriva del nivel L0–L5 ni de la confianza nominal.

Cambios previstos:

- `generate_candidate_actions` asigna ganancia esperada de cobertura igual a
  cero a `retrieval_only` y `structural_relation`;
- la utilidad separa ganancia de recuperación, ganancia probatoria y reducción
  esperada de riesgo;
- la estimación conserva incertidumbre y perfil de calibración;
- `next_actions` añade, de forma aditiva:
  - `addresses_reason_codes`;
  - `remaining_blockers`;
  - `expected_effect`;
  - `capability_required`;
  - `sufficient_if_successful`;
  - `authorization_required`;
- `increase_read_limit` sólo promete resolver truncación. Si no existe una ruta
  probatoria posterior, se marca como diagnóstica e insuficiente;
- cuando falta soporte, el reporte propone habilitar o añadir un verificador
  compatible, sin ejecutar nada automáticamente.

Pruebas obligatorias:

- una acción estática de sólo recuperación tiene delta probatorio cero;
- el orden de acciones cambia sólo por métricas declaradas;
- `increase_read_limit` conserva los bloqueos no resueltos;
- ninguna acción dinámica se ejecuta por aparecer en `next_actions`;
- serialización y consumidores toleran los campos aditivos.

### 5.4 PR D — Introducir el protocolo de verificación estática

**Objetivo:** crear una frontera explícita entre candidato temático y prueba.

Diseño recomendado:

- añadir un módulo pequeño, por ejemplo `argos_epistemic/verifiers.py`;
- definir un protocolo que reciba artefacto, claim candidato, objetivo y contexto
  permitido, y devuelva cero o más resultados de verificación;
- cada resultado incluye:
  - `verifier_profile` versionado;
  - claim normalizado y scope;
  - `supports` o `refutes`;
  - evidencia y dependencias;
  - método (`deterministic`, `symbolic-rule`, `dynamic`);
  - confianza calibrada;
  - grupo de independencia;
  - limitaciones y degradaciones;
- un verificador no acepta autoridad autodeclarada dentro del target;
- una excepción o input no soportado produce resultado desconocido/degradado,
  nunca soporte por defecto;
- el registro de verificadores es explícito y determinista.

No incluir todavía:

- adjudicación LLM como soporte;
- ejecución de terceros;
- inferencia interprocedural completa;
- plugin discovery remoto;
- cambios incompatibles de schemas.

Pruebas de contrato:

- mismo input y perfil producen el mismo resultado;
- input irrelevante produce cero claims probatorios;
- error interno no se convierte en `supports`;
- evidencia manipulada cambia fingerprint o falla verificación;
- dos outputs que comparten una dependencia raíz no cuentan automáticamente
  como fuentes independientes.

### 5.5 PR E — Implementar verificadores mínimos y demostrar liveness

**Objetivo:** probar una ruta real a `complete=True` sin confundir keywords con
verdad.

Seleccionar claims estrechos que puedan verificarse con reglas deterministas.
Ejemplos aceptables:

- configuración: “el manifest declara la dependencia X”;
- AST: “la función X contiene una rama que levanta Y”;
- estructura: “el símbolo X está definido en el módulo Y”;
- tests: “el test X importa o invoca el símbolo Y”, sin afirmar que valida toda
  su semántica;
- ejecución dinámica autorizada: “la suite registrada terminó con el resultado
  Z bajo este entorno”.

No son aceptables claims amplios como “el sistema es seguro” o “la escritura es
correcta” derivados de una coincidencia o de una única suite general.

Plan de independencia:

- definir `independence_group` a partir del productor, dependencia raíz y método;
- dos claims derivados del mismo artefacto o del mismo run cuentan como una
  fuente para corroboración;
- una regla estática y una ejecución dinámica pueden corroborar sólo si prueban
  el mismo claim y sus dependencias no colapsan en la misma observación;
- documentar cuándo dos fuentes son complementarias pero no independientes.

Prueba end-to-end obligatoria:

1. crear un repositorio fixture local mínimo;
2. extraerlo mediante `analyze_path`;
3. producir al menos dos soportes independientes para cada aspecto requerido;
4. alcanzar los umbrales sin overrides de prueba engañosos;
5. obtener `complete=True`;
6. mutar una de las condiciones verificadas y comprobar que coverage, riesgo o
   completion cambian de forma explicable.

Criterio de aceptación:

- existe una ruta automática y segura a completion;
- los casos negativos e indeterminados permanecen no probatorios;
- el test no declara `supports` manualmente en el fixture de entrada.

### 5.6 PR F — Evolucionar métricas y reporte de forma aditiva

**Objetivo:** distinguir capacidad, recuperación y prueba sin romper consumidores.

Campos recomendados:

```text
coverage                       # alias numérico compatible
evidential_coverage            # mismo valor probatorio durante la migración
retrieval_coverage             # aspectos con candidatos relevantes
structural_coverage            # opcional, relaciones tipadas no probatorias
coverage_capability            # unavailable | partial | probatory
verification_profiles          # perfiles habilitados/ejecutados
```

Reglas:

- `coverage` y `evidential_coverage` deben coincidir durante el ciclo de
  compatibilidad;
- `retrieval_coverage` nunca alimenta `should_stop` probatorio;
- `coverage_capability=unavailable` implica `complete=False` y un reason code
  explícito, sin introducir `null` en comparaciones existentes;
- el eventual uso de `null` o retiro de `coverage` requiere un nuevo contrato y
  una migración separada;
- documentar deprecación sólo cuando exista al menos un consumidor migrado y un
  calendario de versión.

Actualizar:

- `README.md`, `MODEL.md`, `ARCHITECTURE.md`, `docs/api.md` y
  `docs/contracts.md`;
- tests de reporte y compatibilidad;
- renderer de casos y benchmarks;
- changelog con semántica anterior/nueva y guía para consumidores.

### 5.7 PR G — Aplicar frescura reproducible en origen

**Objetivo:** evitar mutaciones post-hoc incompatibles con el cálculo usado.

Cambios previstos:

- parametrizar extracción con una política explícita, por ejemplo:
  - `observed_at`;
  - `timestamp_source` (`filesystem`, `git`, `fixed`, `unavailable`);
  - `freshness_profile` versionado;
- calcular timestamp, frescura y relevancia una sola vez bajo esa política;
- prohibir que el generador sobrescriba campos después de la extracción;
- registrar la normalización en manifest y run attestation según corresponda;
- separar un caso determinista con reloj fijado de una prueba longitudinal de
  staleness;
- preferir tiempo de commit o una fuente fijada sobre `mtime` de checkout cuando
  el objetivo sea reproducibilidad histórica.

Pruebas obligatorias:

- checkout con mtimes distintos y política fija produce el mismo núcleo;
- política real conserva y penaliza antigüedad;
- el `relevance` reportado corresponde a la frescura reportada;
- cambiar `observed_at` cambia únicamente campos y fingerprints previstos;
- artefactos sin timestamp declaran neutralidad/degradación explícita.

### 5.8 PR H — Consolidación, documentación y release

**Objetivo:** cerrar la remediación sin dejar contratos o ejemplos divergentes.

Trabajo:

- regenerar benchmarks y todos los casos desde un worktree limpio;
- actualizar `ROADMAP.md`: reabrir la parte de H8 durante la remediación y
  cerrarla sólo cuando los tres casos estén protegidos;
- actualizar el estado del Incremento 3 para distinguir “claims tipados” de
  “pipeline probatorio viable”;
- añadir una sección de migración a `CHANGELOG.md`;
- actualizar `CONTRIBUTING.md` con el gate de todos los casos y el orden de
  regeneración;
- revisar `docs/threat-model.md` si se incorpora nueva ejecución o autoridad;
- verificar que README no use los casos como certificación general;
- retirar documentación histórica sólo si existe una política de archivo; de
  otro modo conservarla con fecha, commit y estado histórico visibles;
- decidir versión del paquete según compatibilidad real. Los campos aditivos
  pueden entrar en una minor pre-1.0; un schema incompatible exige versión de
  schema nueva aunque el paquete siga pre-1.0.

Criterio de salida:

- código, modelo, arquitectura, API, contratos, casos y benchmark describen la
  misma semántica;
- todos los gates públicos y AN-KLA pasan desde un checkout limpio;
- no quedan documentos generados contra revisiones móviles;
- existe un reporte de migración para consumidores de `coverage`.

## 6. Estrategia de pruebas

### 6.1 Pirámide

1. **Unitarias:** fórmula de riesgo, capacidades, identidad, independencia y
   verificadores.
2. **Propiedades/metamórficas:** duplicar `mentions`, reordenar artefactos,
   cambiar mtimes, añadir refutaciones y compartir dependencias.
3. **Integración:** `extract_system -> analyze_system`, generador y schemas.
4. **End-to-end local:** `analyze_path` alcanza completion sobre fixture seguro.
5. **Regresión real:** repositorios terceros fijados, sin tratarlos como gold de
   verdad total.
6. **Compatibilidad:** reporte antiguo/nuevo y schemas coexistentes.

### 6.2 Matriz mínima

| Escenario | Recuperación | Soporte | Riesgo | Complete |
|---|---:|---:|---:|---:|
| sin artefactos | 0 | 0 | 1 | false |
| sólo mentions | >0 | 0 | 1 | false |
| mentions + refutes | >0 | 0 | 1 | false |
| un support | >0 | parcial | >umbral o fuentes insuficientes | false |
| dos supports dependientes | >0 | una fuente efectiva | insuficiente | false |
| dos supports independientes | >0 | suficiente según pesos | bajo | potencialmente true |
| soporte + contradicción | >0 | mixto | aumentado | false si bloqueante |
| verificador unavailable | >0 | 0 | máximo/explicado | false |

### 6.3 Gates por PR

```bash
.venv/bin/python -m ruff check argos_epistemic bench tests scripts
.venv/bin/python -m mypy argos_epistemic
.venv/bin/python -m pytest
.venv/bin/python -c "import argos_epistemic; print(argos_epistemic.run())"
.venv/bin/python examples/regenerate_case_studies.py --target all --check
.venv/bin/python bench/run_benchmark.py --check
.venv/bin/python -m an_kla --project-root . context status
.venv/bin/python -m an_kla --project-root . status
.venv/bin/python -m an_kla --project-root . verify
```

Si el backend denso requiere un modelo no disponible, el gate debe fijar y
provisionar su dependencia o seleccionar explícitamente un perfil sin red. No
debe descubrir la red accidentalmente durante una prueba local.

## 7. Plan de documentación

| Documento | Actualización requerida |
|---|---|
| `MODEL.md` | semántica normativa de riesgo, cobertura y corroboración |
| `ARCHITECTURE.md` | frontera candidato/verificador/agregador |
| `docs/api.md` | campos aditivos, capacidades y comportamiento de completion |
| `docs/contracts.md` | compatibilidad, autoridad e independencia |
| `docs/threat-model.md` | ejecución, repos externos y autoridad de verificadores |
| `README.md` | explicación corta de métricas y límites |
| `ROADMAP.md` | estado real de H8 y viabilidad probatoria |
| `CONTRIBUTING.md` | gates, regeneración y revisión semántica |
| `CHANGELOG.md` | migración y cambios observables |
| `examples/case-study-*.md` | resultados generados y revisiones fijadas |
| `bench/*.md` | separar selección, prueba y completion |

Todo cambio semántico se documenta en el mismo PR. Los Markdown generados no se
editan manualmente; se cambia el generador y se regenera.

## 8. Protocolo operativo para agentes de IA

### 8.1 Inicio de cada sesión material

1. Leer `AGENTS.md` y `AN-KLA.md` completos.
2. Ejecutar preflight, `status` y `verify` de AN-KLA.
3. Ensamblar contexto sólo para el PR activo.
4. Ejecutar `git status --short` y atribuir cambios preexistentes.
5. Leer este plan, los archivos del PR y las pruebas relacionadas.
6. Declarar alcance y no objetivos antes de editar.
7. No iniciar un PR posterior para esquivar un gate fallido del actual.

### 8.2 Durante la implementación

- usar `apply_patch` para cambios manuales;
- no editar `AN-KLA.md`, bloques gestionados o Markdown generado directamente;
- mantener commits y PRs enfocados;
- añadir el test que falla antes o junto al cambio semántico;
- evitar comentarios en código; expresar intención en docstrings o documentos;
- no descargar modelos ni ejecutar terceros sin autorización y perfil explícito;
- no relajar assertions, thresholds o reason codes para obtener verde;
- preservar outputs negativos y degradaciones;
- registrar decisiones de compatibilidad en el PR;
- coordinar propiedad de archivos si varios agentes trabajan en paralelo;
- nunca permitir ediciones concurrentes sobre `algorithm.py`, schemas o el
  generador sin una base y responsable únicos.

### 8.3 Handoff entre agentes

Cada entrega debe incluir:

```text
objetivo del PR
commit base y HEAD
archivos modificados
invariantes afectados
decisiones tomadas y descartadas
tests ejecutados y resultados
gates no ejecutados con motivo
outputs generados
compatibilidad y migración
riesgos o preguntas abiertas
estado AN-KLA y referencias escritas
```

El siguiente agente verifica el handoff contra Git y pruebas; no lo trata como
autoridad suficiente.

### 8.4 Definition of Done de cada PR

- criterio de aceptación específico satisfecho;
- tests nuevos cubren la regresión y el camino feliz;
- ruff, mypy y pytest relevantes en verde;
- documentación afectada actualizada;
- outputs generados reproducibles y diff revisado;
- compatibilidad declarada;
- worktree sin cambios incidentales del agente;
- AN-KLA verificado y, si existe información durable nueva, actualizado sólo por
  `plan-write -> commit-write-plan`.

## 9. Observabilidad y criterios de éxito

Métricas técnicas que deben compararse antes y después:

- porcentaje de acciones con capacidad probatoria;
- delta esperado frente a delta observado de cobertura;
- retrieval coverage y evidential coverage por aspecto;
- proporción de claims por relación y autoridad;
- fuentes efectivamente independientes por claim;
- riesgo antes/después de duplicar `mentions`;
- tasa de `next_actions` que resuelven su reason code declarado;
- determinismo de casos fijados;
- bytes/tokens leídos antes de terminación;
- falsos `complete` y falsos bloqueos sobre fixtures adjudicados.

Éxito no significa maximizar coverage. Significa que cada aumento puede
explicarse mediante soporte auditable y que ausencia, contradicción e
indisponibilidad no se ocultan.

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| volver al sobre-enlace previo | linker limitado a `mentions`; verificador separado |
| fabricar dos fuentes correlacionadas | grupos de independencia y dependencias raíz |
| romper consumidores de `coverage` | campos aditivos y alias durante migración |
| CI inestable por red | revisiones y bundles fijados; job remoto separado |
| tests ajustados a números actuales | invariantes y propiedades antes de goldens |
| claims estáticos demasiado amplios | claims estrechos y perfiles versionados |
| frescura reproducible pero irreal | perfiles `fixed` y `real` separados |
| ejecución dinámica insegura | opt-in, aislamiento y autorización externa |
| documentación vuelve a divergir | checks de todos los outputs generados |
| cambios locales mezclados | status, atribución y PRs enfocados |

## 11. Rollback y recuperación

- Cada PR debe poder revertirse sin depender de los posteriores.
- Los schemas publicados no se reescriben; un contrato defectuoso se sustituye
  mediante versión nueva.
- Los casos anteriores se conservan en Git como historia, no como archivos
  duplicados activos.
- Si un verificador genera falsos soportes, se deshabilita su perfil, se marca la
  degradación y se regenera la evidencia afectada; no se convierte su salida en
  `mentions` silenciosamente.
- Si una revisión tercera desaparece, el gate falla con diagnóstico y conserva
  el último output; no lo declara fresco.
- Si una fórmula nueva de riesgo no satisface propiedades, se revierte el PR B
  completo antes de recalibrar thresholds.

## 12. Decisiones abiertas que requieren aprobación humana

1. Fórmula normativa final y calibración de `residual_risk`.
2. Definición exacta de independencia entre fuentes.
3. Primer conjunto de verificadores estáticos autorizado.
4. Política de red para casos terceros en CI.
5. Duración del ciclo de compatibilidad de `coverage`.
6. Versión de paquete y schemas que transportará las métricas nuevas.
7. Si los casos de staleness serán parte de CI o un benchmark longitudinal.

Los agentes pueden preparar evidencia y alternativas, pero no deben convertir
estas decisiones en hechos consumados fuera del PR que las apruebe.

## 13. Orden inmediato recomendado

1. Ejecutar PR A y publicar la baseline honesta.
2. Ejecutar PR B con tests de propiedades antes de modificar la fórmula.
3. Ejecutar PR C para que la selección deje de prometer coverage imposible.
4. Diseñar PR D y someter el protocolo a revisión antes de añadir verificadores.
5. Implementar PR E y exigir la prueba end-to-end de liveness.
6. Añadir métricas compatibles en PR F.
7. Corregir frescura en PR G.
8. Cerrar documentación y release en PR H.

No comenzar CLI, MCP, API remota o billing sobre esta base hasta que PR E
demuestre que el núcleo puede producir soporte auditable y completar al menos un
objetivo realista sin inyección manual de `supports`.
