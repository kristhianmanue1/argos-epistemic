# Validacion sobre repos reales (P3)

> Tres repos pequenos de pallets con **gold hand-labeled por aspecto**
(`bench/real_gold.py`), etiquetado leyendo el codigo a mano. Mide si la
seleccion de argos recupera el gold en codigo **real** (no micro-fixture),
con precision/recall/**Brier**/costo, y compara linker lexico vs denso.

**OPT-IN, fuera de CI** (requiere red para clonar). Reproducible por commit.
Linker denso disponible: **True** (`[semantic]` extra).

Commits fijados: `markupsafe` b2e4d9c7687b, `itsdangerous` 672971d66a2e, `click` 00e592cea702

| repo | metodo | precision | recall | tokens | argos_coverage | complete | brier |
|---|---|---|---|---|---|---|---|
| markupsafe | argos(lex) | 1.0 | 0.333 | 13638 | 0.07 | False | 0.160 |
| markupsafe | argos(dense) | 0.214 | 1.0 | 13638 | 0.43 | False | 0.391 |
| markupsafe | full_read | 0.103 | 1.0 | 13638 | - | - | - |
| markupsafe | lexical_topk | 0.0 | 0.0 | 1198 | - | - | - |
| itsdangerous | argos(lex) | 0.0 | 0.0 | 19771 | 0.00 | False | - |
| itsdangerous | argos(dense) | 0.733 | 1.0 | 19771 | 0.80 | False | 0.325 |
| itsdangerous | full_read | 0.344 | 1.0 | 19771 | - | - | - |
| itsdangerous | lexical_topk | 0.727 | 0.727 | 9934 | - | - | - |
| click | argos(lex) | 0.0 | 0.0 | 132098 | 0.03 | False | 0.360 |
| click | argos(dense) | 0.065 | 1.0 | 132098 | 1.00 | False | 0.399 |
| click | full_read | 0.044 | 1.0 | 132098 | - | - | - |
| click | lexical_topk | 0.143 | 0.143 | 12086 | - | - | - |

## Lectura
- **Recall medio**: argos(lex) **0.111**, argos(dense) **1.000**, full_read **1.000**, lexical_topk **0.290**.
- **Brier medio** (calibracion de confianza; solo argos emite confidence): argos(lex) **0.260**, argos(dense) **0.372**.

### Hallazgos sobre codigo real
- **El linker denso sube el recall** (recupera aspectos semanticos como
  `injection`/`errors`/`security` que el lexico no puede) — confirma en codigo
  real el beneficio ya visto en micro-fixtures.
- **Tendencia a sobre-enlazar documentacion/ejemplos**: los ficheros cortos
  y saturados de palabras-aspecto (ejemplos, stubs de tipado, config) ganan la
  similitud densa frente al codigo fuente grande y diluido. Pre-fix esto
  producia sobreafirmacion en `click` (coverage 0.83 + `complete=True` con
  recall 0).
- **Gate de evidencia productiva (item 2)**: `production_sources_met` impide
  declarar `complete` cuando un aspecto solo descansa en evidencia periferica
  (impact=0). Tras el fix, `click` denso ya NO sobreafirma (`complete=False`).
  El Brier sigue alto (~0.40) porque el linker aún enlaza ruido: la calibracion
  de la señal requiera un linker que sesgue codigo > docs (siguiente palanca).
- **Costo del honestidad**: al no poder detenerse por sobreafirmacion, argos
  lee TODO el repo (tokens ~= full_read) cuando ningun aspecto alcanza apoyo
  productivo. El ahorro por seleccion solo aparece si `should_stop` dispara con
  apoyo productivo real (palanca: que el codigo productivo enlaces).
- `lexical_topk` degenera en `click` (aspectos sin overlap con el id del gold).

## Reproducibilidad
```bash
ARGOS_BENCH_REAL_DIR=/tmp/argos-bench python bench/real_repos.py        # escribe real_report.md
ARGOS_BENCH_REAL_DIR=/tmp/argos-bench python bench/real_repos.py --dense # anade fila denso
```

## Honestidad
- Gold etiquetado por una persona (el agente) sobre 3 repos; no es annotation
  multiple ni ciega. Aspectos como `injection`/`errors`/`security` son
  semanticos (sin overlap lexico) para aislar la senal densa.
- Sigue siendo N=3 repos; validacion estadistica amplia queda pendiente.
