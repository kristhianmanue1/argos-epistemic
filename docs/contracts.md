# Contratos machine-first

Los contratos versionados de Argos permiten que un agente inspeccione primero
estado e inventario y recupere después sólo la evidencia necesaria.

## Orden de consumo recomendado

1. Verificar `evaluation-manifest-v1` y su fingerprint.
2. Leer `evaluation-envelope-v1` para estado, completion y enlaces.
3. Inspeccionar `discovery-inventory-v1` para conocer omisiones y truncaciones.
4. Seleccionar registros `claim-record-v1` por aspecto, relación y alcance.
5. Recuperar la evidencia referenciada sólo cuando sea necesaria.
6. Leer `run-attestation-v1` si importan costo, tiempo o uso observado.

La recuperación progresiva como interfaz todavía no está implementada; este
orden define el comportamiento que deberán compartir CLI y MCP.

## Contratos disponibles

| Schema | Identidad | Propósito |
|---|---|---|
| `argos/evaluation-manifest-v1` | reproducible | target, evaluador, objetivo y configuración |
| `argos/evaluation-envelope-v1` | derivada del manifest | estado compacto, completion y enlaces |
| `argos/discovery-inventory-v1` | reproducible | universo observado, selección y degradaciones |
| `argos/claim-record-v1` | reproducible | claim, relación, autoridad, alcance y evidencia |
| `argos/run-attestation-v1` | por ejecución | timestamps y uso observado |

Los schemas se distribuyen en `argos_epistemic.schemas` y pueden enumerarse con
`schema_names()` y cargarse con `load_schema(name)`.

## Identidades

- `fingerprint`: SHA-256 del documento bajo `argos/canonical-json-v1`, sin el
  propio campo `fingerprint`;
- `evaluation_id`: identidad derivada del fingerprint del manifest;
- `claim_id`: identidad de perfil, aspecto, texto y alcance;
- `evidence_id`: referencia al artefacto observado.

Las identidades son estables sólo dentro del perfil de canonicalización o
extracción declarado. No son firmas ni conceden autoridad.

## Relaciones y autoridad

`supports` contribuye a cobertura y `refutes` aporta evidencia negativa. Las
relaciones `mentions`, `tests`, `implements` y `configures` no son probatorias.

`authority_class` describe cómo se obtuvo la relación. Es dato para la política
del consumidor, no una orden. El consumidor debe aplicar sus propios límites de
confianza y autorización.

## Completion y degradaciones

`procedure_complete` sólo afirma que el procedimiento satisfizo sus condiciones
de terminación declaradas. No afirma completitud ontológica del target.

Las degradaciones aceptadas permanecen visibles. `next_actions` son propuestas
con costo estimado y `authorization_required`; nunca amplían presupuesto por sí
mismas.

## Compatibilidad

Los nombres de schema incluyen versión mayor. Mientras el paquete permanezca
antes de `1.0`, la API Python puede cambiar, pero un contrato publicado no debe
cambiar de significado silenciosamente. Un cambio incompatible requiere un
nuevo nombre de schema y pruebas de coexistencia.
