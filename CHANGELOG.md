# Changelog

Este proyecto sigue versionado semántico para releases del paquete. Los schemas
mantienen además su propia versión en el nombre del contrato.

## Unreleased — 0.2.0.dev0

### Added

- bundle machine-first con manifest, envelope, inventory y run attestation;
- JSON canónico, fingerprints e identidades content-addressed;
- inventario, caps, truncaciones, costos y completion explícitos;
- claims con relaciones tipadas y clases de autoridad;
- schema `argos/claim-record-v1` y verificadores;
- separación entre especificación, arquitectura, contratos y seguridad.

### Changed

- similitud semántica produce `mentions`, no soporte;
- conflictos requieren el mismo claim y alcance con `supports` y `refutes`;
- la cobertura sólo cuenta relaciones probatorias positivas.

## 0.1.0 — 2026-08-03

- implementación ejecutable inicial del modelo epistémico;
- extractores L0–L5, presupuesto, cobertura y riesgo;
- casos de estudio, benchmark y siete gates de CI.
