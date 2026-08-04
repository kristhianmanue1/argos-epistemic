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
