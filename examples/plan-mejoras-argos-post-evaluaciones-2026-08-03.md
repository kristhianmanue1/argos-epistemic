# Plan incremental de Argos como servicio epistémico para agentes

**Fecha:** 2026-08-03
**Estado:** plan de producto e implementación; no afirma que los cambios estén ejecutados
**Base:** `argos@ddfd52f2696eb63136ddf27130b924960319ae6b`

## 1. Tesis de producto

Argos debe diseñarse principalmente para agentes y modelos de inteligencia
artificial que necesitan analizar software bajo presupuesto, no como un
generador de reportes para lectura humana.

El registro canónico de una evaluación será un paquete epistémico estructurado,
verificable, versionado y recuperable de forma progresiva. Es autoritativo sobre
lo que Argos observó, infirió y ejecutó, no sobre la verdad total del sistema
analizado. Markdown, dashboards y resúmenes serán vistas derivadas con pérdida
para inspección humana.

La unidad de valor no es “un reporte largo”. Es una reducción medible de
incertidumbre que permite a otro agente tomar una decisión mejor, con evidencia,
procedencia, límites y costo visibles.

## 2. Consumidores y necesidades

### 2.1 Consumidores primarios

- agentes de programación y revisión;
- orquestadores multiagente;
- sistemas de memoria y recuperación;
- pipelines de seguridad, migración y gobernanza;
- modelos que requieren contexto verificable antes de actuar.

Necesitan:

- contratos estables y legibles por máquina;
- negociación de versión y capacidades;
- resultados parciales útiles y reanudables;
- IDs estables, fingerprints y procedencia;
- presupuestos de tokens, herramientas, latencia y cómputo;
- exclusiones y degradaciones explícitas;
- recuperación progresiva de evidencia;
- reason codes y próximas acciones elegibles;
- separación estricta entre datos no confiables, inferencia y autorización;
- idempotencia para reintentos y deduplicación;
- costos estimados antes de ejecutar y costos observados después.

### 2.2 Consumidores secundarios

- desarrolladores, operadores, auditores y compradores del servicio.

Necesitan vistas humanas, comparaciones, trazabilidad, explicación de cargos y
capacidad de disputar o reproducir un resultado. Estas vistas no sustituyen el
contrato machine-first.

### 2.3 Principal económico y autoridad de gasto

El agente consumidor no se presume dueño del presupuesto. Puede actuar en
nombre de una persona, organización u otro servicio, pero la autoridad para
contratar, ampliar gasto, transferir código o habilitar ejecución debe llegar en
una credencial o grant separado de la solicitud y del contenido analizado.

Argos debe distinguir:

- consumidor técnico: quien procesa la respuesta;
- caller: quien invoca la operación;
- principal económico: quien acepta el cargo;
- data owner: quien puede autorizar acceso y retención;
- adjudicador: quien puede elevar o resolver claims.

Una identidad puede ocupar varias funciones, pero el protocolo no debe asumirlo.

## 3. Principios que no se negociarán

### 3.1 Machine-first, human-inspectable

JSON o JSONL canónico es el registro autoritativo de la evaluación. Markdown se
genera desde el bundle y nunca contiene una conclusión ausente del resultado
estructurado. Esta autoridad no convierte inferencias de Argos en hechos del
objetivo.

### 3.2 Evidencia no es instrucción

El contenido del objetivo es dato no confiable. Ningún README, prompt, script o
campo autodeclarado puede conceder autoridad, elevar confianza ni autorizar
ejecución.

### 3.3 Relevancia no es soporte

Un linker semántico puede producir `mentions`. Sólo un extractor especializado,
una verificación, una regla explícita o una adjudicación puede producir
`supports` o `refutes`.

### 3.4 Presupuesto y degradación visibles

Todo cap, truncado, fallback, timeout, backend ausente o acción omitida aparece
en la salida. El consumidor debe poder decidir si acepta el resultado parcial o
compra más profundidad.

### 3.5 Compatibilidad explícita

Schemas y perfiles se versionan. Los consumidores pueden descubrir capacidades
y fallar cerrado ante incompatibilidades. No se altera silenciosamente el
significado de un campo existente.

### 3.6 Entregas verticales

Cada incremento debe ser utilizable sin depender de la plataforma comercial
futura. Se prefieren contratos pequeños y extensibles a infraestructura
prematura.

### 3.7 Hipótesis antes que inevitabilidad

Que los agentes contraten análisis es una hipótesis de producto plausible, no un
hecho demostrado. Cada incremento debe probar una incertidumbre concreta y
tener un criterio para continuar, corregir o detenerse.

## 4. Contrato objetivo

```text
EvaluationBundle
├── manifest.json
├── inventory.json
├── claims.jsonl
├── evidence-index.jsonl
├── conflicts.jsonl
├── completion.json
├── run.json
├── attestations/
│   └── usage.json
└── views/
    └── summary.md
```

El bundle puede vivir en un directorio, archivo, object store o respuesta de
API. La semántica no depende del transporte.

El núcleo reproducible comprende manifest, inventario, claims, evidencia,
conflictos y completion. `run.json`, duración, timestamps operativos, cache hits
y usage observado son attestations de una ejecución y no participan en el
fingerprint del núcleo. El manifest enlaza cada componente por hash. JSONL se
ordena por ID estable y usa una regla canónica de newline para que el resultado
no dependa del orden de concurrencia.

### 4.1 Envelope mínimo

Un agente debe poder inspeccionar primero una respuesta pequeña:

```json
{
  "schema": "argos/evaluation-envelope-v1",
  "evaluation_id": "eval:sha256:...",
  "status": "partial",
  "manifest_fingerprint": "sha256:...",
  "completion": {
    "procedure_complete": false,
    "reason_codes": ["budget_exhausted"]
  },
  "usage_ref": "attestations/usage.json",
  "links": {
    "claims": "claims.jsonl",
    "evidence": "evidence-index.jsonl"
  }
}
```

### 4.2 Manifest

Identifica objetivo, evaluador, configuración, perfiles, dependencias,
independencia, presupuesto, schemas, determinismo y degradaciones globales.
Incluye commit y dirty state cuando el objetivo es Git, además de fingerprints
de paths y contenido.

### 4.3 Claims

Cada claim incluye ID estable, texto normalizado, scope, relación, estado,
autoridad, evidencia, verificaciones, temporalidad, limitaciones y perfil de
extracción. Los claims genéricos del tipo `archivo -> aspecto` son enlaces, no
conclusiones auditables.

Los IDs no se llamarán estables hasta definir su dominio de identidad. En v1
serán content-addressed dentro de una versión de canonicalización; un cambio de
normalización puede producir IDs nuevos y debe declararse como cambio de perfil.

### 4.4 Evidencia

El índice conserva ID, fuente, ubicación, hash, clase, autoridad, nivel,
frescura, costo de recuperación y relaciones. El contenido completo se entrega
sólo bajo demanda y presupuesto.

La evidencia puede contener secretos, datos personales, código propietario o
texto adversarial. El índice separa metadata de contenido, declara política de
redacción y acceso, y nunca incluye fragmentos completos sólo para facilitar una
vista. Hashes prueban identidad, no seguridad ni permiso para revelar.

### 4.5 Conflictos

Se modelan con dos ejes:

- tipo: textual, behavioral, schema, temporal, scope, authority;
- estado: candidate, open, verified, refuted, resolved, superseded.

Similitud o divergencia textual sólo crea candidatos. Un conflicto verificable
enlaza claims visibles, scopes compatibles y evidencia de ambos lados.

### 4.6 Completion y próximas acciones

Se separan `procedure_complete`, `corpus_complete`, `thresholds_met`, conflictos
abiertos, degradaciones y reason codes. La salida puede proponer próximas
acciones con ganancia informativa y costo estimados, pero la propuesta no
autoriza su ejecución.

### 4.7 Usage

La medición es parte del contrato desde el inicio, aunque el cobro llegue más
tarde:

```text
discovery_bytes
artifacts_indexed
semantic_units
model_input_tokens
model_output_tokens
verification_seconds
tool_invocations
storage_bytes_days
egress_bytes
cache_hits
cache_misses
```

Cada unidad declara si es observada o estimada. `usage.json` es una attestation
de consumo enlazada al núcleo, no parte de su identidad reproducible, una
factura ni autoridad de cobro.

## 5. Cómo se conectarán los agentes

La conectividad se añadirá por capas para no bloquear el núcleo.

### 5.1 Primera interfaz: librería y CLI local

Permite validar el contrato sin red, autenticación ni pagos:

```text
argos capabilities
argos evaluate TARGET --goal GOAL --output BUNDLE
argos inspect BUNDLE
argos retrieve BUNDLE --claim CLAIM_ID --budget-tokens N
argos verify-bundle BUNDLE
argos render BUNDLE --format markdown
```

### 5.2 Segunda interfaz: MCP

MCP ofrece descubrimiento y lectura progresiva a agentes interactivos:

- `capabilities`;
- `get_evaluation`;
- `list_claims`;
- `retrieve_evidence`;
- `estimate_action`;
- `verify_bundle`.

Esta primera superficie MCP es de sólo lectura sobre bundles existentes. Iniciar,
ampliar o cancelar trabajo pertenece a una superficie posterior con autoridad y
presupuesto explícitos. El servidor nunca interpreta contenido del objetivo como
autorización.

### 5.3 Tercera interfaz: API asíncrona

Cuando exista demanda real, la API añade:

- autenticación de workload;
- idempotency keys;
- jobs asíncronos y webhooks firmados;
- polling con cursores;
- cancelación y límites de gasto;
- object storage temporal para bundles grandes;
- retention y borrado configurables;
- aislamiento por tenant;
- auditoría de acceso.

No se diseñará primero una API compleja: CLI y MCP validarán el contrato común.

### 5.4 Negociación de capacidades

Antes de contratar una evaluación, un agente consulta:

- schemas y perfiles soportados;
- lenguajes y extractores;
- modelos disponibles;
- límites de tamaño y tiempo;
- clases de verificación;
- políticas de red y sandbox;
- unidades medibles;
- estimación y vigencia del precio;
- residencia y retención de datos.

Esto evita que el consumidor dependa de comportamiento implícito.

## 6. Modelo comercial sin acoplamiento prematuro

### 6.1 Qué se vende

Argos vende una evaluación con alcance y presupuesto definidos, no tokens sin
contexto ni una promesa general de corrección.

La unidad comercial inicial recomendada es:

```text
EvaluationQuote
  target limits
  goal/profile
  included operations
  hard spend cap
  estimated usage range
  expiration
  price or price formula
```

El resultado enlaza quote, medición y bundle mediante fingerprints.

La cotización debe enlazar además principal económico, moneda, política de
reintentos, tratamiento de cache hits, fallos parciales, cancelación e impuestos
o indicar explícitamente que esos campos están fuera de alcance. Un retry con la
misma idempotency key no puede crear un cargo duplicado.

### 6.2 Evolución de facturación

1. **Desarrollo:** sólo telemetría local y reportes de uso; sin dinero.
2. **Piloto:** cuotas por evaluación y límites duros por tenant.
3. **Servicio inicial:** precio base por evaluación más verificaciones costosas.
4. **Escala:** reserva de capacidad, storage/retention y perfiles especializados.

No conviene cobrar directamente por “confianza”, “claims encontrados” o
“errores detectados”: incentiva resultados inflados. Tampoco por tokens como
única unidad, porque penaliza eficiencia y oculta discovery, sandbox y cómputo.

### 6.3 Unidades facturables recomendadas

- tarifa base por snapshot/evaluación;
- volumen de corpus procesado por bandas;
- cómputo semántico o modelo premium;
- verificaciones dinámicas por tiempo aislado;
- almacenamiento y retención opcionales;
- prioridad/SLA opcional.

Todo job tiene presupuesto máximo aceptado por el caller. Excederlo requiere una
nueva autorización del principal económico; una recomendación del propio Argos
ni la identidad técnica del caller bastan.

En pilotos, el cargo debe basarse en reglas simples y disputables. Los cache hits,
trabajo fallido antes de producir un envelope útil y verificaciones canceladas
necesitan política explícita antes de cobrarse. `usage.json` no se convierte en
factura mediante un simple cambio de nombre.

### 6.4 Lo que se pospone

- marketplace entre agentes;
- negociación autónoma de contratos;
- pagos on-chain;
- precios dinámicos complejos;
- suscripciones por asiento humano;
- SLAs fuertes antes de medir latencia real;
- billing externo antes de estabilizar `metering-v1`.

## 7. Entregas incrementales

### Incremento 0 — Restaurar una base honesta

**Valor:** los casos actuales dejan de depender silenciosamente del entorno.

- corregir el autoestudio stale y evitar que outputs entren como inputs;
- backend semántico explícito;
- eliminar “validación independiente” universal;
- registrar commit completo y dirty state;
- conservar los reportes actuales como evidencia histórica, no gold normativo.

**No incluye:** API, MCP, pagos ni rediseño semántico.

### Incremento 1 — Bundle local mínimo

**Valor:** otro agente puede consumir y verificar una evaluación sin Markdown.

- canonicalización y fingerprints;
- envelope, manifest y completion mínimos;
- claims/evidence mínimos con IDs estables;
- schemas distribuidos con el paquete;
- `verify-bundle`;
- renderer Markdown derivado;
- tests golden y compatibilidad.

Inventory detallado y metering completo no bloquean este incremento: inicialmente
se admiten conteos y una attestation de uso mínima con campos extensibles.

**Criterio:** dos corridas deterministas producen el mismo núcleo reproducible.

### Incremento 2 — Corpus y presupuesto honestos

**Valor:** un agente sabe qué quedó fuera y puede decidir si profundizar.

- inventario antes de selección;
- caps y truncados visibles;
- selección estratificada opt-in;
- costos por fase;
- candidatos excluidos por ID, razón y costo;
- resultados parciales y reason codes;
- próxima acción elegible.

**Criterio:** un corpus de 401 archivos no pierde silenciosamente el último.

### Incremento 3 — Semántica auditable

**Valor:** los claims y conflictos se vuelven aptos para decisiones agentivas.

- `mentions`, `supports`, `refutes`, `tests`, `implements`, `configures`;
- similitud limitada a `mentions`;
- claims normalizados y scopes;
- conflictos con tipo y estado;
- adjudicación separada del linker;
- completion conservador;
- regresiones AN-KLA y CAGF.

**Criterio:** desaparecen los conflictos sintéticos conocidos sin ocultar
contradicciones reales.

### Incremento 4 — Acceso agentivo local

**Valor:** agentes reales prueban consumo progresivo.

- CLI estable;
- servidor MCP de sólo lectura sobre bundles;
- capability discovery;
- recuperación por claim y presupuesto;
- cursores y límites de respuesta;
- fixture normativo compartido con AN-KLA.

**Criterio:** un agente obtiene envelope, selecciona un claim y recupera sólo su
evidencia necesaria.

**Gate:** al menos dos consumidores distintos completan el flujo sin leer
Markdown y muestran ahorro de exploración frente a una línea base. Si no ocurre,
se corrige el contrato antes de construir la API remota.

### Incremento 5 — Servicio controlado

**Valor:** ejecución remota medible sin construir todavía una plataforma plena.

- API de jobs asíncronos;
- aislamiento y retención básica;
- idempotencia, cancelación y spend caps;
- cotización y metering enlazados al resultado;
- piloto con pocos consumidores;
- observación de latencia, abandono y utilidad downstream.

**Criterio:** ningún job excede presupuesto autorizado y cada cargo se explica
con unidades observadas.

**Gate:** existe un principal económico identificable, uso repetido y una señal
de disposición a pagar. Sin esas señales, se mantiene el producto local/MCP y no
se construye billing de producción.

### Incremento 6 — Verificación y escala

**Valor:** análisis más profundos y objetivos compuestos.

- planes de verificación cubiertos por un grant vigente del data owner y, cuando
  generan costo, del principal económico;
- sandbox y network policy;
- targets multi-repositorio;
- perfiles comparables;
- caching seguro;
- cuotas, prioridad y opciones comerciales basadas en datos reales.

## 8. Secuencia de implementación cercana

| PR | Resultado usable | Dependencias |
|---|---|---|
| 1 | output/input classification + casos honestos | ninguna |
| 2 | canonicalización, IDs y schemas base | PR1 |
| 3 | manifest + envelope + run attestation mínima | PR2 |
| 4 | inventory y degradaciones | PR3 |
| 5 | claims/evidence JSONL + renderer | PR3 |
| 6 | verify-bundle + goldens | PR4–PR5 |
| 7 | presupuesto y exclusiones explicables | PR6 |
| 8 | relaciones tipadas | PR6 |
| 9 | conflictos y completion conservador | PR8 |
| 10 | CLI de recuperación progresiva | PR7–PR9 |
| 11 | MCP de lectura y capabilities | PR10 |
| 12 | piloto remoto con metering | evidencia de uso de PR11 |

Cada PR conserva compatibilidad o versiona el contrato. Ninguno depende de
tener lista la facturación futura.

Después de PR6 se realiza una integración real con un agente consumidor antes de
continuar al rediseño comercial. La tabla expresa una secuencia posible, no el
compromiso de ejecutar todos los PRs si la evidencia contradice la tesis.

## 9. Métricas para decidir qué construir

### Utilidad agentiva

- porcentaje de claims consumidos downstream;
- evidencia recuperada por claim;
- reducción de llamadas del agente consumidor;
- decisiones aceptadas, rechazadas o reabiertas;
- tasa de reanudación exitosa;
- falsos conflictos y falsos `complete`;
- costo por claim usado, no sólo producido.

### Operación

- tiempo a primer envelope;
- tiempo a primer claim útil;
- latencia total por perfil;
- cache hit rate;
- cancelaciones y presupuestos agotados;
- bytes de corpus por unidad de cómputo;
- costo interno frente a unidades facturadas.

### Compatibilidad

- bundles rechazados por schema;
- consumidores por versión;
- uso de fallbacks;
- divergencia entre corridas deterministas;
- degradaciones más frecuentes.

### Hipótesis y pruebas de avance

| Hipótesis | Prueba mínima | Señal para continuar | Señal para corregir o detener |
|---|---|---|---|
| Un bundle reduce exploración | comparar agente con y sin bundle en tareas fijadas | menor costo o latencia sin degradar exactitud | el bundle no se usa o induce más errores |
| La recuperación progresiva aporta valor | registrar envelope, claims y evidencia solicitada | una fracción pequeña del corpus resuelve la tarea | consumidores descargan siempre todo |
| El contrato es portable | integrar dos consumidores distintos | ambos consumen schemas sin adapters ad hoc | cada integración requiere lógica específica |
| Existe demanda repetida | piloto sobre tareas reales recurrentes | retorno voluntario y objetivos repetidos | sólo curiosidad o demos aisladas |
| Existe disposición a pagar | quote no vinculante y luego piloto limitado | principal económico acepta precio/cap | utilidad reconocida pero ningún comprador |
| Metering representa costo | comparar unidades con costo interno | correlación estable y explicable | unidades fáciles de manipular o sin relación |

Las métricas no autorizan telemetría remota por defecto. En uso local se guardan
localmente y sólo se comparten mediante consentimiento independiente.

## 10. Riesgos de producto

### Sobreconstrucción

Mitigación: no implementar API comercial hasta que CLI/MCP demuestren patrones
reales de consumo.

### Optimizar para volumen producido

Mitigación: medir claims y evidencia usados downstream; no premiar longitud.

### Confundir score con garantía

Mitigación: claims, verificaciones y completion separados; lenguaje contractual
que no venda certificación implícita.

### Prompt injection entre agentes

Mitigación: provenance obligatoria, contenido tratado como datos, operaciones
mutantes separadas y autorización externa al bundle.

### Costos impredecibles

Mitigación: estimate/quote, hard caps, resultados parciales y autorización nueva
para ampliar presupuesto.

### Lock-in de transporte o proveedor

Mitigación: bundle portable y schemas públicos; CLI, MCP y API comparten el mismo
contrato.

### Privacidad y propiedad intelectual

Mitigación: minimización, retención configurable, aislamiento, referencias y
hashes antes que copias completas, y red apagada por defecto.

### Integridad de metering y disputas

Mitigación: separar núcleo reproducible, attestation operativa y factura; enlazar
quote, grant y usage; conservar idempotencia y una política explícita para caché,
reintentos, cancelaciones y fallos parciales. Firmas o recibos externos se
evalúan después de validar el modelo, no se simulan con hashes locales.

### Tesis comercial no validada

Mitigación: tratar contratación autónoma como hipótesis. Validar primero utilidad
downstream, repetición y principal económico; no confundir interés técnico con
disposición a pagar.

### Dependencia excesiva de un protocolo

Mitigación: MCP es un adaptador, no el dominio. Los schemas y bundles funcionan
sin MCP y pueden transportarse por CLI, API u object storage.

## 11. Coordinación con AN-KLA

- AN-KLA mantiene el fixture normativo de recuperación y escritura;
- Argos lo consume como caja negra downstream;
- fixtures y expected outputs llevan schema, perfil, revisión y fingerprint;
- el caso compartido conserva fact largo, fact corto, episode fuera de v1 e
  índice ausente con fallback correcto;
- la explicabilidad usa IDs, reasons y costos sin copiar contenido excluido;
- ningún cambio de stream o respuesta presupuestada entra sin perfil versionado;
- Argos registra dependencia operativa y no declara independencia plena.

## 12. Decisiones inmediatas

1. El bundle estructurado será el registro canónico de la evaluación, no una
   autoridad absoluta sobre el objetivo.
2. Markdown será una vista derivada con pérdida.
3. Se implementará primero uso local; MCP antes que API comercial completa.
4. Metering se modelará desde v1, pero billing se pospone.
5. El linker semántico no podrá certificar soporte o refutación.
6. Los resultados parciales serán productos válidos y explicables.
7. Toda expansión de costo requerirá autorización vigente del caller.
8. El desarrollo avanzará por incrementos utilizables, no por capas incompletas.
9. El núcleo reproducible se separará de attestations operativas y facturación.
10. La API comercial sólo avanzará después de validar utilidad y principal
    económico.

## 13. Próximo corte recomendado

La siguiente sesión debe implementar únicamente el Incremento 0 y diseñar los
schemas mínimos del Incremento 1:

- separar inputs de outputs del autoestudio;
- fijar backend e independencia;
- restaurar el gate de frescura;
- definir `evaluation-envelope-v1` y `evaluation-manifest-v1`;
- bosquejar una attestation mínima de ejecución sin estabilizar aún billing;
- añadir canonicalización y tests de fingerprint;
- no implementar todavía MCP, API, pagos, verificación dinámica ni multi-tenant.

Este corte entrega una base comprobable sin bloquear decisiones futuras sobre
transporte, infraestructura o modelo comercial.
