# Respuesta del equipo `an-kla-memory` a nuestro issue #10

> Análisis crítico realizado por el equipo de `an-kla-memory` sobre nuestro issue
> [#10](https://github.com/kristhianmanue1/an-kla-memory/issues/10) (abierto desde
> `argos-epistemic`). Recibido el 2026-08-02. Se guarda íntegro para análisis
> crítico y a fondo en próximas sesiones. El análisis se hizo contra el commit
> exacto reportado, `67f6ee4` (v0.1.0-beta.1), extraído en un directorio temporal;
> no modificaron el proyecto ni su memoria. **Notar: corrige varios diagnósticos
> técnicos nuestros.**

## Veredicto general

El issue #10 contiene observaciones útiles, pero mezcla síntomas reales con
diagnósticos técnicos incorrectos.

| Parte | Veredicto |
|---|---|
| Validación estructural de Argos | Confirmada, con límites metodológicos importantes |
| (a) Registros largos no aparecen | Síntoma confirmado; causa BM25 descartada |
| Episodios no recuperados | Confirmado; recuperación sólo consulta `facts` |
| (b) Índice no actualizado tras commit | Confirmado |
| "Lectura stale hasta rebuild" | No confirmado; existe fallback correcto a scan |
| (c) Esquema poco documentado | Fricción confirmada; los JSON Schema sí existen |
| Riesgo de integridad/CAS | No se encontró regresión |
| Pruebas de `67f6ee4` | 124/124 correctas |

---

## 1. Validación externa de Argos

Pudieron reproducir exactamente la extracción estructural usando Argos:

- 56 artefactos.
- Grafo: 260 nodos, 499 aristas, 113 nodos de producción.
- `__main__.main`: impacto 0.839.
- `MemoryStore.commit_write_plan`: impacto 0.375.
- 51 funciones con `raise`.
- 13 clasificadas como validación.

La interpretación de `commit_write_plan` como superficie crítica es razonable. El
código realmente ejecuta: `lock`; lectura y CAS de `CURRENT`; copia defensiva de
los objetos; reconstrucción y validación del plan; `journal prepared`; escritura
de objetos inmutables; segunda comprobación CAS; reemplazo atómico de `CURRENT`;
`journal committed`. (Ver `an_kla/store.py:207` y `an_kla/store.py:297`.)

No obstante, la "validación externa" debe interpretarse estrechamente:

- El grafo de Argos es AST best-effort; resuelve llamadas por nombre corto y no
  realiza inferencia de tipos o flujo.
- Su `impact` mide **alcanzabilidad sintáctica**, no criticidad de negocio ni
  ejecución real.
- Las 51 funciones con `raise` incluyen tests: sólo 113 de las 260 funciones
  analizadas son de producción.
- `ContextPackageError` **hereda de `ValueError`**; la separación observada es
  nominal, no una familia totalmente independiente.

Esto confirma que la arquitectura es **descubrible**, pero no prueba corrección,
atomicidad o seguridad. Esas garantías siguen dependiendo de código y pruebas.

**Problema de reproducibilidad en el reporte de Argos**: reprodujeron todas las
métricas estructurales, pero **no** `coverage=0.8`, `residual_risk=0` ni
`complete=true`. Sin el backend semántico opcional, el mismo pipeline produjo
**cobertura 0.0**. El caso de estudio no registra claramente el backend efectivo,
su versión o fingerprint, y el generador elige entre recuperación densa y lexical
según el entorno. Por tanto, la parte semántica del reporte **no es reproducible
sólo con el documento publicado**.

---

## 2. Observación (a): recall bajo

### Síntoma: confirmado

Reproducido con escritura gobernada: fact corto (30 bytes); fact largo (1407
bytes); episode largo (1666 bytes); consulta equivalente; `assemble-context`
budget 1500.

Resultados:

- El fact largo obtuvo puntuación **10**.
- El fact corto obtuvo puntuación **4**.
- `retrieve(..., budget=1500)` seleccionó **ambos**.
- `assemble-context(..., budget=1500)` sólo incluyó el **fact corto**.
- `excluded_summary` declaró `{"budget": 1}`.
- Con checkpoint sintético, el fact largo comenzó a caber a partir de **2160 bytes**.
- El episodio **nunca** apareció.

El fact largo sí fue encontrado y quedó primero en el ranking; fue excluido
posteriormente porque **no cabía** en la envolvente completa.

### Diagnóstico BM25: FALSO

AN-KLA **no usa BM25**. El perfil FTS5 sólo obtiene IDs candidatos mediante
`MATCH`; después se conserva el mismo ranking lexical. La documentación declara
que FTS5 todavía no usa BM25.

Ranking real:

```
score = cantidad de términos distintos compartidos
orden = score descendente, ID ascendente
```

No existe penalización por longitud documental. (Ver `an_kla/retrieval.py:74`.)

### Causa real 1: presupuesto global

`assemble-context` presupuesta **toda la envolvente**: metadatos; checkpoint
completo; información nueva; diagnósticos; registros recuperados; IDs,
puntuaciones y framing JSON. Por eso un texto de 1407 bytes no puede caber dentro
de una salida total de 1500 bytes. El ensamblador prueba el candidato, lo retira
si excede el presupuesto y continúa buscando candidatos más pequeños
(`an_kla/context.py:72`).

**No es un fallo de ranking; es una interacción entre selección greedy y presupuesto.**

### Causa real 2: episodios fuera de recuperación

El recuperador itera exclusivamente sobre `snapshot.records["facts"]`. Los streams
`events` y `episodes` **no participan** (`an_kla/retrieval.py:78`). Por tanto,
ningún episode, corto o largo, puede aparecer en `retrieve` o `assemble-context`.

Esto está insuficientemente documentado. El README afirma que AN-KLA conserva
hechos, eventos y episodios y recupera contexto, pero no deja claro que la
recuperación v1 **sólo busca hechos**.

### Clasificación

Problema real de **contrato y experiencia** de recuperación, pero no corrupción ni
fallo del índice.

Recomendaciones prioritarias:

- Documentar explícitamente que `retrieval-result/v1` sólo recupera `facts`.
- Documentar que `--budget` de `assemble-context` incluye la envolvente completa.
- Añadir prueba de regresión con un candidato largo de mayor puntuación y uno
  corto de menor puntuación.
- Exponer diagnóstico opt-in por candidato: puntuación, costo y motivo de exclusión.
- Diseñar una proyección recuperable corta (`retrieval_summary`) separada del
  contenido durable completo.
- No prometer recuperación de episodios hasta definir cómo se mezclan streams,
  scoring y procedencia.

---

## 3. Observación (b): índice después de escribir

### Hecho confirmado

`commit_write_plan` no reconstruye el índice. Cada índice está ligado a una
revisión concreta y vive bajo `indexes/<revision>/sqlite-fts5-v1/`. Después de
mover `CURRENT`, el índice anterior sigue asociado a la revisión anterior
(`an_kla/index.py:53`).

### "Lectura stale": DESCARTADO

No encontraron brecha de corrección escritura→lectura:

- Perfil predeterminado: `scan-fallback/v1`; ve inmediatamente la revisión nueva.
- `assemble-context` siempre usa ese perfil.
- Si se solicita FTS5 tras el commit, busca un índice de la revisión nueva.
- Si no existe, declara `index_unavailable` y **degrada al escaneo**.
- **No reutiliza silenciosamente el índice anterior.**

Reproducción:

```
Antes de rebuild:
  profile      = scan-fallback/v1
  degradation  = index_unavailable
  resultados   = fact nuevo + fact anterior

Después de rebuild:
  profile      = sqlite-fts5/v1
  degradation  = none
  resultados   = fact nuevo + fact anterior
```

Coincide con `docs/architecture/0004-index-reference.md:23`. Por tanto:

- "el commit no actualiza el índice": **verdadero**;
- "la recuperación queda stale": **falso**;
- "rebuild cierra la brecha de corrección": **falso**;
- "rebuild elimina una degradación y recupera aceleración": **verdadero**.

Actualizar FTS dentro del commit no parece recomendable para esta fase: aumentaría
la duración del lock, acoplaría una caché derivada al camino autoritativo y podría
convertir fallos de SQLite en fallos de escritura. Es preferible conservar el
fallback correcto y mejorar visibilidad/documentación.

---

## 4. Observación (c): escritura gobernada

### Los JSON Schema ya existen

El repositorio contiene schemas normativos para `WriteProposal`, `WriteAuthority`,
`WriteDecision`, `WritePlan` y certificados de costo. La guía enlaza `docs/schemas`
y muestra una propuesta completa (`docs/write-policy-cli.md:15`). La sugerencia
"crear un JSON Schema" **ya está satisfecha**.

### La fricción de integración sí es real

El feedback sigue siendo válido:

- `plan-write --help` sólo enumera `--proposal` y `--authority`.
- No hay un ejemplo completo de `authority.json`.
- No se explica operativamente cómo calcular `proposal_sha256`.
- No existe un comando de validación o generación.
- El usuario debe conocer combinaciones válidas entre `authority_class` e
  `issuer.kind`.
- El wheel sólo declara `packages = ["an_kla"]`; documentos y schemas no parecen
  instalarse como recursos del paquete (un consumidor instalado desde Git puede no
  tenerlos en su venv).

Clasificación: **defecto de usabilidad/documentación**, no ausencia del contrato
normativo.

Acciones recomendadas:

- Añadir ejemplos completos para `model_derived` y `derived_from_retrieval`.
- Incorporar `an_kla build-proposal`, `build-authority` o al menos
  `validate-write-input`.
- Proporcionar un helper para el hash canónico de la propuesta.
- Empaquetar los schemas como recursos del paquete o exponerlos mediante CLI.
- Ampliar `--help` con la ruta de la guía y las clases permitidas por CLI.
- Mantener fuera del CLI la fabricación de `tool_observed` y `channel_confirmed`.

---

## Priorización recomendada (por el equipo an-kla)

- **P1**: aclarar y probar el contrato de recuperación sólo sobre `facts`.
- **P1**: diseñar representación recuperable corta para contenido durable largo.
- **P2**: diagnóstico explicable de exclusión por presupuesto.
- **P2**: documentación completa y helpers para escritura gobernada.
- **P2**: documentar que `rebuild` restaura el perfil FTS, no la corrección de
  lectura.
- **P3**: exigir que los reportes de Argos registren commit, linker efectivo,
  versión, configuración y fingerprint.

---

## Cierre del equipo an-kla

No encontraron evidencia de un bug en CAS, atomicidad, integridad o actualización
de `CURRENT`. El problema más importante del issue es de **semántica y ergonomía
de recuperación**: el producto guarda tres streams, pero sólo recupera uno, y un
presupuesto pequeño puede ocultar un fact altamente relevante sin explicar cuál fue
excluido.
