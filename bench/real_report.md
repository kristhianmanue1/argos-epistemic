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
| markupsafe | argos(lex) | 1.0 | 0.333 | 13638 | 0.00 | False | 0.160 |
| markupsafe | argos(dense) | 0.214 | 1.0 | 13638 | 0.00 | False | 0.391 |
| markupsafe | argos(dense,impact) | 0.214 | 1.0 | 13638 | 0.00 | False | 0.349 |
| markupsafe | full_read | 0.103 | 1.0 | 13638 | - | - | - |
| markupsafe | lexical_topk | 0.0 | 0.0 | 1198 | - | - | - |
| itsdangerous | argos(lex) | 0.0 | 0.0 | 19771 | 0.00 | False | - |
| itsdangerous | argos(dense) | 0.733 | 1.0 | 19771 | 0.00 | False | 0.325 |
| itsdangerous | argos(dense,impact) | 0.733 | 1.0 | 19771 | 0.00 | False | 0.323 |
| itsdangerous | full_read | 0.344 | 1.0 | 19771 | - | - | - |
| itsdangerous | lexical_topk | 0.727 | 0.727 | 9934 | - | - | - |
| click | argos(lex) | 0.0 | 0.0 | 132098 | 0.00 | False | 0.360 |
| click | argos(dense) | 0.065 | 1.0 | 132098 | 0.00 | False | 0.399 |
| click | argos(dense,impact) | 0.065 | 1.0 | 132098 | 0.00 | False | 0.385 |
| click | full_read | 0.044 | 1.0 | 132098 | - | - | - |
| click | lexical_topk | 0.143 | 0.143 | 12086 | - | - | - |

## Lectura
- **Recall medio**: argos(lex) **0.111**, argos(dense) **1.000**, argos(dense,impact) **1.000**, full_read **1.000**, lexical_topk **0.290**.
- **Brier medio** (calibracion de confianza; solo argos emite confidence): argos(lex) **0.260**, argos(dense) **0.372**, argos(dense,impact) **0.352**.

### Hallazgos sobre codigo real
- **`argos_coverage`/`complete` son 0.00/False en TODAS las filas desde
  `bed0ae7` ("add auditable typed claims"): ese commit separo la relacion
  `mentions` (evidencia semanticamente vinculada) de `supports` (evidencia
  confirmada), y `aspect_score`/`compute_coverage` solo cuentan `supports`.
  La unica via a `supports` sin declaracion explicita es verificacion
  `dynamic` (ejecutar el codigo), que este benchmark **no activa**
  (`extract_system` sin `run_dynamic=True`). Precision/recall siguen siendo
  comparables entre filas (miden seleccion, no confirmacion); `argos_coverage`
  y `complete` ya no lo son hasta que se active verificacion dinamica.
- **El linker denso sube el recall** (recupera aspectos semanticos como
  `injection`/`errors`/`security` que el lexico no puede) — confirma en codigo
  real el beneficio ya visto en micro-fixtures. Esto se mide por seleccion
  (precision/recall), no por `argos_coverage`.
- **Tendencia a sobre-enlazar documentacion/ejemplos**: los ficheros cortos
  y saturados de palabras-aspecto (ejemplos, stubs de tipado, config) ganan la
  similitud densa frente al codigo fuente grande y diluido.
- **Gate de evidencia productiva (item 2)**: `production_sources_met` sigue
  vigente como segunda barrera anti-sobreafirmacion (evidencia con
  `impact=0` no basta), pero hoy queda subsumido por el gate `supports`
  descrito arriba: ningun aspecto llega a `complete=True` sin verificacion
  dinamica, independientemente de `production_sources_met`.
- **Costo del honestidad**: al no poder detenerse por sobreafirmacion, argos
  lee TODO el repo (tokens ~= full_read) cuando ningun aspecto alcanza apoyo
  productivo. El ahorro por seleccion solo aparece si `should_stop` dispara con
  apoyo productivo real (palanca: que el codigo productivo enlaces).
- **Palanca prior de impact** (`argos(dense,impact)`, `link_impact_weight=1.0`):
  levanta el link efectivo del codigo productivo (`sim + w*impact`) para que
  enlace a similitud baja, donde los docs cortos ganaban. Comparar recall y
  Brier de `argos(dense)` vs `argos(dense,impact)` mide si recupera codigo gold
  sin inflar ruido. Es opt-in (default weight 0 -> no-op en fixtures sin impact).
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

## Validez del gold y lectura del Brier (importante)
- El Brier ~0.40 **no es una medida limpia de calibracion**: el gold es
  single-annotator y 'canonico' (estrecho). Ficheros relevantes pero no
  canonicos cuentan como falsos positivos. Verificado en click: `utils.py`
  (impact 0.42, importado por todo) y `shell_completion.py` (trata de
  comandos, impact 0.43) los enlaza el linker con razon, pero el gold los
  excluye -> inflan el Brier sin que el modelo 'falle'.
- El Brier medido es un **techo** que mezcla defecto del modelo y estrechez
  del gold. Desambiguarlo requiere multi-annotator y/o un gold 'relevante'
  (no solo canonico) -> follow-up C1, fuera del alcance de este reporte.
- El gate de evidencia productiva (item 2) ya impide la sobreafirmacion
  (`complete=False` sin apoyo productivo real); la propiedad epistemicamente
  critica (no sobreclaimar) se cumple independientemente del Brier.
