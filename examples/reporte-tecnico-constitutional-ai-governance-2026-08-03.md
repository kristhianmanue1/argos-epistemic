# Reevaluación técnica de `constitutional-ai-governance` con Argos

**Fecha:** 2026-08-03
**Destinatario:** equipo de desarrollo y gobernanza de CAGF
**Repositorio:** `https://github.com/kristhianmanue1/constitutional-ai-governance`
**Revisión evaluada:** `5459d0c7a7a9308e54c20731217d0e6ec9253349` (`main`)
**Harness externo observado:** `cagf-conformance-harness@7de00aececd67c18336c2aeb72f302862205a79d`
**Evaluador:** `argos@ddfd52f2696eb63136ddf27130b924960319ae6b`
**Resultado general:** núcleo documental y guards locales consistentes, pero la frontera recién separada canon↔harness dejó CI y reproducibilidad compuesta en estado no autocontenido.

## 1. Resumen ejecutivo

CAGF es un framework semiformal de gobernanza constitucional para sistemas de
IA. Su superficie combina doctrina, definiciones tipadas, contratos de
conformidad, un artefacto Lean, guards Python, una cadena EventLog y un proceso
documental de ratificación. Esta evaluación fue de sólo lectura sobre clones
temporales; no constituye una enmienda, voto, ratificación ni participación en
un asiento de gobernanza.

La comprobación directa encontró una base técnicamente valiosa:

- los guards constitucionales locales pasan;
- 46 pruebas residentes pasan;
- el artefacto Lean compila con Lean 4.15.0;
- la cadena EventLog de 191 registros verifica bajo el perfil invocado por CI;
- el reloj de aplicaciones interinas no presenta vencimientos;
- los 16 teoremas SMT sobre la forma de P3/P4/C3 resultan `PROVED`;
- el gate P3 pasa cuando el harness externo correcto está disponible.

Sin embargo, el estado publicado de `main` presenta cuatro problemas de alta
prioridad:

1. **P0 — GitHub Actions está rojo:** el workflow no instala `PyYAML`, requerido
   antes de alcanzar los gates principales.
2. **P0 — el checkout limpio no es autocontenido:** tras instalar PyYAML,
   `ci_check.sh` falla con 19 referencias de evidencia ausentes si no existe el
   repositorio hermano `cagf-conformance-harness`.
3. **P1 — evidencia externa no ligada a identidad:** P3 acepta cualquier
   directorio indicado por `CAGF_HARNESS_ROOT` que contenga las rutas esperadas;
   no comprueba remote, commit, manifiesto ni hashes de archivos.
4. **P1 — documentación viva desincronizada:** README, VERSION, AGENTS y la
   salida del CI todavía describen `examples/` como el harness ejecutable local
   y la suite como si incluyera paridad JS, aunque ese contenido fue extraído.

El fallo remoto es observable en el workflow público de la revisión evaluada:
`https://github.com/kristhianmanue1/constitutional-ai-governance/actions/runs/30716857585`.
El log termina en `ModuleNotFoundError: No module named 'yaml'`.

La separación del harness fue autorizada y está documentada. El defecto no es
haber separado repositorios, sino que la composición posterior no quedó
materializada como una dependencia reproducible en clones limpios y CI.

## 2. Alcance y método

La evaluación usó dos carriles independientes:

### 2.1 Carril Argos

- descubrimiento multinivel;
- grafo de llamadas Python;
- clasificación estática de comportamiento;
- síntesis con linker léxico;
- síntesis con surrogate de embeddings determinista;
- comparación entre scores, conflictos y cobertura.

### 2.2 Carril directo

- clon limpio de CAGF;
- ejecución del entrypoint canónico `scripts/ci_check.sh`;
- ejecución separada de los gates posteriores al primer fallo;
- compilación de Lean;
- verificación EventLog;
- ejecución SMT;
- inspección de GitHub Actions;
- clon del harness externo y repetición de la composición esperada;
- revisión de actos de extracción, contratos y fuentes de verdad.

Las conclusiones sobre defectos usan el carril directo. Los scores de Argos se
conservan como señales heurísticas.

## 3. Línea base

| Elemento | Valor |
|---|---|
| CAGF `HEAD/main` | `5459d0c7a7a9308e54c20731217d0e6ec9253349` |
| Harness `HEAD/main` | `7de00aececd67c18336c2aeb72f302862205a79d` |
| Argos | `ddfd52f2696eb63136ddf27130b924960319ae6b` |
| Python local | 3.12.12 |
| Lean | 4.15.0 |
| Z3 | 4.16.0 |
| Archivos rastreados | 1061 |
| Markdown rastreados | 885 |
| Python rastreados | 34 |
| Lean rastreados | 1 |
| Archivos `.cagf/` rastreados | 752 |
| EventLog | 191 registros |

El repositorio no declara un archivo de dependencias Python consolidado para
CI. El workflow instala únicamente `pytest` e `hypothesis`, aunque varios
scripts importan `yaml` y `verify_gates_smt.py` importa Z3.

## 4. Resultados directos

### 4.1 Entry point canónico en un clon limpio

Comando:

```bash
./scripts/ci_check.sh
```

Los guards iniciales pasan:

```text
A1 baseline:                 5/5 OK
A3 finite urgency:           OK
sorts hygiene:               OK
axiom identity:              OK
P0 adherence:                OK
artifact registry:           OK
INDEX:                       in sync
```

Después, el gate P3 falla con 19 rutas ausentes. Entre ellas:

```text
examples/runner/cases/c2_killswitch.py
examples/runner/cases/c3_token_budget.py
examples/runner/cases/c1_quorum.py
examples/runner/core/engine.py
examples/runner/core/a10_integration.py
examples/runner/core/adial_workflow.py
examples/tests/test_engine_parity.py
examples/tests/test_a9_delegation.py
examples/tests/test_a_live_h5.py
```

Esas rutas fueron eliminadas del canon por el commit `225b105`, que extrajo
110 archivos al harness externo. El gate fue adaptado para buscar primero en el
canon y luego en:

```text
../cagf-conformance-harness
```

o en la ruta aportada por `CAGF_HARNESS_ROOT`.

Por tanto, el clon limpio del repositorio evaluado no puede ejecutar por sí solo
su entrypoint canónico.

### 4.2 Composición con el harness externo

Se clonó el harness en la ruta hermana esperada y se repitió el comando. Su
`main` continúa exactamente en `7de00ae`, la revisión registrada en las actas
de publicación del 2026-07-21.

Resultado:

```text
GATE PASS — pre-ratification gate v0.3
INTERIM CLOCK OK
Lean A2: OK
EventLog: OK — 191 registros
46 passed
ALL CHECKS GREEN
```

Esto confirma que el contenido publicado del harness todavía satisface las
rutas nominales. También confirma que la ejecución verde depende del layout
ambiental y no sólo del commit CAGF.

### 4.3 GitHub Actions

Los diez workflows públicos más recientes consultados terminan en `failure`.
En la corrida correspondiente a `5459d0c`, el primer fallo es:

```text
ModuleNotFoundError: No module named 'yaml'
```

El workflow ejecuta:

```yaml
- run: pip install pytest hypothesis
- run: ./scripts/ci_check.sh
```

pero `test_artifact_registry.py` y los gates usan PyYAML.

Incluso tras añadir PyYAML, el workflow seguiría sin reproducir la composición
local verde porque:

- `actions/checkout` clona únicamente el canon;
- no clona `cagf-conformance-harness`;
- no configura `CAGF_HARNESS_ROOT`;
- el gate P3 falla cerrado cuando las rutas no existen en ninguno de los roots.

La afirmación en `AGENTS.md` de que CI de servidor está inactivo no coincide con
el estado observable: existe `.github/workflows/ci.yml`, se activa en push/PR y
produce ejecuciones fallidas.

### 4.4 Gates ejecutados por separado

Para no confundir el primer fallo con el estado del resto, se ejecutaron los
gates posteriores individualmente:

| Gate | Resultado | Límite |
|---|---|---|
| Interim clock | PASS | No hay excepciones abiertas vencidas |
| Lean A2 | PASS | Prueba un resultado negativo acotado, no todo CAGF |
| EventLog | PASS | Sin manifiesto esperado ni checkpoint en el perfil CI |
| Pytest residente | 46 PASS | Ya no incluye el harness extraído |
| SMT P3/P4/C3 | 16 PROVED | Prueba forma lógica del gate; runtime P3 falla sin harness |
| Hito 3 verifier | PASS | Declara explícitamente lo que no verifica |
| Oracle seal | PASS | Sello in-repo re-sellable; limitación declarada |

La salida de EventLog es honesta:

```text
NO verificado: manifiesto (sin --expected-manifest), checkpoint (sin --checkpoint)
```

No se considera un fallo oculto, pero sí una diferencia entre “cadena
verificada” y “ratificación estricta reconstruida”.

## 5. Resultados de Argos

### 5.1 Extracción

Objetivo:

```text
auditoria-gobernanza-constitucional
aspects = governance, axiom, conformance, ratification, test
```

Resultado estructural:

| Métrica | Valor |
|---|---:|
| Artefactos del sistema | 434 |
| Evidencias observadas por la corrida léxica | 442 |
| L0 / L1 / L2 / L3 / L4 / L5 | 12 / 1 / 19 / 1 / 400 / 1 |
| Docs clasificados | 410 |
| Config clasificada | 19 |
| Nodos de call graph | 191 |
| Aristas | 331 |
| Funciones de producción | 128 |
| Funciones con `raise` | 22 |
| Funciones con `assert` | 46 |
| Funciones que mutan `self` | 4 |
| Funciones clasificadas como validación | 10 |

Top de impacto sintáctico:

```text
verify_gates_smt.main       0.370
trace_verify.main           0.354
verify_gates_smt.verify_p3  0.339
verify_gates_smt.verify_p4  0.339
verify_gates_smt.verify_c3  0.339
```

El resultado es coherente con un repositorio donde la mayor superficie
ejecutable reside en verificadores y trazabilidad.

### 5.2 Límite de discovery

Argos impone `MAX_CODE_ARTIFACTS = 400`. CAGF tiene 885 archivos Markdown y
1061 archivos rastreados; sólo 434 artefactos entraron al sistema y 400 ocuparon
L4. La selección depende del orden lexicográfico del recorrido.

Consecuencias:

- el análisis no cubre todo el corpus documental;
- documentos tardíos en orden de ruta pueden quedar fuera;
- “niveles cubiertos” no significa corpus cubierto;
- una cobertura semántica de 0.8 no puede interpretarse como 80 % del repositorio;
- el gran volumen de documentos de proceso domina la señal frente al pequeño
  núcleo formal.

Este es un límite de Argos, no de CAGF.

### 5.3 Sensibilidad semántica

| Perfil | Léxico | Embedding surrogate |
|---|---:|---:|
| Evidencias | 442 | 357 |
| Proposiciones | 0 | 226 |
| Cobertura | 0.0000 | 0.8000 |
| Riesgo residual | 1.0000 | 0.0000 |
| Conflictos | 0 | 5 |
| `complete` | `false` | `true` |

Puntuaciones con surrogate:

```text
governance   1.0000
conformance  1.0000
ratification 1.0000
test         0.6667
axiom        0.3333
```

Los cinco conflictos emparejan prompts, ballots, planes y resúmenes del grafo
sin demostrar contradicción textual. Por ejemplo, un ballot N23 se enfrenta a
un ballot N24 por compartir el aspecto `ratification`. Se consideran conflictos
sintéticos no adjudicados.

Argos marca `complete=true` aun con cinco conflictos abiertos de severidad 0.5.
El modelo sólo bloquea por conflictos críticos; para auditorías de gobernanza,
esa política es demasiado permisiva. La conclusión directa de esta evaluación
no usa ese indicador.

## 6. Hallazgos priorizados

### CAG-R1-01 — Workflow remoto sin dependencias completas

**Prioridad:** P0
**Estado:** confirmado local y remotamente
**Superficie:** `.github/workflows/ci.yml`

El workflow omite PyYAML. Los checks llevan múltiples ejecuciones consecutivas
en rojo y la revisión actual falla antes del gate P3.

Recomendación:

- declarar dependencias en un archivo versionado y bloqueable;
- instalar PyYAML además de pytest/hypothesis;
- incluir Z3 sólo si `verify_gates_smt.py` pasa a ser parte del entrypoint;
- añadir un smoke test del entorno desde cero;
- fijar acciones por SHA en vez de tags móviles si la política del proyecto lo
  exige para otras superficies de confianza.

Criterio de cierre: el workflow de `main` pasa desde un runner limpio y el
comando de instalación se deriva de una fuente de dependencias mantenida.

### CAG-R1-02 — CI canónico depende de un sibling implícito

**Prioridad:** P0
**Estado:** confirmado
**Superficie:** `scripts/check_pre_ratification_gate.py`, `ci_check.sh`

El acto Lote 1 afirma simultáneamente:

- que los guards corren sin depender del harness;
- que RT1 busca evidencia en el harness externo y falla cerrado si no existe.

La segunda afirmación describe el comportamiento real. Los guards sintácticos
individuales son autocontenidos, pero el entrypoint canónico completo no lo es.

Recomendación: elegir y documentar uno de estos modelos:

1. **CI del canon autocontenido:** P3 valida un manifiesto/puntero firmado sin
   exigir el checkout externo; la ejecución del harness vive en su propio CI.
2. **CI compuesto:** el workflow clona explícitamente el harness fijado, verifica
   identidad y ejecuta P3 con `CAGF_HARNESS_ROOT`.

No mantener una dependencia opcional por convención de nombre de directorio.

### CAG-R1-03 — El gate externo verifica existencia, no identidad

**Prioridad:** P1
**Estado:** confirmado por código
**Superficie:** P3/RT1

Para cada evidencia, el gate sólo evalúa:

```python
any((root / ev_path).exists() for root in search_roots)
```

No verifica:

- URL/remote del harness;
- commit `7de00ae`;
- correspondencia con una versión del canon;
- hash del manifiesto;
- hash o contenido de cada evidencia;
- que la evidencia ejecutable haya sido ejecutada;
- resultado o certificado de la suite externa.

Una estructura de archivos nominalmente compatible satisface RT1. La etiqueta
“real witness” en el mensaje de éxito es más fuerte que la comprobación.

Recomendación:

- crear un descriptor machine-readable canon↔harness;
- fijar repo URL, commit, versión, manifiesto y digest;
- comprobar que `git rev-parse HEAD` y `remote.origin.url` coincidan;
- verificar hashes de evidencias;
- separar `evidence_exists` de `evidence_executed`;
- consumir un certificado de suite ligado al commit cuando se afirme ejecución.

### CAG-R1-04 — Fuentes de verdad no actualizadas después de la extracción

**Prioridad:** P1
**Estado:** confirmado
**Superficie:** README, VERSION, AGENTS, mensajes CI

Ejemplos:

- README: “The executable harness in `examples/`...”;
- VERSION: fila vigente “`examples/` (harness)”;
- AGENTS: “`examples/` (harness ejecutable)” y “harness completo” en CI;
- `ci_check.sh`: “Examples harness suite (incl. JS engine parity via node)”.

En la revisión evaluada, `examples/runner`, el engine JS, la paridad JS y la
mayoría de las pruebas ya no existen en el canon. El comando final ejecuta 46
pruebas residentes, no el harness completo.

Recomendación:

- actualizar las cuatro superficies en el mismo acto;
- distinguir `canon guards`, `external harness` y `composed conformance run`;
- añadir el harness al registro de herramientas externas;
- registrar su versión/commit vigente en VERSION o en un lock descriptor;
- cambiar el texto del CI para describir exactamente lo ejecutado.

### CAG-R1-05 — Registro externo omite el harness que ya es dependencia

**Prioridad:** P1
**Estado:** confirmado
**Superficie:** `docs/EXTERNAL-TOOLS-REGISTRY-v0.1.md`

El registry lista `cagf-audit`, `cagf-dashboard` y `cagf-memory`, pero no
`cagf-conformance-harness`. Al mismo tiempo, P3 lo consume como fuente de
evidencia para superficies ratificadas.

Recomendación: registrar el harness con URL pública, commit, contrato, estado,
última verificación y conformance hash. Una ruta absoluta local no es una
identidad portable.

### CAG-R1-06 — Contrato de harness v0.3 quedó históricamente congelado

**Prioridad:** P2
**Estado:** confirmado
**Superficie:** `N6-CONFORMANCE-HARNESS-CONTRACT-v0.3.md`

El contrato aún declara:

```text
harness_repo: ruta local, aún no creado
runtime_state: UNEXECUTED — reauditoría pendiente
```

Las actas posteriores registran que fue creado/publicado y luego reutilizado en
Lote 1. Si el header es histórico e inmutable, no debe editarse; debe existir un
contrato sucesor o descriptor vigente que resuelva el estado actual.

### CAG-R1-07 — Verificación EventLog de CI no usa el perfil estricto disponible

**Prioridad:** P2
**Estado:** limitación declarada, oportunidad de endurecimiento

CI invoca `trace_verify --check`, que verifica digests SQLite, cadena, parents,
ciclos, tipos, tablero y firmas, pero omite manifiesto esperado y checkpoint.
El propio CLI dispone de `--ratify`, `--expected-manifest`,
`--manifest-sig-key` y `--checkpoint`.

No es una falsa afirmación en stdout, pero el nombre “EventLog chain
verification” puede confundirse con reconstrucción integral. Se recomienda:

- mantener el perfil rápido para cada cambio;
- añadir un job estricto periódico o para tags/ratificación;
- conservar externamente el ancla que impida re-sellar historia junto con el
  repositorio.

### CAG-R1-08 — CI configura Node pero ya no ejecuta JavaScript

**Prioridad:** P3
**Estado:** confirmado

El workflow instala Node 20 y el script anuncia paridad JS, pero los tests de
engine parity y la implementación JS fueron extraídos. Esto añade tiempo,
advertencias de deprecación y una señal de cobertura inexistente.

Eliminar Node del CI del canon o usarlo únicamente en un job compuesto que
clone y ejecute el harness.

## 7. Aspectos que no se clasifican como defectos

### 7.1 A2 formalizado sólo parcialmente

El único archivo Lean prueba que una cota de correlación escalar no determina
el fallo conjunto. VERSION describe A2 como doctrinal/deferred y el script
declara “negative result”. La limitación está expuesta; no se presenta aquí
como incumplimiento.

### 7.2 A10 representacional con runtime diferido

La matriz etiqueta A10 como `representational`, limita cobertura al universo
declarado y declara `runtime_gate: deferred`. Aunque `aggregation_status` usa
`end_to_end_governed`, el resto del contrato impide interpretar esto como una
garantía universal. Conviene revisar el nombre del estado, pero no se halló una
promoción runtime oculta en esta evaluación.

### 7.3 GitHub Actions “inactivo”

No se interpreta como decisión de desactivar garantías: técnicamente el workflow
está activo y genera fallos. La documentación debe escoger entre deshabilitarlo
realmente o mantenerlo verde.

## 8. Plan de refinamiento recomendado

### Fase 1 — Restaurar una línea base verificable

1. Crear una declaración de dependencias para los guards.
2. Corregir GitHub Actions para instalar PyYAML.
3. Decidir CI autocontenido o compuesto.
4. Si es compuesto, clonar el harness a commit exacto y verificarlo.
5. Conseguir una ejecución verde en `main`.

### Fase 2 — Cerrar la identidad canon↔harness

1. Crear `harness-lock.yaml` o equivalente.
2. Incluir URL, commit, versión, manifiesto SHA-256 y versión CAGF compatible.
3. Hacer que P3 valide el descriptor antes de revisar rutas.
4. Verificar hashes de evidencia o un certificado ligado al commit.
5. Añadir tests adversariales: repo equivocado, commit equivocado, archivo vacío,
   manifiesto alterado y suite no ejecutada.

### Fase 3 — Sincronizar superficies públicas

1. Actualizar README, VERSION y AGENTS.
2. Corregir mensajes de `ci_check.sh`.
3. Añadir el harness al External Tools Registry.
4. Publicar un sucesor del contrato v0.3 sin reescribir el registro histórico.
5. Documentar el comando reproducible desde dos clones vacíos.

### Fase 4 — Endurecer trazabilidad

1. Ejecutar EventLog estricto en tags y actos de ratificación.
2. Mantener anclas externas de manifiesto/checkpoint.
3. Separar claramente integridad interna de completitud histórica.
4. Asociar los certificados del harness a eventos o releases identificables.

### Fase 5 — Refinar Argos para repositorios documentales grandes

1. Reportar archivos descubiertos, analizados y excluidos por el cap.
2. Evitar truncado lexicográfico silencioso a 400 artefactos.
3. Estratificar canon, histórico, prompts, ballots y código.
4. No generar conflictos sólo por polaridades débiles de documentos distintos.
5. Impedir `complete=true` con conflictos abiertos en perfil de auditoría.
6. Publicar perfiles semánticos separados y fingerprints reproducibles.

## 9. Criterios de cierre

La siguiente evaluación debería exigir:

- GitHub Actions verde sobre el commit evaluado;
- clon limpio reproducible sin dependencias ambientales implícitas;
- harness externo fijado por identidad y contenido;
- P3 capaz de rechazar un sibling con rutas correctas pero identidad incorrecta;
- documentación consistente con la frontera física actual;
- External Tools Registry con el harness;
- mensajes CI que no afirmen ejecutar JS o el harness completo cuando no lo hacen;
- EventLog estricto en al menos el perfil de ratificación/release;
- reporte Argos que declare el porcentaje real de corpus sometido a análisis.

## 10. Veredicto

CAGF muestra una disciplina de gobernanza y honestidad epistémica superior a la
media: conserva actos, limita claims, prueba regresiones formales concretas y
expone varios límites en la salida de sus verificadores. Los guards residentes,
Lean, SMT y EventLog funcionan en la revisión evaluada.

El riesgo principal actual no está en una fórmula constitucional detectada como
incorrecta, sino en la transición de arquitectura del repositorio. La extracción
del harness creó una composición distribuida sin lock ejecutable, sin bootstrap
de CI y sin sincronización completa de las fuentes de verdad. Como resultado,
`main` no tiene una señal verde reproducible desde un clon limpio y el gate de
“evidencia real” verifica presencia nominal, no procedencia.

La prioridad correcta es estabilizar esa frontera antes de ampliar axiomas,
contratos o tooling. Una vez que canon y harness estén ligados mediante identidad,
manifiesto y ejecución reproducible, los refinamientos formales volverán a
descansar sobre una base falsificable y portable.
