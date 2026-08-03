# Reevaluación técnica de `an-kla-memory` con Argos

**Fecha:** 2026-08-03
**Destinatario:** equipo de desarrollo de `an-kla-memory`
**Repositorio evaluado:** `https://github.com/kristhianmanue1/an-kla-memory`
**Revisión evaluada:** `67f6ee486a4235e43ca16d8f701eb8722aaad68a` (`v0.1.0-beta.1`)
**Revisión del evaluador:** `argos@ddfd52f2696eb63136ddf27130b924960319ae6b`
**Resultado general:** implementación sólida en integridad local y escritura gobernada; persisten límites de recuperación, explicabilidad, distribución y reproducibilidad documental.

## 1. Resumen ejecutivo

Esta reevaluación no cubre código nuevo de `an-kla-memory`: al momento de la
consulta, `HEAD`, `main` y la etiqueta `v0.1.0-beta.1` resolvían al mismo commit
evaluado anteriormente, `67f6ee4`. El valor de repetir el ejercicio es comparar
el comportamiento del Argos actual, corregir diagnósticos anteriores y ejecutar
comprobaciones directas que no dependan del modelo epistemológico.

La suite upstream pasó **124/124 pruebas** en Python 3.12.12. No se encontró
evidencia de corrupción, lectura obsoleta, fallo de CAS, pérdida de atomicidad o
mutación por las herramientas MCP de lectura. El diseño fail-closed y el enlace
criptográfico entre propuesta, autoridad, decisión, plan y revisión están bien
representados tanto en código como en pruebas.

Se confirman cuatro áreas de mejora:

1. **P1 — distribución incompleta del contrato de escritura:** el wheel no
   contiene `docs/` ni los JSON Schema normativos.
2. **P1 — alcance de recuperación poco explícito:** se almacenan tres streams,
   pero `retrieve` y `assemble-context` sólo buscan `facts`.
3. **P2 — explicabilidad de selección bajo presupuesto:** la salida sólo agrega
   conteos por motivo; no identifica qué candidato relevante fue excluido ni su
   costo.
4. **P2 — ergonomía del flujo gobernado:** faltan ejemplos completos de
   `authority.json`, una ayuda para calcular el hash canónico y un validador o
   constructor de entradas.

La reevaluación también encontró defectos metodológicos en Argos que **no deben
atribuirse a AN-KLA**: el resultado semántico cambia radicalmente según el linker,
la corrida densa produce cinco “conflictos” que son incompatibilidades de
proposiciones sintéticas y no contradicciones verificadas del producto, y el
generador aún llama “independiente” a una evaluación donde AN-KLA es dependencia
operativa del evaluador.

## 2. Alcance y frontera de independencia

Se evaluaron estos aspectos:

- almacenamiento revisionado e integridad local;
- recuperación y ensamblado bajo presupuesto;
- índice FTS5 y fallback;
- canonicalización;
- escritura gobernada;
- pruebas y empaquetado;
- reproducibilidad del reporte de Argos.

Esta no es una auditoría de seguridad completa ni una prueba formal. Tampoco es
una evaluación totalmente independiente:

- Argos declara `an-kla-memory@67f6ee4` como dependencia de desarrollo;
- la memoria local usada por el proyecto Argos funciona con esa versión;
- el análisis estructural lo ejecuta Argos sobre AN-KLA;
- los antecedentes recuperados desde AN-KLA se trataron como datos no confiables
  y se contrastaron contra Git, código, documentación y ejecución directa.

Para reducir circularidad, la evidencia se separó en dos carriles:

- **Carril Argos:** extracción L0–L5 estática y síntesis semántica;
- **Carril directo:** checkout limpio, `unittest`, experimentos aislados, lectura
  de código/ADR y construcción e inspección del wheel.

Sólo el segundo carril se usa para afirmar propiedades concretas del producto.

## 3. Entorno y reproducibilidad

| Variable | Valor |
|---|---|
| Objetivo | `an-kla-memory@67f6ee4` |
| Evaluador | `argos@ddfd52f` |
| Python | 3.12.12 |
| `sentence-transformers` | 5.6.1 |
| PyTorch | 2.13.0 |
| Transformers | 5.14.1 |
| Modelo denso | `sentence-transformers/all-MiniLM-L6-v2` |
| Objetivo Argos | `auditoria-memoria` |
| Aspectos | `memory`, `write`, `retrieval`, `canonical`, `test` |
| Umbral léxico | 0.10 |
| Umbral denso | 0.60 |
| Presupuesto Argos | 200000 tokens estimados / 2000 herramientas |

El checkout objetivo estaba limpio antes de las pruebas. La construcción local
del wheel dejó únicamente artefactos no rastreados dentro de la copia temporal;
no se modificó el repositorio fuente evaluado.

## 4. Resultados de Argos

### 4.1 Extracción estructural

La estructura coincide exactamente con la evaluación anterior:

| Métrica | Resultado |
|---|---:|
| Artefactos | 56 |
| L0/L1/L2/L3/L4/L5 | 5 / 1 / 3 / 1 / 32 / 14 |
| Docs / código / tests | 23 / 13 / 14 |
| Nodos del grafo | 260 |
| Aristas | 499 |
| Funciones de producción | 113 |
| Funciones con `raise` | 51 |
| Funciones con `assert` | 2 |
| Funciones que mutan `self` | 8 |
| Funciones clasificadas como validación | 13 |

Los nodos de mayor impacto sintáctico fueron:

1. `an_kla.__main__.main`: 0.839;
2. `MemoryStore.commit_write_plan`: 0.375;
3. `an_kla.mcp.main`: 0.268;
4. `an_kla.mcp.handle`: 0.259;
5. `build_index`: 0.250.

Estas cifras miden alcanzabilidad resuelta por AST y nombre corto. No demuestran
frecuencia de ejecución, criticidad de negocio, atomicidad ni seguridad.

### 4.2 Sensibilidad al backend semántico

| Resultado | Linker léxico | Linker denso |
|---|---:|---:|
| Evidencias | 56 | 56 |
| Proposiciones | 0 | 66 |
| Cobertura | 0.0000 | 0.8667 |
| Riesgo residual | 1.0000 | 0.0000 |
| Conflictos | 0 | 5 |
| `complete` | `false` | `false` |

Puntuaciones densas por aspecto:

```text
memory    1.0000
write     0.8333
retrieval 1.0000
canonical 0.5000
test      1.0000
```

La evaluación publicada anteriormente indicaba cobertura `0.8`, riesgo `0.0`,
cero conflictos implícitos y `complete=true`. El objetivo no cambió; el cambio
proviene del evaluador. Desde aquella corrida, Argos añadió un requisito de
evidencia de producción y otras correcciones. El resultado actual es más
prudente, pero continúa siendo muy sensible al linker.

Conclusión metodológica: las puntuaciones de Argos sirven para seleccionar zonas
de inspección, no para certificar AN-KLA. Un reporte reproducible debe conservar
backend, modelo, versión, umbral, configuración y huellas. La corrida léxica y la
densa deben publicarse como perfiles distintos, nunca reemplazarse entre sí de
forma implícita.

### 4.3 Los cinco conflictos de Argos

Argos declaró un conflicto por cada aspecto. Ejemplos:

- `memory`: `an_kla/__init__.py` frente a `benchmarks/README.md`;
- `retrieval`: `benchmarks/README.md` frente a un fixture de `AGENTS.md`;
- `canonical`: `an_kla/canonical.py` frente al resumen L4;
- `write`: notas de release frente a la guía del CLI;
- `test`: un test concreto frente al README de benchmarks.

No se observaron afirmaciones textuales incompatibles en esos pares. Los
“conflictos” nacen de cómo Argos transforma similitud semántica, fuerza,
polaridad débil y procedencia en proposiciones. Por ello se clasifican como
**falsos positivos o conflictos sintéticos no adjudicados**, no como defectos de
AN-KLA. Sí explican correctamente por qué el Argos actual se niega a marcar la
evaluación como completa.

## 5. Verificación directa

### 5.1 Suite upstream

Comando:

```bash
python -m unittest discover -s tests -v
```

Resultado:

```text
Ran 124 tests in 3.206s
OK
```

La suite cubre, entre otros:

- estabilidad de snapshots y revisiones inmutables;
- escritores concurrentes y CAS;
- recuperación después de fallos antes y después de `CURRENT`;
- índices ausentes, alterados, incompletos o no referenciados;
- presupuesto UTF-8 exacto;
- canonicalización y rechazo de NaN;
- mutación de propuesta, decisión o plan;
- autoridad separada y límites del CLI;
- integración administrada de `AGENTS.md`/`AN-KLA.md`;
- MCP de sólo lectura.

La amplitud es buena para una beta local. La evidencia sigue siendo la ejecución
en una sola plataforma y proceso host; no valida coordinación multi-máquina,
durabilidad ante pérdida física ni identidad criptográfica, que además están
declaradas fuera de alcance.

### 5.2 Recuperación y presupuesto global

Se creó una memoria temporal con:

- un fact largo de mayor puntuación;
- un fact corto de menor puntuación;
- un episodio largo con términos equivalentes.

Consulta: `memoria presupuesto`. Presupuesto de ensamblado: 1500 bytes.

Resultado:

```json
{
  "ranked_ids": ["f-long", "f-short"],
  "assembled_ids": ["f-short"],
  "assembly_excluded": {"budget": 1},
  "episode_retrieved": false
}
```

Interpretación:

- el ranking léxico encuentra correctamente el fact largo y lo coloca primero;
- el ensamblador lo retira porque no cabe en la envolvente completa;
- después incorpora el fact corto;
- el episodio no entra al conjunto candidato porque recuperación itera sólo
  sobre `snapshot.records["facts"]`;
- no existe penalización BM25 por longitud.

Esto confirma el análisis corregido del equipo AN-KLA: es selección greedy bajo
presupuesto global, no un bug de ranking.

### 5.3 Índice FTS5

Antes de construir un índice para la revisión nueva:

```json
{"profile": "scan-fallback/v1", "degradation": "index_unavailable"}
```

Después de `build_index`:

```json
{"profile": "sqlite-fts5/v1", "degradation": "none"}
```

Los IDs seleccionados antes y después fueron idénticos. La implementación no
reutiliza silenciosamente el índice de una revisión anterior. El rebuild
restaura aceleración y elimina la degradación; no corrige una lectura stale.

No se recomienda introducir la actualización de FTS dentro del commit
autoritativo: alargaría el lock y acoplaría una caché derivada a la escritura.
La arquitectura actual prioriza correctamente la integridad.

### 5.4 Canonicalización

Para `{"á":"🧠","z":1}` se obtuvo:

```text
bytes UTF-8: 19
sha256:ba8d937908baa4097b02dff153f218ed938756c1b0a51e4c33968bbd7ca0e654
```

La suite también prueba orden de claves, límites decimales del tamaño embebido,
NaN y huellas no autorreferenciales. No se encontró una discrepancia en este
aspecto. La puntuación `canonical=0.5` de Argos expresa cobertura semántica
insuficiente, no un fallo observado de canonicalización.

### 5.5 Wheel y recursos normativos

Se construyó el wheel con:

```bash
python -m pip wheel . --no-deps --no-build-isolation
```

Artefacto:

```text
an_kla_memory-0.1.0b1-py3-none-any.whl
sha256:03a736a05540158a2e971361aa41aeb6ec6d225be112612d2e83f4e9d6a498e3
```

El archivo contiene los 12 módulos de `an_kla`, metadatos y licencia. No contiene:

- `docs/write-policy-cli.md`;
- ADR de arquitectura;
- `docs/schemas/write-proposal-v1.schema.json`;
- `write-authority`, `write-decision`, `write-plan` ni `cost-certificate` schemas.

La configuración `packages = ["an_kla"]` explica el resultado. Un consumidor
instalado desde Git obtiene el código, pero no puede descubrir los contratos
normativos desde el entorno instalado. Este hallazgo queda confirmado.

## 6. Hallazgos priorizados para AN-KLA

### ANKLA-R2-01 — Los schemas normativos no se distribuyen

**Prioridad:** P1
**Tipo:** empaquetado / contrato público
**Estado:** confirmado directamente

La documentación presenta los JSON Schema como normativos, pero el wheel no los
incluye. Esto crea una diferencia entre trabajar desde un checkout y consumir
la beta instalada.

Recomendación:

- mover o copiar los schemas a un paquete de recursos, por ejemplo
  `an_kla/schemas/`;
- declararlos como package data;
- ofrecer `an_kla schema list` y `an_kla schema show <nombre>`;
- añadir una prueba que construya e inspeccione el wheel, no sólo el árbol fuente;
- conservar los documentos largos fuera del runtime si se desea, pero distribuir
  al menos los contratos normativos y sus identificadores.

Criterio de aceptación: una instalación aislada puede enumerar y leer exactamente
los cinco schemas versionados sin acceso al checkout ni a la red.

### ANKLA-R2-02 — Recuperación sólo sobre `facts` insuficientemente visible

**Prioridad:** P1
**Tipo:** contrato / experiencia de integración
**Estado:** confirmado por código y experimento

La API almacena `facts`, `events` y `episodes`, pero recuperación e índice recorren
exclusivamente `facts`. El README habla de conservar los tres streams y recuperar
contexto, sin destacar esa restricción en el flujo de uso diario.

Recomendación inmediata:

- declarar en README, CLI help, MCP y ADR que `retrieval-result/v1` busca sólo
  `facts`;
- incluir `streams_searched: ["facts"]` en la salida o en el perfil;
- añadir una prueba contractual que garantice que esa declaración no diverja.

Recomendación de diseño posterior:

- no mezclar streams silenciosamente bajo el mismo perfil;
- si se amplía recuperación, versionar el perfil y definir scoring, precedencia,
  presupuesto y procedencia por stream;
- considerar una proyección recuperable corta para episodios o contenido largo.

### ANKLA-R2-03 — Exclusión por presupuesto no es explicable por candidato

**Prioridad:** P2
**Tipo:** observabilidad
**Estado:** confirmado directamente

`excluded_summary: {"budget": 1}` explica el total, pero no revela que el fact de
mayor puntuación fue el excluido. Para depurar recall, el integrador necesita
distinguir “no encontrado”, “fuera de stream”, “sin texto” y “encontrado pero no
cabe”.

Recomendación:

- mantener la salida compacta por defecto;
- añadir diagnóstico opt-in con `id`, `score`, bytes incrementales y motivo;
- no copiar contenido excluido en el diagnóstico;
- contabilizar por separado costo del registro y crecimiento de framing;
- fijar límites de cantidad/tamaño para que la explicación también respete un
  presupuesto.

### ANKLA-R2-04 — Fricción innecesaria al construir entradas gobernadas

**Prioridad:** P2
**Tipo:** usabilidad / prevención de errores
**Estado:** confirmado por interfaz y documentación

La arquitectura y los schemas existen, pero el CLI obliga al consumidor a
construir objetos complejos y calcular `proposal_sha256` fuera del producto. La
guía muestra una propuesta, pero no un `authority.json` completo ejecutable.

Recomendación:

- añadir ejemplos completos para `model_derived` y
  `derived_from_retrieval`;
- ofrecer `validate-write-input` o comandos `build-proposal` y
  `build-authority`;
- exponer un helper CLI de hash canónico;
- mostrar clases, emisores compatibles y operaciones admitidas en `--help`;
- preservar la prohibición de fabricar `tool_observed` y
  `channel_confirmed` desde archivos controlados por el candidato.

### ANKLA-R2-05 — Diagnóstico del índice es correcto; falta consolidarlo en UX

**Prioridad:** P3
**Tipo:** documentación
**Estado:** comportamiento correcto

No es un defecto de integridad. Conviene presentar consistentemente que:

- `scan-fallback/v1` es correcto y predeterminado;
- `index_unavailable` es degradación de aceleración;
- el índice está ligado a una revisión;
- `rebuild-index` no “pone al día” datos autoritativos.

## 7. Hallazgos sobre Argos que afectan la interpretación

Estos puntos corresponden al evaluador, no al producto evaluado:

1. El generador usa el backend denso cuando está instalado y el léxico cuando no,
   pero el Markdown no registra cuál se usó.
2. Tampoco registra versiones, modelo, umbral, configuración ni fingerprints.
3. La frase “validación independiente” contradice la nota que reconoce que
   AN-KLA es dependencia operativa.
4. Los conflictos actuales pueden aparecer entre evidencia débil y soportada sin
   una contradicción textual real.
5. `residual_risk=0` puede coexistir con conflictos abiertos y
   `complete=false`; no debe leerse aisladamente.
6. La corrida léxica produce cobertura cero, mientras la densa produce 0.8667:
   el score no es portable entre entornos.

Antes de usar el caso como evidencia pública, Argos debería emitir un manifiesto
de ejecución y separar métricas de selección de conclusiones verificadas.

## 8. Comparación con la evaluación anterior

| Afirmación anterior | Reevaluación |
|---|---|
| BM25 penalizaba registros largos | Refutada: AN-KLA no usa BM25 para ranking |
| Fact largo no era recuperado | Matizada: se encuentra y rankea primero; no cabe en la envolvente |
| Episodios no aparecen | Confirmada: recuperación v1 sólo busca facts |
| Índice queda desactualizado | Confirmada como caché ligada a revisión |
| Lectura queda stale | Refutada: fallback a scan ve la revisión nueva |
| Faltan JSON Schema | Refutada en fuente; confirmada su ausencia en el wheel |
| Escritura gobernada es difícil de integrar | Confirmada como fricción de UX |
| Posible fallo CAS/atomicidad | No sustentado; suite y revisión contradicen la sospecha |
| Argos: cobertura 0.8 y completo | No reproducido por el Argos actual |

## 9. Orden recomendado de implementación

### Iteración 1

- empaquetar schemas como recursos;
- prueba sobre wheel construido;
- documentar `streams_searched=[facts]` en todas las fronteras;
- ejemplo completo y verificable de propuesta + autoridad + plan.

### Iteración 2

- diagnóstico opt-in por candidato excluido;
- helper/validador CLI de entradas y hash canónico;
- métricas específicas de exclusión por envolvente.

### Iteración 3

- diseñar `retrieval_summary` o una proyección recuperable;
- decidir si habrá un perfil versionado multi-stream;
- ampliar el benchmark con documentos largos, Unicode y mezcla de streams.

No se recomienda mover FTS al camino de commit ni ampliar recuperación a episodios
sin versionar el contrato.

## 10. Criterios de cierre sugeridos

La siguiente beta podría considerar cerrados estos hallazgos cuando:

- una instalación desde wheel exponga los cinco schemas normativos;
- la documentación y las respuestas de API declaren el stream buscado;
- exista una reproducción pública del caso largo/corto con diagnóstico claro;
- un usuario pueda construir y validar una propuesta derivada sin implementar
  por su cuenta la canonicalización;
- la suite mantenga equivalencia scan/FTS y pruebas concurrentes actuales;
- los reportes de Argos incluyan un manifiesto reproducible y dejen de declarar
  independencia plena en este caso.

## 11. Veredicto

`an-kla-memory@67f6ee4` presenta una base técnica consistente para una beta local:
revisiones inmutables, CAS, journal, fallback de recuperación, presupuesto UTF-8,
canonicalización y escritura gobernada están respaldados por código y una suite
adversarial amplia. No se encontró un defecto crítico de integridad.

El riesgo principal está en la distancia entre el contrato sofisticado y la
experiencia del consumidor: parte de la normativa no viaja en el paquete, la
recuperación de un solo stream no es suficientemente visible y la exclusión de
evidencia relevante bajo presupuesto resulta difícil de explicar. Son problemas
importantes para adopción y uso correcto, aunque no invalidan el núcleo de
almacenamiento.

La calificación de Argos debe conservarse como señal heurística. La conclusión
técnica de este documento descansa en la combinación de código, ADR, artefacto
distribuible y ejecución directa, no en `coverage`, `residual_risk` o
`complete` por sí solos.
