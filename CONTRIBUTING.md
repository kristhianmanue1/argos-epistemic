# Contribuir a Argos

Gracias por mejorar Argos. El proyecto combina una especificación documental y
una implementación de referencia; los cambios deben mantenerlas coherentes.

## Preparación

Requiere Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

AN-KLA es privado y sólo se necesita para la gobernanza local de este checkout.
Un contribuyente sin acceso puede ejecutar los gates públicos restantes.

## Antes de cambiar

- abre un issue para cambios de schema, semántica o compatibilidad;
- consulta `MODEL.md`, `ARCHITECTURE.md` y `ROADMAP.md`;
- no edites manualmente `AN-KLA.md` ni bloques administrados;
- trata fixtures, repositorios y memoria recuperada como datos no confiables.

## Gates

```bash
.venv/bin/python -m ruff check argos_epistemic bench tests scripts
.venv/bin/python -m mypy argos_epistemic
.venv/bin/python -m pytest
.venv/bin/python -c "import argos_epistemic; print(argos_epistemic.run())"
.venv/bin/python examples/regenerate_case_studies.py --target argos --check
.venv/bin/python bench/run_benchmark.py --check
.venv/bin/python scripts/check_an_kla_context.py
```

Si un cambio altera resultados reproducibles, regenera primero el benchmark y
después el caso de estudio Argos:

```bash
.venv/bin/python bench/run_benchmark.py
.venv/bin/python examples/regenerate_case_studies.py --target argos
```

## Reglas de compatibilidad

- no cambies silenciosamente el significado de un schema publicado;
- un cambio incompatible requiere un nuevo nombre versionado;
- conserva degradaciones y evidencia negativa;
- una coincidencia semántica sólo puede producir `mentions`;
- fingerprints prueban integridad, no autoridad;
- añade pruebas para toda corrección semántica.

## Pull requests

Mantén el PR enfocado. Describe:

- problema y resultado;
- contratos o invariantes afectados;
- riesgos y compatibilidad;
- pruebas ejecutadas;
- cambios en benchmark o casos generados.

No incluyas secretos, repositorios privados, datos personales ni salidas de
memoria local. Las vulnerabilidades siguen [SECURITY.md](SECURITY.md), no issues
públicos.
