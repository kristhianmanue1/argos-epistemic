# Caso de estudio: markupsafe (tercerizado)

> Validación **independiente** de la cadena extractores → §22 → reporte sobre un
> repositorio público ajeno. A diferencia del autoestudio (`case-study-argos.md`),
> aquí analizador y analizado son distintos proyectos. Fuente:
> `https://github.com/pallets/markupsafe`, clonado `--depth 1`, commit
> `b2e4d9c` (David Lord, 2025-09-27).

## Objetivo y aspectos

- `G = seguridad y refactor` de la superficie de escaping.
- `T_G = {escape, native, exception, test, config}`.
- Extractores no funcionales: `sec`.
- Presupuesto: `K_tokens = 300_000`, `K_tool = 2_000`. Umbrales: `θ = 0.8`, `ρ = 0.25`.

## Extracción (L0–L5 + L3 grafo de llamadas)

28 artefactos sobre filesystem real (ignorando `.git`, `.venv`, `__pycache__`, etc.):

| nivel | # | contenido principal |
|---|---|---|
| L0 intención | 1 | `README.md` |
| L1 topología | 1 | árbol de directorios |
| L2 entorno | 11 | `pyproject.toml`, `setup.py`, `uv.lock`, `MANIFEST.in`, `tox.ini`, plantillas `.github/` |
| **L3 contratos** | 1 | **grafo de llamadas simbólico** (88 nodos, 78 aristas) |
| L4 código | 7 | `src/markupsafe/__init__.py`, `_native.py`, `bench.py`, `docs/conf.py` |
| L5 prueba | 7 | `tests/test_escape.py`, `test_markupsafe.py`, `test_leak.py`, `test_exception_custom_html.py` |

`relevance` = mezcla 0.6·lexical + 0.25·`Impact` + 0.15·`Centrality` (términos L3
tool-measured, §6.1). Top impacto de código: `tests/test_markupsafe.py::test_escaping`
(0.10), `src/markupsafe/__init__.py::__radd__` (0.069), `escape` (0.057). La función
central del paquete (`escape`) aparece entre las de mayor radio de impacto —coherente
con la meta `G`.

## Reporte generado

```text
evidence_count  : 14       belief_count    : 14
conflict_count  : 0        compressed_count: 6
coverage        : 1.0      residual_risk   : 0.25
levels_covered  : [2, 4, 5]
evidence_kinds  : [code, config, doc, test]
complete        : True
budget_remaining: tokens 299777 / tool 1986
```

Compresión con pérdida ejercitada sobre datos reales: 6 evidencias resumidas con
digest `φ_E` al superar la capacidad del store, preservando procedencia. 14
creencias (todas `weak`/0.6 o `supported`/0.9 según verificación determinista vs
simbólica), sin conflictos (cada `scope` con una sola `position`).

## Interpretación

1. **Selección budgetada real.** De 28 artefactos el bucle tomó 14 y declaró
   `complete` al alcanzar `coverage = 1.0`, `risk = 0.25 ≤ ρ`. `levels_covered =
   [2,4,5]`: ni `README.md` (L0) ni la topología (L1) ni el grafo (L3) fueron
   seleccionados —su `ΔValue` marginal no ganaba bajo el `R` aproximado. Esto
   evidencia el sesgo declarado en §6.1: al no computar `S_semantic`, la
   selección se apoya en señales léxicas y `README` puntúa bajo para este `G`.
2. **L3 activo e informativo, pero parcial.** El grafo (88 nodos / 78 aristas)
   ubica a `escape` en el conjunto de alto impacto. Es **simbólico best-effort**
   (resolución por nombre corto; markupsafe usa C-extensions nativas y `__dunder__`
   que el AST de Python no ve) → subaproximación del grafo real.
3. **Sesgo de `Impact` hacia tests.** El nodo de mayor impacto es un *test*
   (`test_escaping`), porque los tests son sumideros que llaman a muchos símbolos
   y `Impact = |alcance adelante|/(n−1)` los premia. Para una vista de *impacto de
   producción* debería excluirse `tests/` del cálculo: hallazgo accionable.
4. **Sin conflictos.** Requiere dos evidencias divergentes en el mismo `scope`;
   aquí cada artefacto es único por ubicación. Queda sin ejercitar la rama §11.

## Riesgo residual

- **L3 parcial / sin tipos.** Sin análisis de flujo ni tipos, `Impact` y
  `Centrality` son estimadores burdos; no representan el grafo real.
- **`S_semantic` sin computar.** Sesgo léxico en `R`.
- **`Impact` contaminado por tests.** Ver hallazgo 3.
- **Verificación sólo determinista/simbólica.** Sin L5 dinámico (ejecución) no hay
  evidencia de comportamiento, rendimiendo ni condiciones de carrera.

## Reproducibilidad

```bash
git clone --depth 1 https://github.com/pallets/markupsafe.git /tmp/markupsafe
.venv/bin/python -c "
from argos_epistemic import extract_system, analyze_system, Budget
g = {'name':'seguridad-y-refactor','aspects':['escape','native','exception','test','config'],'non_functional':['sec'],'theta_coverage':0.8,'rho_risk':0.25}
s = extract_system('/tmp/markupsafe', goal=g)
print(s['call_graph'])
print(analyze_system(s, g, Budget(tokens_remaining=300000, tool_remaining=2000)))
"
```
