# Caso de estudio: argos analizado por argos

> Demostración de la cadena **extractor real → algoritmo de §22 → reporte**. Es un
> **autoestudio** (el sistema analizado es el propio repositorio), lo que limita
> la independencia (ver §Riesgo residual). Generado con
> `argos_model.extractors.analyze_path` sobre `HEAD`.

## Objetivo y aspectos

- `G = refactorización` de la implementación de referencia.
- `T_G = {algorithm, config, test, doc}`.
- Extractores no funcionales: `sec`.
- Presupuesto: `K_tokens = 200_000`, `K_tool = 2_000`.
- Umbrales: `θ_coverage = 0.8`, `ρ_risk = 0.2`.

## Extracción (L0–L4 sobre filesystem real)

El extractor recorrió el árbol ignorando `.git/`, `.venv/`, `__pycache__/`,
`.an-kla/` (§`DEFAULT_IGNORES`) y produjo 12 artefactos:

| nivel | cantidad | contenido principal |
|---|---|---|
| L0 intención | 3 | `readme.md`, `AGENTS.md`, `AN-KLA.md` |
| L1 topología | 1 | grafo de directorios (árbol) |
| L2 entorno | 3 | `pyproject.toml`, `requirements.txt`, `.gitignore` |
| L4 código | 4 | `argos_model/*.py`, `tests/test_smoke.py` |
| L5 prueba | 1 | `tests/test_smoke.py` (clasificado como test) |

`relevance` de cada artefacto = aproximación de `R(x|G)` por nombre/extensión
condicionada a `G` (§6.1 declara que `S_semantic` no se computa).

## Reporte generado

```text
evidence_count  : 5        belief_count    : 5
conflict_count  : 0        compressed_count: 0
coverage        : 0.825    residual_risk   : 0.154
levels_covered  : [0, 2, 4]
evidence_kinds  : [code, config, doc]
complete        : True
budget_remaining: tokens 199900 / tool 1995
```

Conclusiones verificadas (5, extraídas del `BeliefStore`): tres con estado
`supported` (confianza 0.9, verificación determinista sobre `doc`/`config`) y dos
`weak` (confianza 0.6, verificación simbólica sobre `code`).

## Interpretación

1. **Selección bajo presupuesto.** Pese a 12 artefactos, el bucle extrajo sólo 5:
   al alcanzar `coverage ≥ θ` y `risk ≤ ρ` sin conflictos críticos, `should_stop`
   detuvo el análisis. Los niveles cubiertos `[0,2,4]` reflejan que la topología
   L1 y la prueba L5 no se seleccionaron —su `ΔValue` marginal no ganaba—. Esto
   ejemplifica el comportamiento central del modelo: no leer todo, sino optimizar
   valor informativo.
2. **Sin conflictos.** No hay divergencia doc↔código sobre un mismo `scope`. La
   detección de conflictos (§11) requiere dos evidencias en el mismo `location`
   con `position` distinta; en este repositorio los artefactos son únicos por
   ubicación. Queda sin ejercitar empíricamente la rama de escalamiento de
   contradicciones.
3. **R approximado, no computado.** La selección usó `relevance` declarada, no
   `R = α·S_semantic + β·Impact + γ·Centrality + …`, porque ni `S_semantic` ni los
   grafos L1/L3 están implementados (§6.1). El `coverage`/`risk` reportados son
   por-aspecto con la heurística de referencia, no una medición fiel del modelo.

## Riesgo residual

- **Autoestudio (severidad alta para validez empírica).** El analizador y el
  analizado coinciden; un repo de terceros daría evidencia independiente. No
  consumida: requiere clonar/inspeccionar un sistema externo.
- **L3/L5 no implementados.** Sin grafo de llamadas ni ejecución, `Impact`,
  `Centrality` y el comportamiento dinámico no se miden.
- **`S_semantic` es LLM-approximated.** Su ausencia sesga la selección hacia
  señales léxicas (nombre/extensión).

## Reproducibilidad

```bash
.venv/bin/python -c "
from argos_model import extract_system, analyze_system, Budget
s = extract_system('.', goal={'name':'refactorizacion','aspects':['algorithm','config','test','doc']})
g = {'name':'refactorizacion','aspects':['algorithm','config','test','doc'],'non_functional':['sec'],'theta_coverage':0.8,'rho_risk':0.2}
print(analyze_system(s, g, Budget(tokens_remaining=200000, tool_remaining=2000)))
"
```
