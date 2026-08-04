# API Python actual

La API está en desarrollo y puede cambiar antes de `1.0`. Los schemas
versionados tienen reglas de compatibilidad más estrictas que las firmas Python.

## Análisis

### `analyze_system(system, goal, budget)`

Analiza una descripción de sistema ya construida.

- `system`: mapping con `name` y lista `artifacts`;
- `goal`: mapping con `name`, `aspects` y opciones de terminación;
- `budget`: `Budget(tokens_remaining, tool_remaining)`.

Devuelve un mapping con evidencia, claims, conflictos, cobertura, riesgo, costo,
inventory, completion y conclusiones de compatibilidad.

### `analyze_path(path, goal, budget, ...)`

Descubre un checkout y ejecuta el mismo pipeline. Las opciones dinámicas,
históricas, de logs, perfiles y cobertura habilitan evidencia adicional. No uses
ejecución dinámica sobre código no confiable sin aislamiento externo.

### `run()`

Demo determinista mínima para smoke tests. No es una interfaz de producción.

## Bundle

- `build_manifest(...)` y `verify_manifest(...)`;
- `build_envelope(...)` y `verify_envelope(...)`;
- `build_run_attestation(...)` y `verify_run_attestation(...)`;
- `verify_inventory(...)`;
- `verify_claim_record(...)`;
- `schema_names()` y `load_schema(name)`.

Los verificadores lanzan `BundleContractError`. Consulta
[contracts.md](contracts.md) antes de persistir o intercambiar documentos.

## Canonicalización

- `canonical_json_bytes(value)`;
- `sha256_fingerprint(document)`;
- `fingerprinted_document(document)`;
- `verify_fingerprinted_document(document)`;
- `content_id(namespace, value)`.

El perfil rechaza floats y claves no textuales para mantener portabilidad entre
runtimes. Los decimales contractuales se expresan como strings.

## Perfiles semánticos

`lexical_semantic`, `embedding_semantic` y el backend denso opcional producen
relevancia. Ninguno puede certificar soporte o refutación. El extra `semantic`
instala el backend denso; `languages` habilita extractores tree-sitter.

## Estabilidad

Antes de `1.0`:

- importa desde `argos_epistemic`, no desde módulos internos cuando exista una
  exportación pública;
- fija la versión del paquete;
- valida `schema` y `canonicalization` al consumir documentos;
- no interpretes campos desconocidos como autoridad;
- conserva documentos originales para auditoría.
