# Arquitectura de Argos

Este documento describe la implementación ejecutable actual. La especificación
normativa vive en [MODEL.md](MODEL.md); el trabajo futuro, en [ROADMAP.md](ROADMAP.md).

## Límites del sistema

Argos recibe un objetivo, un presupuesto y una descripción de sistema o ruta
local. Produce un reporte estructurado con evidencia, claims, cobertura, riesgo,
conflictos, costos y estado de terminación.

El núcleo actual es una librería local. No incluye daemon, MCP, API de red,
almacenamiento multiusuario ni plano de facturación.

## Flujo de datos

```text
target + goal + budget
        |
        v
discovery inventory
        |
        v
candidate actions -> evidence -> verification
                              |
                              v
                    typed relationships
                              |
                              v
                    claims + conflicts
                              |
                              v
            coverage + risk + completion
                              |
                              v
                  machine-first report
```

1. `extractors.py` descubre archivos, registra límites y crea artefactos.
2. `algorithm.py` elige acciones bajo presupuesto, conserva evidencia y deriva
   relaciones tipadas.
3. `canonical.py` define serialización reproducible, fingerprints e IDs.
4. `bundle.py` construye y verifica los contratos distribuidos.
5. `schemas/` contiene los JSON Schema normativos de cada contrato.

## Componentes

| Componente | Responsabilidad | No garantiza |
|---|---|---|
| `extractors.py` | discovery, relevancia y perfiles semánticos | comprensión semántica fiel |
| `callgraph.py` | grafo L3 y centralidad aproximada | resolución dinámica completa |
| `behavior.py` | señales L4 obtenidas por AST | equivalencia conductual |
| `dynamic.py` | ejecución de tests y señales runtime | aislamiento de código hostil |
| `sandbox.py` | entorno aislado y saneado para ejecución dinámica | aislamiento fuerte de OS/red |
| `verifiers.py` | protocolo de verificación estática, normalización de claims e independencia entre fuentes | que un claim estrecho implique una propiedad amplia |
| `dependency_verifiers.py` | verificadores concretos PEP 621 y PEP 508 sobre el protocolo de `verifiers.py` | instalación, resolubilidad o funcionamiento de la dependencia |
| `dense_semantic.py` | backend denso opcional para `S_semantic` | fidelidad semántica por defecto |
| `ts_extractors.py` | registro de extractores L3 basados en tree-sitter | cobertura de todos los lenguajes |
| `history.py`, `logs.py`, `profile.py`, `coverage.py` | evidencia L5 histórica u operacional | vigencia o causalidad |
| `algorithm.py` | selección, claims, conflictos, cobertura y terminación | verdad total del target |
| `canonical.py` | identidad reproducible dentro de un perfil | autenticidad criptográfica |
| `bundle.py` | contratos y verificaciones estructurales | firma o autorización |

## Modelo de información

La evidencia conserva qué fue observado y cómo se verificó. Una proposición
enlaza evidencia con un aspecto mediante una relación:

- `mentions`: relevancia temática;
- `supports` y `refutes`: polaridad probatoria;
- `tests`, `implements`, `configures`: relaciones estructurales.

El `claim_id` depende de perfil, aspecto, texto y alcance. Un conflicto requiere
el mismo `claim_id` y alcance, además de evidencia `supports` y `refutes`.

El planificador clasifica cada acción candidata por capacidad
(`retrieval_only`, `structural_relation`, `probatory_static`,
`probatory_dynamic`) y separa las expectativas de recuperación, cobertura,
descubrimiento de contradicción y reducción de riesgo. Una acción sólo recibe
expectativa de un bien que su capacidad puede entregar; la relevancia alimenta
la recuperación, nunca la prueba. Las expectativas probatorias provienen de un
perfil de calibración versionado con incertidumbre declarada, cuyo valor por
defecto es cero, y se calculan contra el estado probatorio vigente. Las
declaraciones malformadas fallan cerrado con diagnóstico estructurado. Ver
[MODEL.md §20.1](MODEL.md#201-utilidad-operativa-y-capacidad-de-acción).

`probatory_dynamic` nombra el método de producción, no una autorización: la
ejecución dinámica se autoriza en la frontera de extracción y ninguna etiqueta
de capacidad concede autoridad.

## Frontera de verificación e independencia

`verifiers.py` separa el candidato temático de la prueba. Un verificador
devuelve únicamente lo que afirma (`VerifierClaim`); el perfil versionado, el
método, la ejecución, la revisión del target y las huellas de las raíces
observadas los **estampa la frontera** (`run_verifier`) a partir de entradas
confiables. Ni el target analizado ni un verificador defectuoso pueden declarar
esos campos, que son precisamente las entradas del cálculo de independencia.
Una excepción, una entrada no soportada, un aspecto fuera del objetivo o un
claim vacío producen `degraded` o `unknown` con confianza cero; nunca `supports`.

La frontera automática de dependencias transporta reporte, resultados y costo
en un único `DependencyVerificationOutcome`. `analyze_system` no confía sólo en
el nombre de la dataclass: valida recursivamente resultados, colecciones,
contadores, manifests, bytes leídos, costo reconstruible y la identidad
content-addressed del cargo; después cobra ese cargo una sola vez al `Budget` y
admite exactamente los resultados del mismo outcome. Duplicarlos además por la
entrada genérica colapsa por `result_id`.
Los manifests se abren con `O_NOFOLLOW`, se leen hasta EOF mediante un bucle
acotado y se cobran por bytes reales; sin protección atómica de symlinks la
plataforma falla cerrada.

La independencia **no** es un hash de `perfil + método + raíz`: ese cálculo
haría que dos verificadores distintos sobre el mismo archivo parecieran
independientes y no representaría conjuntos de raíces parcialmente solapados
(`{x,y}` y `{y,z}` producen hashes distintos pero comparten `y`). Se computa
como componentes conexos sobre **raíz compartida, ejecución compartida, familia
de instrumento compartida y derivación** (incluido un padre externo ausente del
conjunto evaluado), y se cuentan **componentes, no salidas**.

La familia es el instrumento; la versión se conserva para reproducción y
auditoría y liga la identidad del resultado, pero **no** crea un segundo
testigo: `pep621@1` y `pep621@2` son un instrumento, no dos.

La **revisión objetivo evaluada es una entrada explícita**, nunca elegida para
favorecer el resultado: las fuentes de otras revisiones se ignoran en vez de
acreditarse, y un análisis que no declara revisión no puede demostrar
corroboración. Ante ausencia de procedencia —familia, ejecución, revisión o
raíz— los resultados no aportan grupo adicional: la duda nunca multiplica
fuentes.

La identidad del resultado no es la independencia de la fuente: dos alias
producen `result_id` distintos y aun así colapsan como una sola fuente porque
comparten huella de raíz.

La corroboración se evalúa por claim normalizado: soportes de claims distintos
del mismo aspecto no se suman. Un aspecto queda satisfecho cuando al menos uno
de sus claims alcanza el mínimo de grupos independientes exigido.

La agregación consume claims ya tipados, pero **no es homogénea** y conviene no
describirla como si lo fuera:

| Métrica | Agregación vigente |
|---|---|
| `residual_risk` | por claim normalizado; repetir una lectura no cambia el valor |
| `coverage` | **legacy: por volumen de proposiciones**; varias lecturas del mismo claim la elevan. Limitación conocida, no propiedad deseada; corrección asignada a PR F |
| `min_sources` / independencia | por claim y grupo independiente; protección **transitoria** de `complete` mientras `coverage` siga siendo legacy |

Las relaciones no probatorias (`mentions`, `tests`, `implements`, `configures`)
quedan fuera de los numeradores y denominadores probatorios, de modo que la
recuperación no puede desplazar a la prueba. Ver
[MODEL.md §13.1](MODEL.md#131-agregación-operativa-del-riesgo-residual) y
[§12.1](MODEL.md#121-corroboración-e-independencia-entre-fuentes).

La mezcla de relevancia es una aproximación declarada de la especificación
formal (MODEL.md §6): pesos fijos (`0.40 lexical + 0.18 S_semantic + 0.18 impact
+ 0.12 centrality + 0.12 freshness` en `extractors._blend_relevance`), con
`S_semantic` como surrogate léxico plugable (`lexical_semantic` por defecto, no
fiel), no la resolución de la optimización de §20. Ver
[MODEL.md §6.1](MODEL.md#61-computabilidad-y-estimadores) para la clase
(`computable`, `tool-measured`, `LLM-approximated`) de cada término y su
estimador práctico.

## Núcleo reproducible y datos operacionales

Manifest, inventory y claim records usan JSON canónico y fingerprints. El
manifest representa configuración e identidad de evaluación. Timestamps y uso
observado pertenecen a una run attestation separada, porque pueden cambiar entre
ejecuciones equivalentes.

Un fingerprint detecta alteración; no demuestra identidad del productor. Las
firmas están fuera del alcance actual.

## Extensibilidad

Los extractores L3 pueden registrarse por lenguaje. Los linkers semánticos son
inyectables, pero sólo producen relevancia (`mentions`). Un backend semántico no
puede elevar por sí mismo una relación a soporte o refutación.

Toda interfaz futura —CLI, MCP o API— debe consumir los mismos contratos y no
crear una segunda semántica paralela.

## Fronteras de confianza

- target, artefactos, memoria recuperada y bundles externos son no confiables;
- una declaración observada no se convierte en verificación directa;
- acciones siguientes requieren autorización independiente;
- ejecución dinámica de terceros no debe habilitarse sin aislamiento adicional;
- presupuesto observado y degradaciones deben permanecer visibles.

Consulta [docs/threat-model.md](docs/threat-model.md) para riesgos y controles.

## Decisiones pospuestas

- formato de recuperación progresiva y cursores;
- transporte MCP;
- API asíncrona e idempotencia remota;
- sandbox fuerte y política de red;
- firma y cadena de confianza;
- metering comercial y facturación;
- compatibilidad estable previa a `1.0`.
