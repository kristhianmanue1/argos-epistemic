# Argos Epistemic

Argos es una implementación de referencia de un modelo para que agentes de IA
analicen software mediante evidencia trazable, presupuesto explícito y
conclusiones auditables.

El consumidor principal es otro agente. La salida canónica es estructurada y
verificable; Markdown es una vista secundaria para inspección humana.

> Estado: release candidate (`0.2.0rc2`). Los contratos versionados son
> utilizables, pero la API Python aún puede cambiar antes de `1.0`.

## Qué ofrece hoy

- descubrimiento e inventario visible del corpus;
- extracción de evidencia en niveles L0–L5;
- presupuesto, truncaciones y degradaciones explícitas;
- claims content-addressed con relaciones tipadas;
- conflictos sólo entre `supports` y `refutes` del mismo claim y alcance;
- manifest, envelope, inventory, claim records y run attestations;
- JSON canónico y fingerprints reproducibles;
- implementación local como librería Python.

Argos no ofrece todavía CLI estable, MCP, API remota, aislamiento fuerte,
facturación, firma de attestations ni compatibilidad `1.x`.

## Instalación de la release candidate

Requiere Python 3.12. Mientras el repositorio sea privado y el paquete no esté
publicado en PyPI, un colaborador autorizado debe descargar y verificar el wheel
de la GitHub Release `v0.2.0rc2` mediante GitHub CLI:

```bash
python3.12 -m venv .venv
gh auth status
gh release download v0.2.0rc2 --repo kristhianmanue1/argos-epistemic \
  --pattern 'argos_epistemic-0.2.0rc2-py3-none-any.whl' --pattern SHA256SUMS
grep 'argos_epistemic-0.2.0rc2-py3-none-any.whl' SHA256SUMS | shasum -a 256 -c -
.venv/bin/python -m pip install ./argos_epistemic-0.2.0rc2-py3-none-any.whl
```

El comando de verificación debe terminar en `OK`. Esta prerelease no se
promoverá a `0.2.0` hasta recibir validación de consumidores. Usuarios externos
no pueden descargarla mientras el repositorio siga privado; hacerla pública o
distribuirla mediante PyPI requiere una decisión separada.

## Instalación para desarrollo

Requiere Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

AN-KLA es una dependencia privada de gobernanza usada por este repositorio. Si
no tienes acceso, instala el paquete y las herramientas de prueba por separado,
como lo hace CI.

## Uso mínimo

```python
from argos_epistemic import Budget, analyze_system

system = {
    "name": "writer",
    "artifacts": [
        {
            "id": "writer.py",
            "kind": "code",
            "level": 4,
            "content": "def write(): ...",
            "relevance": 1.0,
            "implements": [
                {
                    "aspect": "atomicity",
                    "claim": "writes implement compare-and-swap",
                    "scope": "writer-v1",
                }
            ],
        }
    ],
}
goal = {"name": "audit", "aspects": ["atomicity"]}

report = analyze_system(system, goal, Budget(tokens_remaining=10_000, tool_remaining=10))
print(report["claims"])
```

Para descubrir la versión instalada y las entradas públicas sin iniciar un
análisis:

```bash
python -m argos_epistemic --help
python -m argos_epistemic --version
```

Esta interfaz es informativa: no lee repositorios, no ejecuta código y no
anticipa la CLI analítica del Incremento 4. El análisis se realiza hoy mediante
`analyze_path()` o `analyze_system()` desde Python.

`mentions`, `tests`, `implements` y `configures` orientan recuperación, pero no
elevan cobertura. Sólo `supports` aporta evidencia positiva y `refutes`
evidencia negativa. Una acción sugerida por el reporte nunca constituye
autorización para ejecutarla.

El reporte conserva `coverage` como alias numérico de `evidential_coverage` y
añade `retrieval_coverage`, `structural_coverage`, `coverage_capability` y
`verification_profiles`. La cobertura probatoria agrega fuentes independientes
del mismo claim; duplicar una lectura, raíz o ejecución no aumenta el valor.

## Verificación local

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check argos_epistemic bench tests scripts
.venv/bin/python -m mypy argos_epistemic
.venv/bin/python -c "import argos_epistemic; print(argos_epistemic.run())"
.venv/bin/python examples/regenerate_case_studies.py --target argos --check
.venv/bin/python bench/run_benchmark.py --check
```

## Mapa de documentación

- [MODEL.md](MODEL.md): especificación normativa del modelo epistémico.
- [ARCHITECTURE.md](ARCHITECTURE.md): arquitectura de la implementación actual.
- [ROADMAP.md](ROADMAP.md): entregas realizadas, siguiente incremento y gates.
- [docs/contracts.md](docs/contracts.md): contratos machine-first y consumo.
- [docs/api.md](docs/api.md): superficie Python disponible hoy.
- [docs/threat-model.md](docs/threat-model.md): fronteras de confianza y riesgos.
- [CONTRIBUTING.md](CONTRIBUTING.md): flujo de contribución y gates.
- [SECURITY.md](SECURITY.md): reporte responsable de vulnerabilidades.
- [CHANGELOG.md](CHANGELOG.md): cambios por versión.
- [docs/release.md](docs/release.md): construcción, verificación y publicación.

Los casos de estudio reproducibles están en `examples/`; los benchmarks y sus
limitaciones están en `bench/`.

## Ayuda y reportes

- [Reportar un bug reproducible](https://github.com/kristhianmanue1/argos-epistemic/issues/new?template=bug.yml).
- [Proponer una mejora](https://github.com/kristhianmanue1/argos-epistemic/issues/new?template=feature.yml).
- [Hacer una pregunta](https://github.com/kristhianmanue1/argos-epistemic/issues/new?template=question.yml).
- [Seguir el procedimiento de seguridad vigente](SECURITY.md).
- Consultar [soporte](SUPPORT.md), [contribución](CONTRIBUTING.md) y
  [problemas abiertos](https://github.com/kristhianmanue1/argos-epistemic/issues).

No publiques secretos, repositorios privados ni datos personales. Las acciones
sugeridas por Argos tampoco conceden autorización para adjuntar el contenido de
un target a un issue.

## Garantías y límites

Un bundle certifica qué observó, configuró e infirió el evaluador dentro de un
presupuesto. No certifica la verdad completa del sistema analizado. El contenido
de repositorios y bundles se considera dato no confiable.

Las fórmulas de MODEL.md (§6 relevancia, §15 utilidad, §20 valor) son
**normativas**: la implementación de referencia usa aproximaciones declaradas —
`S_semantic` es un surrogate léxico plugable (no semántica fiel), `Impact` y
`Centrality` sólo se computan cuando existe el extractor, y la mezcla real de
`R(x|G)` usa pesos fijos (`0.40 lexical + 0.18 S_semantic + 0.18 impact + 0.12
centrality + 0.12 freshness`), no el resultado de resolver §20. Ver
[MODEL.md §6.1](MODEL.md#61-computabilidad-y-estimadores) para la clase
(`computable`, `tool-measured`, `LLM-approximated`) de cada término.

Consulta [MODEL.md](MODEL.md) para los invariantes formales y
[docs/threat-model.md](docs/threat-model.md) antes de habilitar ejecución
dinámica sobre código de terceros.

## Licencia

Apache License 2.0. Consulta [LICENSE](LICENSE).
