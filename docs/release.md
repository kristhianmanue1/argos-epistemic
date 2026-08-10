# Publicación de Argos

Este procedimiento produce una release auditable desde un commit exacto. Una
GitHub Release distribuye artefactos; no certifica que el análisis de Argos sea
verdad completa ni sustituye los límites documentados del modelo.

## 1. Preparar el candidato

- partir de `main` limpia y sincronizada;
- usar una rama `codex/release-X.Y.Z`;
- sincronizar la versión en `pyproject.toml`, `CITATION.cff`, README y
  changelog;
- documentar migración y compatibilidad;
- no incluir archivos locales, memoria AN-KLA, secretos ni resultados privados.

Para una prerelease PEP 440, `0.2.0rc1` corresponde al tag SemVer
`v0.2.0rc1`. `coverage` seguirá siendo alias de `evidential_coverage` durante
la serie `0.2.x`.

## 2. Ejecutar los gates

```bash
.venv/bin/python -m ruff check argos_epistemic bench tests scripts
.venv/bin/python -m mypy argos_epistemic
.venv/bin/python -m pytest
.venv/bin/python -c "import argos_epistemic; print(argos_epistemic.run())"
.venv/bin/python examples/regenerate_case_studies.py --target argos --check
.venv/bin/python bench/run_benchmark.py --check
.venv/bin/python -m an_kla --project-root . context status
git diff --check
```

Si GitHub Actions no ejecuta pasos por una limitación administrativa, se
documenta como tal. Los gates locales no se presentan como un check remoto.

## 3. Construir e inspeccionar

Construir desde un checkout limpio del SHA que se etiquetará. El epoch debe ser
el timestamp Unix de ese commit (`git show -s --format=%ct HEAD`):

```bash
SOURCE_DATE_EPOCH=EPOCH .venv/bin/python -m build \
  --sdist --wheel --outdir build/release-raw
.venv/bin/python scripts/normalize_sdist.py \
  build/release-raw/argos_epistemic-0.2.0rc1.tar.gz \
  dist/argos_epistemic-0.2.0rc1.tar.gz --epoch EPOCH
cp build/release-raw/argos_epistemic-0.2.0rc1-py3-none-any.whl dist/
.venv/bin/python -m twine check dist/*
.venv/bin/python scripts/check_release_artifacts.py \
  --version 0.2.0rc1 --dist-dir dist
```

El inspector exige exactamente un wheel y un sdist, verifica metadatos,
dependencias, schemas normativos, archivos de documentación y rutas seguras, y
publica los SHA-256 que deben acompañar la release.

`MANIFEST.in` define explícitamente la documentación, schemas y herramientas
que deben viajar en el sdist; no se confía en la inclusión implícita de
setuptools.

Construir dos veces con el mismo epoch debe producir hashes idénticos. El wheel
honra `SOURCE_DATE_EPOCH`; el sdist de setuptools se normaliza después porque
su tar conserva timestamps y propietarios del host.

## 4. Instalar el wheel aislado

Crear un entorno temporal fuera del repositorio, instalar únicamente el wheel
y sus dependencias, cambiar el directorio de trabajo fuera del checkout y
verificar:

- `importlib.metadata.version("argos-epistemic")`;
- importación de `argos_epistemic`;
- demo mínima;
- carga de todos los schemas normativos;
- verificadores PEP 621 y PEP 508 sobre fixtures controlados.

Importar desde el checkout no demuestra que el wheel sea autosuficiente.

## 5. Publicar

1. fusionar el PR por squash;
2. repetir gates y construcción sobre el commit fusionado;
3. crear el tag anotado `v0.2.0rc1` sobre ese commit;
4. crear una GitHub Release marcada como prerelease;
5. adjuntar wheel, sdist y `SHA256SUMS`;
6. comprobar que los enlaces de instalación descargan los mismos hashes.

La rama se conserva hasta completar la comprobación posterior. PyPI queda fuera
de este flujo mientras no exista Trusted Publishing y CI operativo; nunca se
introducen tokens de publicación en el repositorio.
