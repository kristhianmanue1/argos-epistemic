# Subplan técnico de la fase F: métricas epistémicas compatibles

Fecha: 2026-08-10<br>
Estado: propuesto para revisión antes de implementar<br>
Plan padre: `plan-mejoras-argos-remediacion-epistemica-2026-08-05.md`, §5.6<br>
Base verificada: `main@00900b225a8a9dbb3d2d81c1b33824dc216ec9a1`<br>
Rama preparada: `codex/phase-f-metrics`

## 1. Resultado perseguido

F elimina la inflación de cobertura por volumen de proposiciones y publica una
separación aditiva entre recuperación, estructura y prueba, sin retirar ni
cambiar el tipo del campo público `coverage`.

Al cerrar F deben cumplirse simultáneamente estas propiedades:

1. duplicar una proposición, un `evidence_id`, una raíz, una ejecución o una
   derivación no aumenta cobertura ni acerca `complete=True`;
2. sólo fuentes independientes que sostienen el mismo claim normalizado pueden
   corroborarse;
3. soportes de claims distintos del mismo aspecto no se suman como si fueran
   corroboración;
4. `coverage` continúa siendo un `float` en `[0, 1]` y es exactamente el alias
   compatible de `evidential_coverage`;
5. `retrieval_coverage` y `structural_coverage` son observables, pero nunca
   alimentan `should_stop`, `thresholds_met` ni `complete`;
6. ausencia de capacidad probatoria se informa de forma explícita y fuerza
   `complete=False`;
7. la fórmula usada por el reporte, la selección de acciones y la terminación
   es una sola implementación compartida;
8. el cambio permanece offline, determinista y acotado en costo.

## 2. Estado vigente confirmado contra código

En la base `00900b2`:

- `aspect_score` suma confianza por proposición positiva y divide entre
  `corroboration`; por eso duplicar una lectura aumenta el resultado;
- `compute_coverage` pondera `aspect_score` por los pesos de los aspectos;
- `compute_residual_risk` ya agrupa por claim y es invariante ante duplicación;
- `min_sources_met` ya corrobora por claim normalizado y componentes conexos de
  independencia;
- `should_stop` y `synthesize_report` reciben el `coverage` legacy;
- la simulación de utilidad llama la misma `compute_coverage`, por lo que una
  corrección sólo en el renderer dejaría decisiones internas incoherentes;
- `examples/regenerate_case_studies.py` y `bench/run_benchmark.py` consumen
  directamente `report["coverage"]`;
- no existe un schema versionado para el diccionario completo de reporte; los
  schemas publicados de bundle no contienen estas métricas y no deben
  reescribirse en F;
- existe una regresión marcada como `KNOWN-UNSOUND` y `REMOVAL TARGET: PR F`;
- la suite de la base contiene 943 tests.

## 3. Alcance y no objetivos

### 3.1 Dentro de F

- agregación probatoria por aspecto, claim normalizado y componente de
  independencia;
- campos aditivos de métricas y capacidad;
- reporte saneado de perfiles de verificación observados;
- integración con utilidad, parada y completion;
- compatibilidad del campo `coverage`;
- pruebas unitarias, metamórficas, adversariales, integración y rendimiento;
- actualización de documentación, renderer de casos, benchmark y changelog;
- regeneración determinista de los artefactos afectados.

### 3.2 Fuera de F

- cambiar `residual_risk`, sus umbrales o su calibración;
- ponderar `strength` como masa probatoria;
- cambiar los pesos de aspectos, `theta_coverage`, `rho_risk` o
  `min_sources_per_aspect` para conservar goldens;
- introducir `null`, retirar o renombrar `coverage`;
- modificar el significado de schemas publicados de bundle;
- aplicar la política de frescura de G;
- habilitar red, modelos densos o ejecución dinámica de terceros;
- publicar versión, tag o release, trabajo que pertenece a H;
- integrar los cambios preservados en `origin/codex/bench-user-preservation`;
- editar `bench/real_report.md` o `bench/real_repos.py`.

## 4. Contrato semántico propuesto

### 4.1 Vocabulario

- **claim key:** `claim_id` textual no vacío; si falta en una proposición
  legacy, identidad canónica derivada de aspecto, claim textual y scope. Datos
  malformados no se coercionan con `str()` y quedan fuera con diagnóstico.
- **componente independiente:** componente conexo producido por el protocolo D
  sobre raíces, ejecución, familia de instrumento y derivación.
- **confianza del componente:** máximo de las confianzas válidas dentro de un
  mismo componente. Repetir miembros del componente no suma masa.
- **score del claim:** masa de sus componentes independientes dividida entre
  `corroboration`, acotada a `[0, 1]`.
- **score del aspecto:** máximo score entre los claims positivos del aspecto.
  Claims diferentes no se corroboran entre sí.

### 4.2 Fórmula recomendada

Para cada aspecto requerido $a$ y claim positivo $c$:

$$
S(c) = \min\left(1,\frac{\sum_{g \in Groups(c)}\max_{p \in g} conf(p)}{\kappa}\right)
$$

$$
S(a) = \max_{c \in Claims(a)} S(c)
$$

$$
evidential\_coverage = \sum_{a \in A} w_a S(a)
$$

Donde $\kappa$ conserva el parámetro actual `corroboration`, validado como
finito y positivo. El orden de entrada no altera el resultado; se usa orden
canónico y `math.fsum`, y sólo se redondea en la frontera del reporte.

Reglas adicionales:

- sólo `supports` con polaridad, confianza y `strength` mayores que cero pueden
  entrar a $Claims(a)$;
- `strength` sigue siendo criterio de admisión, no multiplicador de confianza;
- `refutes` no aporta cobertura positiva y continúa afectando riesgo y
  conflictos por las rutas existentes;
- resultados directos de verificador sólo cuentan si su revisión coincide con
  la revisión objetivo ya validada por la frontera de admisión;
- soportes legacy sin procedencia completa conservan compatibilidad numérica,
  pero colapsan conservadoramente a un solo componente y no demuestran
  independencia múltiple;
- un `source_id` conflictivo se excluye usando la misma vista canónica de D; F
  no implementa otro algoritmo de deduplicación.

### 4.3 Métricas aditivas

El reporte añadirá:

```text
coverage                    float  # alias de evidential_coverage
evidential_coverage         float  # cobertura probatoria por claim/grupo
retrieval_coverage          float  # aspectos con relación recuperada útil
structural_coverage         float  # aspectos con tests/implements/configures
coverage_capability         str    # unavailable | partial | probatory
coverage_profile            str    # argos/claim-component-coverage-v1
coverage_parameters         object # parámetros efectivos auditables
verification_profiles       object # perfiles ejecutados observables
evidential_aspect_scores    object # score probatorio por aspecto
retrieval_aspect_scores     object # presencia 0/1 por aspecto
structural_aspect_scores    object # presencia 0/1 por aspecto
```

`aspect_scores` se conserva como alias compatible de
`evidential_aspect_scores`. Los aliases deben ser iguales después del mismo
redondeo, no sólo aproximadamente iguales.

`retrieval_coverage` es la suma ponderada de aspectos que poseen al menos una
relación admitida y positiva en fuerza entre `mentions`, `tests`, `implements`,
`configures`, `supports` o `refutes`. Mide recuperación observada, no candidatos
que nunca fueron leídos.

`structural_coverage` es la suma ponderada de aspectos con al menos una relación
admitida entre `tests`, `implements` o `configures`. No incluye `mentions`,
`supports` ni `refutes`.

Ambas métricas son binarias por aspecto e invariantes ante duplicación.

`coverage_profile` liga la fórmula a
`argos/claim-component-coverage-v1`. `coverage_parameters` publica al menos
`corroboration`, el operador de confianza por componente (`max`), el operador
por claim (`sum_components`) y el operador por aspecto (`max_claim`). Los
decimales se serializan según el contrato canónico vigente. El mismo perfil se
incluye en la configuración del evaluation manifest y del manifest de casos;
dos fórmulas distintas no pueden compartir silenciosamente identidad de
evaluación.

### 4.4 Capacidad y perfiles

Definición inicial recomendada, basada sólo en observaciones demostrables:

- `unavailable`: ningún aspecto requerido tiene una proposición probatoria
  válida;
- `partial`: existe al menos una proposición probatoria válida, pero no todos
  los aspectos requeridos poseen alguna;
- `probatory`: todos los aspectos requeridos poseen al menos una proposición
  probatoria válida, positiva o negativa.

`unavailable` añade `coverage_capability_unavailable` a `reason_codes` y fuerza
`complete=False`. `partial` no rebaja umbrales ni elimina los gates de fuentes,
producción, riesgo o conflictos.

Un objetivo sin aspectos requeridos se reporta `unavailable`, con las tres
métricas en cero y `complete=False`; no se interpreta como prueba vacuamente
completa. Una refutación válida demuestra que existe observación probatoria y
por tanto puede contribuir a `coverage_capability`, pero mantiene cobertura
evidencial en cero y continúa bloqueando completion. Un resultado `unknown` o
degradado queda visible en perfiles ejecutados, pero no crea por sí solo una
proposición ni eleva capacidad.

`verification_profiles` no afirmará qué plugins podrían haberse ejecutado. Sólo
publicará observación saneada:

```json
{
  "profile": "argos/verification-profile-report-v1",
  "enabled": [],
  "enabled_state": "unavailable",
  "executed": [
    {
      "family": "pep621",
      "versions": ["1"],
      "methods": ["static"],
      "aspects": ["requests"],
      "result_count": 1,
      "probative_result_count": 1
    }
  ]
}
```

La lista `enabled` queda vacía y su estado explícitamente `unavailable` hasta
que exista un manifest de capacidades con frontera confiable. `executed` se
deriva sólo de `VerificationResult` válidos, en scope y revisión; nunca de
objetos rechazados, `repr`, URLs o contenido del target.

La única fuente de `executed` será el ledger saneado de la frontera
`_admit_verification_results`. El reporte específico de dependencias puede
referenciar ese resumen, pero no volver a sumar los mismos resultados.

## 5. Diseño de implementación

### 5.1 Una sola instantánea de métricas

Introducir una estructura interna inmutable, por ejemplo `CoverageMetrics`, con
todos los valores globales, scores por aspecto, capacidad, perfiles y
diagnósticos. Una función pura `compute_coverage_metrics(...)` será la única
fuente para:

- el bucle de `analyze_system`;
- la simulación de delta usada por utilidad;
- `should_stop`;
- `synthesize_report`;
- casos y benchmark mediante el reporte público.

`compute_coverage` puede permanecer como wrapper interno compatible que devuelve
`metrics.evidential_coverage`; no debe conservar la fórmula legacy.

### 5.2 Reutilización de independencia

La agrupación debe consumir la vista preparada del protocolo D. La API
`independence_groups` actual sólo devuelve componentes de fuentes con
procedencia completa, mientras `independent_source_count` conserva un piso de
uno para evidencia in-scope con procedencia incompleta. F necesita exactamente
esa segunda semántica para compatibilidad legacy. Se añadirá una función
estrecha en `verifiers.py` que exponga componentes utilizables, el componente
conservador de procedencia incompleta y los mismos diagnósticos de
`prepare_sources`, sin duplicar union-find ni relajar validaciones.

No se permite:

- copiar `_linkage_keys` o el union-find a `algorithm.py`;
- contar `evidence_id` distintos como independencia;
- usar `verifier_version` para crear una fuente nueva de la misma familia;
- resolver conflictos de `source_id` por orden de llegada;
- llamar `independence_groups` y olvidar el piso conservador de evidencia
  legacy incompleta.

### 5.3 Complejidad y cache local

Objetivo: una instantánea completa debe ser $O(P\log P + L)$, donde $P$ es el
número de proposiciones y $L$ los enlaces de independencia. No se recalcula la
misma vista para `coverage`, `aspect_scores`, capacidad y reporte.

La simulación de utilidad debe invocar la misma función normativa. Si el costo
por candidato excede el baseline acordado, se permite un índice incremental
local al análisis, siempre que produzca resultados bit-idénticos a la función
pura y tenga tests diferenciales.

## 6. Tickets de implementación

### F-001 — Baseline, decisiones y consumidores

**Dependencias:** E fusionada.
**Archivos:** tests existentes, este subplan, sin código productivo.

Tareas:

1. ejecutar y guardar baseline local de los siete gates;
2. convertir el test `KNOWN-UNSOUND` en regresión roja con el resultado deseado;
3. inventariar todos los accesos a `coverage`, `aspect_scores`, `complete` y
   `thresholds_met`;
4. congelar muestras JSON de reportes vacío, parcial, contradictorio y completo;
5. confirmar en revisión la fórmula §4.2 y la duración del alias.

Criterio de aceptación:

- existe una lista verificable de consumidores;
- la reproducción falla por inflación, no por una fixture vacía;
- no se modificaron umbrales ni goldens.

### F-002 — Núcleo probatorio por claim y componente

**Dependencias:** F-001.
**Archivos previstos:** `algorithm.py`, `verifiers.py`, tests de métricas e
independencia.

Tareas:

1. implementar identidad de claim fail-closed;
2. obtener componentes desde la vista canónica de D;
3. representar procedencia legacy in-scope e incompleta como un único
   componente conservador por claim, nunca como cero ni como N fuentes;
4. calcular confianza por componente, score por claim y máximo por aspecto;
5. implementar `CoverageMetrics` y el wrapper compatible;
6. validar `corroboration` como finito y positivo sin coerción hostil;
7. garantizar determinismo y redondeo sólo en salida.

Pruebas obligatorias:

- duplicado exacto;
- mismo claim con distinto `evidence_id` y misma raíz;
- alias de contenido, ejecución compartida y derivación compartida;
- versiones distintas de una familia;
- `source_id` conflictivo;
- dos fuentes realmente independientes;
- una, dos y diez fuentes legacy con procedencia incompleta;
- dos claims diferentes del mismo aspecto;
- revisión ajena, claim vacío, confianza cero, `NaN`, bool y tipos hostiles;
- permutación e idempotencia;
- pesos de aspecto no uniformes.

Criterio de aceptación:

- todos los duplicados conservan el mismo resultado bit a bit;
- una segunda fuente independiente del mismo claim puede aumentar el score;
- claims distintos nunca se suman.

### F-003 — Recuperación y estructura no probatorias

**Dependencias:** F-002.
**Archivos previstos:** `algorithm.py`, tests de claims y smoke.

Tareas:

1. calcular presencia por aspecto para recuperación y estructura;
2. excluir entradas malformadas y fuerza no positiva;
3. añadir scores por aspecto y métricas ponderadas;
4. probar que no participan en ninguna decisión probatoria.

Pruebas obligatorias:

- sólo `mentions` produce retrieval mayor que cero y evidencia cero;
- `tests`/`implements`/`configures` producen structural y retrieval;
- soportes y refutaciones recuperados cuentan como retrieval observado;
- duplicación y reordenamiento no cambian las métricas;
- retrieval igual a 1 con evidencia igual a 0 nunca produce completion;
- aspectos fuera del objetivo no contaminan ninguna métrica.

### F-004 — Capacidad y perfiles observados

**Dependencias:** F-002.
**Archivos previstos:** `algorithm.py`, `dependency_verifiers.py`, tests de
admisión.

Tareas:

1. derivar capacidad desde proposiciones probatorias válidas por aspecto;
2. extender la admisión con un ledger saneado que sea la única fuente de
   perfiles ejecutados;
3. conservar perfiles válidos aunque el resultado sea `unknown` o degradado,
   sin convertirlo en proposición;
4. construir el reporte determinista de perfiles ejecutados;
5. sanear campos y no exponer contenido, URL, marker secreto ni objetos
   rechazados;
6. añadir el reason code bloqueante de capacidad indisponible.

Criterio de aceptación:

- `unavailable` siempre implica `complete=False`;
- ejecutar un verificador degradado queda visible sin aportar cobertura;
- perfiles inválidos o fuera de revisión no aparecen como ejecutados válidos;
- el reporte es estable bajo duplicación y permutación.

### F-005 — Integración con utilidad, parada y reporte

**Dependencias:** F-002, F-003 y F-004.
**Archivos previstos:** `algorithm.py`, tests de smoke, claims y verificadores.

Tareas:

1. sustituir las recomputaciones legacy por una instantánea compartida;
2. usar `evidential_coverage` en utilidad y `should_stop`;
3. añadir los campos públicos y aliases exactos;
4. mantener `complete`, `procedure_complete` y `thresholds_met` coherentes;
5. actualizar `next_actions` para distinguir falta de evidencia y capacidad;
6. conservar diagnóstico, costo y terminación cuando el presupuesto es cero.

Pruebas obligatorias:

- `coverage == evidential_coverage` para todos los caminos;
- `aspect_scores == evidential_aspect_scores`;
- `complete=True` implica capacidad `probatory`, umbrales, fuentes,
  producción, ausencia de negativos/conflictos y degradaciones permitidas;
- presupuesto agotado después de obtener prueba conserva
  `termination_reason=thresholds_met`;
- simulación de utilidad y delta observado usan la misma fórmula;
- agregar retrieval sin soporte no altera utilidad probatoria ni parada.

### F-006 — Compatibilidad y contratos

**Dependencias:** F-005.
**Archivos previstos:** `README.md`, `MODEL.md`, `ARCHITECTURE.md`,
`docs/api.md`, `docs/contracts.md`, `CHANGELOG.md` y tests contractuales.

Tareas:

1. documentar la fórmula, perfiles, capacidad y límites;
2. publicar una tabla de migración campo anterior/campo nuevo;
3. afirmar explícitamente que `coverage` sigue numérico;
4. ligar `coverage_profile` y sus parámetros a la configuración construida por
   `build_manifest`, mediante argumento aditivo y default explícito;
5. mantener intactos `evaluation-envelope-v1`, `claim-record-v1` y los demás
   schemas publicados: cambia contenido/fingerprint de nuevos manifests, no el
   significado del schema v1;
6. añadir tests de manifest que prueben que cambiar perfil cambia fingerprint y
   que los nombres y validadores de schemas siguen coexistiendo;
7. no anunciar deprecación sin calendario y consumidor migrado.

Matriz mínima de compatibilidad:

| Consumidor | Antes | Durante F |
|---|---|---|
| `report["coverage"]` | float probatorio legacy | float probatorio por claim |
| `report["aspect_scores"]` | por volumen | alias del score por claim |
| `report["complete"]` | bool | bool, gates iguales o más estrictos |
| bundle v1 | sin métricas nuevas | sin cambio semántico ni de schema |
| renderer | una cobertura | cobertura alias + métricas separadas |

### F-007 — Casos y benchmark

**Dependencias:** F-005 y F-006.
**Archivos previstos:** `examples/regenerate_case_studies.py`,
`examples/case-study-*.md`, `bench/run_benchmark.py`, `bench/report.md`.

Tareas:

1. mostrar métricas separadas en los renderers;
2. incluir `coverage_profile` en el manifest reproducible de cada caso;
3. añadir al benchmark una fixture adjudicada de inflación por duplicados;
4. comparar before/after sin tratar mayor coverage como mejor por sí mismo;
5. regenerar desde worktree limpio y con gates secuenciales;
6. no tocar los dos archivos `bench/real_*` preservados del usuario.

Criterio de aceptación:

- los casos son fresh desde el SHA candidato;
- el benchmark detecta si reaparece inflación;
- el plan, por usar prefijo `plan-mejoras-`, permanece excluido del autoestudio
  y no vuelve autorreferente el caso Argos.

### F-008 — Ronda adversarial y rendimiento

**Dependencias:** F-002 a F-007.
**Archivos previstos:** tests, sin nuevas features.

Ataques mínimos:

1. 10 000 duplicados del mismo claim y raíz;
2. cadenas y ciclos de derivación;
3. fuentes conflictivas mezcladas con fuentes legítimas;
4. familias/versiones diseñadas para aparentar independencia;
5. revisiones con espacios, bytes, bool, `None` y objetos hostiles;
6. confianza `NaN`, infinita, negativa y mayor que uno;
7. pesos extremos y orden aleatorio;
8. perfil con datos que parezcan secretos;
9. iterables de un solo uso y colecciones cíclicas;
10. ejecución repetida, serialización repetida y permutación completa.

Presupuesto de rendimiento:

- registrar tiempo y memoria con 1, 100, 1 000 y 10 000 proposiciones;
- 10 000 duplicados no deben crear 10 000 componentes;
- una instantánea no debe recalcular union-find por cada campo del reporte;
- cualquier optimización debe tener oracle diferencial contra la función pura.

### F-009 — Entrega, rollback y memoria

**Dependencias:** F-008.

Tareas:

1. revisar diff contra la allowlist de F;
2. ejecutar los siete gates sobre el SHA exacto en worktree limpio;
3. documentar checks remotos no ejecutados por billing como administrativos;
4. preparar commit y PR enfocados, sin merge automático;
5. registrar hito y checkpoint en AN-KLA sólo tras revisión;
6. conservar una ruta de rollback que revierta F sin depender de G.

## 7. Orden de ejecución y propiedad

```text
F-001
  └─ F-002
       ├─ F-003
       └─ F-004
            └─ F-005
                 ├─ F-006
                 └─ F-007
                      └─ F-008
                           └─ F-009
```

Un único agente es propietario de `algorithm.py`, `verifiers.py` y los
renderers durante cada ticket. Las tareas paralelas sólo pueden cubrir lectura,
oráculos o documentación en archivos distintos; nunca ediciones concurrentes
del núcleo de agregación.

## 8. Estrategia de pruebas

### 8.1 Oráculos manuales

Se mantendrá una tabla pequeña con resultados calculados a mano:

| Caso | Resultado evidencial esperado |
|---|---:|
| sin soporte | 0 |
| un claim, un grupo, confianza 0.6, κ=1.8 | 0.333333… |
| mismo grupo repetido tres veces | 0.333333… |
| mismo claim, dos grupos de 0.6 | 0.666666… |
| dos claims de 0.6 en un aspecto | 0.333333… |
| dos grupos de 0.9 | 1.0 |

### 8.2 Propiedades metamórficas

- duplicación, alias, reordenamiento y partición de entrada son invariantes;
- añadir una fuente independiente positiva del mismo claim no reduce cobertura;
- añadir `mentions` o relaciones estructurales no cambia cobertura evidencial;
- añadir `refutes` no aumenta cobertura y no reduce riesgo;
- retirar una raíz independiente no aumenta cobertura;
- cambiar revisión invalida únicamente los resultados ligados a esa revisión;
- todas las métricas son finitas y pertenecen a `[0, 1]`.

### 8.3 Gates locales

Ejecutar secuencialmente, no en paralelo con el autoestudio:

```bash
.venv/bin/python -m ruff check argos_epistemic bench tests scripts
.venv/bin/python -m mypy argos_epistemic
.venv/bin/python -m pytest
.venv/bin/python -c "import argos_epistemic; print(argos_epistemic.run())"
.venv/bin/python examples/regenerate_case_studies.py --target argos --check
.venv/bin/python bench/run_benchmark.py --check
.venv/bin/python -m an_kla --project-root . context status
.venv/bin/python -m an_kla --project-root . status
.venv/bin/python -m an_kla --project-root . verify
git diff --check
```

Los casos terceros remotos no se presentan como verdes si no se ejecutaron. El
check protegido de GitHub no se fabrica mientras siga bloqueado por billing.

## 9. Observabilidad de la migración

Cada reporte de prueba o caso generado debe permitir comparar:

- `coverage` legacy esperado antes de F frente a cobertura por claim;
- `evidential_coverage`, `retrieval_coverage` y `structural_coverage`;
- número de claims, grupos independientes y proposiciones;
- perfiles ejecutados y resultados probatorios;
- reason codes y condición exacta que impidió completion;
- costo antes/después y tiempo de agregación.

No se considera éxito que coverage aumente. Éxito significa que cualquier
aumento se explica por un nuevo grupo independiente sobre el mismo claim.

## 10. Decisiones que requieren confirmación en revisión

1. Aprobar la fórmula de máximo por claim y máximo de confianza por componente.
2. Mantener `strength` como admisión, sin ponderación, durante `0.2.x`.
3. Mantener el alias `coverage` al menos durante toda la serie `0.2.x`.
4. Incluir `structural_coverage` en F o diferir sólo ese campo sin bloquear el
   núcleo probatorio.
5. Confirmar que `verification_profiles.enabled_state=unavailable` es preferible
   a inferir capacidades globales no demostrables.
6. Decidir versión final y eventual schema nuevo únicamente en H.

Hasta resolver 1–3 no debe modificarse código productivo. Los tickets pueden
preparar tests y evidencia, pero no convertir decisiones abiertas en hechos.

## 11. Ronda adversarial del subplan

Ronda ejecutada el 2026-08-10 contra código, contratos y generadores de la base
`00900b2`.

| Severidad | Ataque o brecha | Corrección incorporada |
|---|---|---|
| bloqueante | usar `independence_groups` directamente elimina toda fuente legacy con procedencia incompleta, aunque D la cuenta conservadoramente como una | F-002 exige una vista canónica que conserve el piso de uno y reutilice `prepare_sources` |
| bloqueante | cambiar la fórmula sin `coverage_profile` permite que dos evaluaciones con distinta semántica compartan configuración aparente | se añade perfil versionado, parámetros auditables y enlace al manifest |
| P1 | sumar perfiles desde admisión y desde `dependency_verification` duplica ejecuciones | un único ledger saneado de admisión alimenta el reporte |
| P1 | capacidad sobre objetivo vacío o sobre puras refutaciones era ambigua | objetivo vacío falla cerrado; refutes demuestra observación pero no cobertura ni completion |
| P1 | un resultado degradado podía presentarse como capacidad probatoria o desaparecer | queda en perfiles ejecutados, sin proposición ni aumento de capacidad |
| P1 | añadir métricas sólo al renderer deja utilidad y parada con la fórmula vieja | `CoverageMetrics` se vuelve fuente única para utilidad, loop, parada y reporte |
| P2 | recomputar union-find para cada campo o candidato crea explosión de costo | instantánea única, presupuesto de rendimiento y oracle diferencial |
| P2 | el nuevo documento podía volver stale el autoestudio | el nombre usa el prefijo excluido `plan-mejoras-`; el gate de frescura lo verifica |
| P2 | reescribir schemas v1 para añadir métricas rompería consumidores | los schemas se conservan; el perfil viaja en configuración aditiva y reporte |
| P2 | combinar claims diferentes por aspecto recrea falsa corroboración | máximo entre claims, suma únicamente entre componentes del mismo claim |

Resultado de la ronda: no quedan bloqueos conocidos dentro del alcance del
subplan. Las decisiones humanas de §10 permanecen explícitas y bloquean código
productivo; no se resolvieron por inferencia.

## 12. Definition of Done de F

- fórmula y decisiones de compatibilidad aprobadas;
- test legacy sustituido por el invariante correcto;
- una sola implementación gobierna cobertura, utilidad, reporte y parada;
- duplicados y fuentes dependientes no inflan ninguna métrica;
- `coverage` y `evidential_coverage` son aliases exactos y numéricos;
- `coverage_profile` aparece en reporte y manifest, y cambiarlo cambia la
  identidad de configuración;
- retrieval y estructura nunca producen completion;
- capacidad indisponible falla cerrada con diagnóstico;
- schemas publicados permanecen compatibles;
- documentación y migración están completas;
- casos y benchmark son reproducibles desde checkout limpio;
- rendimiento adversarial dentro del presupuesto acordado;
- siete gates locales y AN-KLA verdes sobre el SHA exacto;
- PR enfocado, rollback explícito y cambios `bench/real_*` ausentes.
