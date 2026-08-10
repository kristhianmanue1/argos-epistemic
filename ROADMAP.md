# Roadmap de Argos

Este roadmap registra entregas verificables. No promete fechas ni convierte una
hipótesis comercial en compromiso. El plan estratégico original se conserva en
`examples/plan-mejoras-argos-post-evaluaciones-2026-08-03.md`.

## Principios de entrega

- cada incremento debe ser utilizable verticalmente;
- machine-first, human-inspectable;
- relevancia no equivale a soporte;
- presupuesto, omisiones y degradaciones permanecen visibles;
- las acciones propuestas no conceden autorización;
- no se construye transporte o billing antes de validar el contrato previo.

## Estado

| Incremento | Estado | Resultado |
|---|---|---|
| 0 — Base honesta | completado | casos reproducibles, perfiles explícitos y CI |
| 1 — Bundle local mínimo | completado | canonicalización, manifest, envelope, schemas y attestation |
| 2 — Corpus y presupuesto honestos | completado | inventory, caps, costos, completion y reason codes |
| 3 — Semántica auditable | completado | claims tipados, autoridad y conflictos estrictos |
| 3.5 — Base documental y de confianza | completado en `0.2.0rc1` | contratos, verificación estática, métricas independientes y release reproducible |
| 4 — Acceso agentivo local | siguiente | CLI, recuperación progresiva y MCP de sólo lectura |
| 5 — Servicio controlado | condicionado | API asíncrona, aislamiento y metering |
| 6 — Verificación y escala | condicionado | firmas, perfiles comparables y objetivos compuestos |

## Incremento 3.5 — Base documental y de confianza

Objetivo: permitir que contribuyentes y agentes distingan especificación,
implementación, contratos, riesgos y trabajo futuro antes de ampliar interfaces.

Entregables:

- README orientado a adopción;
- `MODEL.md` como especificación normativa;
- `ARCHITECTURE.md` como descripción ejecutable;
- documentación de contratos y threat model;
- roadmap vigente;
- contribución, seguridad y plantillas GitHub mínimas;
- metadata de distribución coherente.

Criterio de salida: todos los documentos enlazan fuentes vigentes, no prometen
capacidades ausentes y los siete gates permanecen verdes.

Resultado: la fase A–F corrigió admisión, autoridad, independencia,
verificadores declarativos y cobertura por claims; la consolidación de release
añade migración, inspección de artefactos e instalación aislada. La prerelease
`0.2.0rc2` añade descubrimiento informativo y rutas accionables de soporte sin
anticipar la CLI analítica; conserva `coverage` como alias compatible antes de
estabilizar `0.2.0`.

No incluye portal de documentación, gobernanza multiequipo, catálogo completo
de ADRs ni automatización de releases.

## Incremento 4 — Acceso agentivo local

Valor: agentes reales consumen resultados progresivamente sin leer Markdown.

Alcance propuesto:

- CLI local estable para producir y verificar bundles;
- consulta de envelope, inventory y claims;
- recuperación por claim con presupuesto, cursores y límites;
- servidor MCP de sólo lectura sobre bundles existentes;
- capability discovery;
- fixture normativo compartido con al menos dos consumidores.

Gate: dos consumidores distintos deben completar
`envelope → claim → evidencia` y mostrar menor recuperación que una lectura
completa. Si no ocurre, se corrige el contrato antes de construir red o billing.

## Incremento 5 — Servicio controlado

Sólo avanza si el Incremento 4 demuestra utilidad repetible.

- jobs asíncronos e idempotentes;
- aislamiento, retención y cancelación;
- autenticación y spend caps;
- cotización y metering enlazados al resultado;
- piloto limitado con observación de utilidad downstream.

Gate: ningún job excede autoridad o presupuesto y existe un principal económico
identificable con señal real de uso repetido.

## Incremento 6 — Verificación y escala

- firmas de attestations y raíces de confianza;
- políticas de verificación gobernadas;
- targets multi-repositorio;
- perfiles comparables y evaluación longitudinal;
- objetivos compuestos y evidencia operacional más profunda.

## Fuera de alcance cercano

- pagos on-chain;
- marketplace autónomo;
- precios dinámicos complejos;
- suscripciones por asiento humano;
- ejecución arbitraria de terceros sin sandbox;
- garantías de verdad total o certificación universal.
