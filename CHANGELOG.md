# Changelog

Este proyecto sigue versionado semántico para releases del paquete. Los schemas
mantienen además su propia versión en el nombre del contrato.

## Unreleased

Sin cambios todavía.

## 0.2.0rc2 — 2026-08-10

### Added

- ayuda informativa y sin efectos laterales mediante
  `python -m argos_epistemic --help` y `--version`;
- rutas accionables para bugs, mejoras, preguntas y coordinación segura de
  vulnerabilidades en el repositorio privado;
- diagnóstico de entorno e instalación en el formulario de bugs.

### Changed

- la instalación desde GitHub Release descarga y verifica el wheel antes de
  instalarlo;
- soporte y contribución enlazan directamente los formularios disponibles;
- la metadata de madurez pasa de Alpha a Beta para reflejar la candidata de
  release, sin prometer compatibilidad `1.x`;
- la ayuda informativa no analiza repositorios ni anticipa la CLI estable del
  Incremento 4.

## 0.2.0rc1 — 2026-08-10

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
- `coverage` agrega por claim y componente independiente y permanece como alias
  de `evidential_coverage` durante `0.2.x`;
- el reporte separa recuperación, estructura, capacidad probatoria y perfiles
  de verificación observados;
- el manifest liga el perfil y los parámetros de cobertura a su fingerprint.

### Migration from 0.1.0

- `coverage` continúa siendo un `float`, pero ahora es alias exacto de
  `evidential_coverage`; deja de sumar volumen bruto de proposiciones y agrega
  claims normalizados por componentes independientes;
- los consumidores que mostraban progreso de descubrimiento deben usar
  `retrieval_coverage` o `structural_coverage`, nunca inferirlo desde
  `coverage`;
- `coverage_capability` y `verification_profiles` son campos aditivos que
  explican qué clase de prueba se observó y con qué perfil;
- `complete=True` es deliberadamente más estricto: duplicados, aliases,
  confianza cero, revisión ausente y procedencia incompleta no crean fuentes
  independientes;
- los verificadores PEP 621 y PEP 508 prueban únicamente declaraciones de
  dependencias; no prueban instalación, importabilidad ni funcionamiento en
  runtime;
- los schemas públicos `v1` conservan su nombre y compatibilidad estructural.

### Release validation

- wheel y sdist inspeccionados por contenido, metadatos y rutas seguras;
- instalación del wheel validada en un entorno Python 3.12 limpio;
- 992 tests y los siete gates locales ejecutados sobre el candidato de release;
  la fase F se verificó además antes y después de su merge.

## 0.1.0 — 2026-08-03

- implementación ejecutable inicial del modelo epistémico;
- extractores L0–L5, presupuesto, cobertura y riesgo;
- casos de estudio, benchmark y siete gates de CI.
