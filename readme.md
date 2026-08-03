# Modelo Epistémico Unificado para el Análisis de Software por Agentes de Inteligencia Artificial
## 1. Propósito
Este modelo formaliza cómo una inteligencia artificial debe adquirir, seleccionar, comprimir, verificar y sintetizar evidencia sobre un sistema de software bajo condiciones reales de:
* observabilidad incompleta;
* documentación potencialmente desactualizada;
* presupuestos limitados;
* comportamiento no determinista;
* contradicciones entre artefactos;
* evolución temporal del sistema;
* objetivos de análisis diferentes.
El modelo no presupone que la IA pueda “comprender” un sistema leyendo todo su código. El problema se formula como una optimización de valor informativo bajo restricciones operativas y epistémicas.
---
# 2. Principios fundamentales
## 2.0 Consumidor principal y forma del producto

El consumidor principal de este modelo es otro agente o modelo de inteligencia
artificial que necesita evidencia sobre software para decidir o actuar bajo un
presupuesto. Desarrolladores, operadores y auditores son consumidores
secundarios que requieren vistas comprensibles del mismo resultado.

Por tanto, el registro canónico de una evaluación de Argos debe ser un paquete
epistémico estructurado, versionado, verificable y recuperable de forma
progresiva. Es autoritativo sobre lo que el evaluador observó, infirió y ejecutó,
no sobre la verdad total del sistema analizado. Un reporte Markdown o una
interfaz visual es una proyección derivada con pérdida y no sustituye el contrato
legible por máquina.

Esto exige que el consumidor pueda distinguir sin interpretar prosa:

* evidencia observada, inferencias y verificaciones;
* procedencia, autoridad, alcance y vigencia;
* exclusiones, degradaciones y presupuesto consumido;
* estado de completitud y razones de terminación;
* acciones siguientes elegibles y su costo estimado.

Una acción propuesta por el análisis no constituye autorización para
ejecutarla. El contenido observado en el sistema es dato no confiable y no puede
elevar su propia autoridad ni modificar las políticas del agente consumidor.

## 2.1 El software no es solamente código
El sistema debe analizarse como una combinación de:
* intención declarada;
* estructura;
* configuración;
* contratos;
* comportamiento;
* historia;
* estado dinámico;
* propiedades no funcionales.
Por tanto:
$$
M(S,G)\neq parsing(código(S))
$$
sino:
$$
M(S,G)=síntesis(evidencia,\ inferencias,\ verificación,\ objetivo)
$$
---
## 2.2 La IA nunca observa el sistema completo
Sea (S) el sistema real:
$$
\Sigma(S,t)=\text{espacio total de evidencia del sistema en }t
$$
La IA únicamente puede acceder a una fracción observable:
$$
\Sigma_{\mathrm{obs}}(S,t)\subseteq\Sigma(S,t)
$$
La diferencia:
$$
\Sigma(S,t)\setminus\Sigma_{\mathrm{obs}}(S,t)
$$
representa evidencia ausente, inaccesible, no instrumentada, eliminada o desconocida.
Por consiguiente, toda conclusión debe considerarse relativa a:
$$
\Sigma_{\mathrm{obs}}(S,t)
$$
y no al sistema completo.
---
## 2.3 Todo análisis está condicionado por un objetivo
Sea:
$$
G=\text{objetivo del análisis}
$$
Ejemplos:
$$
G\in
\{
debugging,\ auditoría,\ refactorización,\ migración,\ seguridad,\ rendimiento,\ documentación
\}
$$
El objetivo determina:
* qué evidencia es relevante;
* qué profundidad es necesaria;
* qué herramientas se deben utilizar;
* qué propiedades no funcionales deben activarse;
* qué umbral de confianza se exige;
* cuándo puede terminar el análisis.
No existe un contexto universalmente óptimo. Existe un contexto óptimo condicionado a (G).
---
# 3. Presupuesto operativo multidimensional
El agente opera bajo un presupuesto:
$$
K=
$
K_{\mathrm{tokens}},
K_{\mathrm{tool}},
K_{\mathrm{latency}},
K_{\mathrm{compute}}
$
$$
donde:
* $K_{\mathrm{tokens}}$: capacidad de contexto y generación;
* $K_{\mathrm{tool}}$: número o costo de llamadas a herramientas;
* $K_{\mathrm{latency}}$: tiempo máximo admisible;
* $K_{\mathrm{compute}}$: capacidad de ejecución, indexación o análisis.
El costo de una acción (a) se expresa como:
$$
Cost(a)=
$
c_{\mathrm{tokens}},
c_{\mathrm{tool}},
c_{\mathrm{latency}},
c_{\mathrm{compute}}
$
$$
Una acción es factible cuando:
$$
Cost(a)\preceq K_{\mathrm{remaining}}
$$
La relación $\preceq$ se evalúa componente por componente.
---
# 4. Niveles de extracción de evidencia
Se define una familia de extractores:
$$
L_n:S,t\rightarrow\Sigma_n\subseteq\Sigma_{\mathrm{obs}}(S,t)
$$
para:
$$
n\in{0,1,2,3,4,5}
$$
## (L_0): intención declarada
Lee:
* README;
* PRD;
* ADR;
* documentación funcional;
* especificaciones;
* diagramas declarados;
* guías de operación.
Produce:
$$
\Sigma_0=
\{
propósito,\ dominio,\ usuarios,\ restricciones,\ decisiones\ declaradas
\}
$$
La evidencia de (L_0) no constituye verdad del sistema. Constituye una colección inicial de afirmaciones e hipótesis declaradas.
---
## (L_1): topología estructural
Lee:
* árbol de directorios;
* límites de paquetes;
* módulos;
* repositorios;
* capas;
* workspaces;
* relaciones entre componentes.
Produce:
$$
\Sigma_1=
\{
grafo\ topológico,\ límites,\ módulos,\ relaciones\ estructurales
\}
$$
La salida debe representarse como grafo, no como listado plano de archivos.
---
## (L_2): entorno reproducible y configuración
Lee:
* manifiestos;
* lockfiles;
* archivos de construcción;
* contenedores;
* pipelines;
* configuración;
* plantillas de entorno;
* infraestructura como código.
Produce:
$$
\Sigma_2=
\{
stack,\ versiones,\ configuración,\ proceso\ de\ build,\ entorno\ declarado
\}
$$
(L_2) es fuente primaria para el estado declarado o reproducible, pero no es necesariamente fuente de verdad del estado desplegado.
Debe contrastarse con:
$$
build,\ image,\ deployment,\ runtime
$$
---
## (L_3): puntos de entrada y contratos
Lee:
* funciones de arranque;
* controladores;
* endpoints;
* comandos;
* consumidores de eventos;
* schemas;
* OpenAPI;
* GraphQL;
* protobuf;
* tipos públicos;
* interfaces.
Produce:
$$
\Sigma_3=
\{
grafo\ inicial\ de\ control,\ contratos,\ vocabulario,\ fronteras
\}
$$
Este nivel permite estimar:
* flujos;
* dependencias;
* superficie pública;
* radio de impacto;
* compatibilidad.
---
## (L_4): comportamiento e invariantes
Lee:
* servicios;
* reglas de dominio;
* mutaciones;
* validaciones;
* autorización;
* transacciones;
* manejo de errores;
* rutas alternativas;
* pruebas relevantes.
Produce:
$$
\Sigma_4=
\{
invariantes,\ reglas,\ estados,\ efectos,\ excepciones,\ comportamiento
\}
$$
Debe distinguirse entre:
* comportamiento declarado;
* comportamiento implementado;
* comportamiento probado;
* comportamiento accidental.
---
## (L_5): ejecución, historia y despliegue
Lee o ejecuta:
* tests;
* builds;
* linters;
* logs;
* métricas;
* trazas;
* perfiles;
* git log;
* blame;
* historial de despliegues;
* imágenes activas;
* configuración efectiva.
Produce:
$$
\Sigma_5=
\{
comportamiento\ observado,\ estado\ desplegado,\ historia,\ fallos,\ concurrencia
\}
$$
Aunque (L_5) suele activarse después de los niveles estructurales, puede invocarse anticipadamente cuando el objetivo (G) exige evidencia dinámica inmediata.
---
# 5. Extractores no funcionales transversales
Las propiedades no funcionales no constituyen un nivel (L_6). Son dimensiones transversales:
$$
L_{\mathrm{NF}}=
\{
L_{\mathrm{sec}},
L_{\mathrm{privacy}},
L_{\mathrm{perf}},
L_{\mathrm{reliability}},
L_{\mathrm{compliance}},
L_{\mathrm{operability}}
\}
$$
Su activación depende de (G):
$$
L_{\mathrm{NF}}^*(S,G)
=
\{
L_{\mathrm{NF}}^i(S)
\mid
R(L_{\mathrm{NF}}^i\mid G)>\tau_{\mathrm{NF}}
\}
$$
Ejemplos:
$$
G=\text{auditoría de software médico}
$$
activa preferentemente:
$$
L_{\mathrm{sec}},
L_{\mathrm{privacy}},
L_{\mathrm{compliance}},
L_{\mathrm{reliability}}
$$
mientras que:
$$
G=\text{reducción de latencia}
$$
activa:
$$
L_{\mathrm{perf}},
L_{\mathrm{reliability}},
L_{\mathrm{operability}}
$$
La evidencia no funcional se mantiene inicialmente en un canal separado:
$$
E_{\mathrm{NF}}
$$
y se fusiona con el contexto general únicamente cuando aporta valor al objetivo.
---
# 6. Relevancia computable
Cada unidad de evidencia (x) recibe una puntuación:
$$
R(x\mid G)\in[0,1]
$$
Una aproximación operativa es:
$$
R(x\mid G)=
\alpha S_{\mathrm{semantic}}(x,G)
+
\beta Impact(x,G)
+
\gamma Centrality(x)
+
\eta Risk(x,G)
+
\mu Freshness(x)
$$
donde:
* $S_{\mathrm{semantic}}$: similitud entre evidencia y objetivo;
* (Impact): radio de impacto probable;
* (Centrality): centralidad en grafos de llamadas o dependencias;
* (Risk): severidad asociada al artefacto;
* (Freshness): vigencia temporal de la evidencia.
Con:
$$
\alpha+\beta+\gamma+\eta+\mu=1
$$
El extractor filtrado queda definido como:
$$
L_n^*(S,G,t)=
\{
x\in L_n(S,t)
\mid
R(x\mid G)\geq\tau_n
\}
$$
El umbral $\tau_n$ puede determinarse mediante:
* percentil de relevancia;
* presupuesto restante;
* cobertura faltante;
* riesgo;
* objetivo;
* costo marginal.
Cuando el presupuesto disminuye, $\tau_n$ puede aumentar para hacer la selección más estricta.
## 6.1 Computabilidad y estimadores
Las fórmulas de (R(x\mid G)) (§6) y (Value) (§20) mezclan términos de naturaleza distinta. Para no presentar como computable lo que no lo es, se declara la clase de cada término y su estimador práctico:
* (Freshness(x)): **computable**; (e^{-\lambda_n(t-t_x)}) con (t_x) de mtime/git (§14).
* (Risk(x,G)): **tool-measured**; severidad por tipo de artefacto y hallazgos de linter, tests o CVE (L5/L_NF).
* (Impact(x,G)): **tool-measured**; radio de impacto sobre el grafo de dependencias/llamadas (L1/L3).
* (Centrality(x)): **tool-measured**; centralidad (pagerank/betweenness) sobre el grafo L1/L3.
* (Traceability(\phi_E(E'))): **computable**; vale (1) sii cada creencia resuelve a evidencia con (V) completa (§8, §10).
* (Contradiction), (Staleness) en (Value): **mixto**; (Contradiction) se deriva de ConflictStore (§11); (Staleness=1-Freshness).
* (S_{\mathrm{semantic}}(x,G)): **LLM-approximated**; similitud evidencia(\leftrightarrow)objetivo. No tiene estimador cerrado. En la implementacion de referencia es un *surrogate* lexico plugable (Jaccard de tokens, no fiel) que se inyecta via ``semantic_fn``; un aproximador basado en embeddings/LLM puede reemplazarlo y su incertidumbre debe propagarse como dependencia (§10).
Implicancia operativa: los términos `tool-measured` sólo son computables cuando el extractor correspondiente existe. En la implementación de referencia (`argos_epistemic/`) los extractores (L_1)–(L_5) están implementados a nivel lectura/simbólico (L_3 grafo de llamadas, L_4 comportamiento/invariantes por AST, L_5 pytest e histórico), por lo que (Impact) y (Centrality) se computan sobre el subgrafo de producción; $S_{\mathrm{semantic}}$ se aproxima con un surrogate léxico plugable, (Freshness) se computa por mtime con tasa $\lambda_n$ por nivel (§14) y (R) se mezcla como $0.40\,lexical + 0.18\,S_{semantic} + 0.18\,Impact + 0.12\,Centrality + 0.12\,Freshness$. La propagación de confianza conservativa (§10, $Conf(b)\leq\min_{d_i\in Dep(b)}Conf(d_i)$) se aplica además sobre beliefs y propositions por dependencias.
Notación: las llaves literales de conjuntos se escriben $\{\,\}$; el modo display usa ($$$\dots$$$).
---
# 7. Separación entre evidencia e inferencia
El modelo debe separar obligatoriamente dos estados.
## 7.1 Estado de evidencia
$$
E(n)
$$
contiene únicamente unidades observadas o derivadas mediante herramientas verificables.
Cada unidad se representa como:
$$
e_i=
(
contenido_i,
tipo_i,
fuente_i,
localización_i,
timestamp_i,
nivel_i
)
$$
---
## 7.2 Estado de creencias
$$
B(n)
$$
contiene:
* hipótesis;
* inferencias;
* conclusiones provisionales;
* relaciones derivadas;
* contradicciones;
* preguntas abiertas.
Cada creencia se representa como:
$$
b_i=
(
claim_i,
confidence_i,
status_i,
provenance_i,
dependencies_i
)
$$
La actualización del estado de creencias se define como:
$$
B(n+1)=Update(B(n),E(n+1),V,G)
$$
Las inferencias nunca deben reingresar al conjunto de evidencia como si fueran observaciones.
---
# 8. Compresión con pérdida controlada
La función de compresión opera sobre evidencia, no sobre creencias indistintamente:
$$
E_c(n)=
\phi_E
\left(
E_c(n-1)\cup L_n^*(S,G,t),
K
\right)
$$
La salida de $\phi_E$ debe preservar trazabilidad:
$$
\phi_E(x)=
(
summary(x),
provenance(x),
verification(x),
loss(x)
)
$$
## 8.1 Invariantes obligatorios de compresión
Toda política de compresión debe preservar:
1. puntos de entrada;
2. contratos públicos;
3. versiones exactas;
4. límites arquitectónicos;
5. invariantes de negocio relevantes;
6. errores y contradicciones;
7. evidencia de seguridad o cumplimiento crítica;
8. referencias a evidencia original;
9. nivel de confianza;
10. estado temporal de la evidencia.
Una compresión es inválida cuando elimina información necesaria para verificar una conclusión vigente.
Formalmente, para un conjunto de invariantes (Q_G):
$$
Q_G(E)=Q_G(\phi_E(E))
$$
La compresión puede perder detalle sintáctico, pero no debe perder propiedades críticas condicionadas al objetivo.
---
# 9. Verificación epistémica
La verificación no debe representarse únicamente como un escalar.
Se define:
$$
V(x,\Sigma_{\mathrm{obs}})
=
(
c_x,
s_x,
P_x,
m_x,
t_x
)
$$
donde:
* $c_x\in[0,1]$: confianza;
* (s_x): estado epistémico;
* (P_x): provenance o evidencia de soporte;
* (m_x): método de verificación;
* (t_x): instante o vigencia.
Los estados posibles son:
$$
s_x\in
\{
supported,
weak,
unknown,
conflicted,
contradicted
\}
$$
## 9.1 Tipos de verificación
### Determinista
Adecuada para:
* presencia de archivos;
* versiones;
* configuración;
* rutas;
* símbolos exactos.
Herramientas:
* lectura directa;
* `find`;
* `ripgrep`;
* parsers;
* inspección de lockfiles.
### Simbólica
Adecuada para:
* grafos de llamadas;
* tipos;
* contratos;
* alcance;
* dependencias;
* flujo estático.
Herramientas:
* AST;
* LSP;
* análisis de datos;
* análisis de flujo;
* compilador.
### Dinámica
Adecuada para:
* comportamiento;
* rendimiento;
* condiciones de carrera;
* integración;
* configuración efectiva;
* despliegue.
Herramientas:
* tests;
* ejecución;
* logs;
* trazas;
* profiling;
* inspección de runtime.
### Histórica
Adecuada para:
* intencionalidad;
* regresiones;
* decisiones previas;
* evolución de contratos.
Herramientas:
* git log;
* blame;
* PR;
* historial de despliegues;
* ADR.
---
# 10. Propagación de confianza
Si una conclusión (b) depende de evidencias o hipótesis previas:
$$
Dep(b)={d_1,d_2,\dots,d_m}
$$
su confianza no puede exceder la de sus dependencias críticas.
Una política conservadora es:
$$
Conf(b)\leq
\min_{d_i\in Dep(b)} Conf(d_i)
$$
Una política ponderada puede ser:
$$
Conf(b)=
V_{\mathrm{direct}}(b)
\cdot
\prod_{d_i\in Dep(b)}
Conf(d_i)^{w_i}
$$
donde:
$$
\sum_iw_i=1
$$
Las afirmaciones provenientes de (L_0) se mantienen como hipótesis declaradas hasta ser contrastadas con (L_1), (L_2), (L_3), (L_4) o (L_5).
La validación de intención puede expresarse como:
$$
V_0(x)=
\alpha V_{\mathrm{docs\leftrightarrow topology}}
+
\beta V_{\mathrm{docs\leftrightarrow contracts}}
+
\gamma V_{\mathrm{docs\leftrightarrow behavior}}
+
\eta V_{\mathrm{docs\leftrightarrow runtime}}
$$
Los pesos dependen de (G).
---
# 11. Contradicciones
Una contradicción no equivale a falta de evidencia.
Se define un registro:
$$
Conflict=
(
claim,
evidence^+,
evidence^-,
scope,
severity,
resolutionStatus
)
$$
El sistema debe distinguir entre:
* evidencia ausente;
* evidencia insuficiente;
* fuentes desactualizadas;
* divergencia entre ramas;
* divergencia entre build y runtime;
* contradicción entre documentación y código;
* contradicción entre contrato e implementación;
* contradicción entre implementación y ejecución.
Si:
$$
s_x=conflicted
$$
el agente no debe elegir silenciosamente una fuente. Debe:
1. conservar ambas evidencias;
2. identificar su alcance temporal y ambiental;
3. elevar la contradicción;
4. seleccionar una acción de desambiguación.
---
# 12. Cobertura semántica
La cobertura permite determinar si el contexto acumulado es suficiente.
Sea (T_G) el conjunto de aspectos requeridos por el objetivo:
$$
T_G=
\{
t_1,t_2,\dots,t_m
\}
$$
Cada aspecto tiene un peso:
$$
w_i,\qquad\sum_iw_i=1
$$
La cobertura se define como:
$$
Cov(E,B,G)=
\sum_{i=1}^{m}
w_i
\cdot
Coverage(t_i)
\cdot
Confidence(t_i)
$$
con:
$$
Cov(E,B,G)\in[0,1]
$$
Una alternativa basada en evidencia es:
$$
Cov(E,G)=
\frac{
\sum_{x\in E}
R(x\mid G)\cdot Conf(x)
}{
\sum_{y\in Candidate(G)}
R(y\mid G)
}
$$
Esta segunda expresión solo es computable cuando existe una aproximación razonable del conjunto candidato.
Por tanto, para implementación se recomienda la cobertura por aspectos (T_G), ya que no presupone conocer toda la evidencia posible.
---
# 13. Riesgo de error por omisión
El riesgo asociado a la ausencia de un nivel se expresa como:
$$
H(n\mid G)=
P
\left(
error
\mid
L_n^*\not\subseteq E,
L_{<n}\subseteq E,
G
\right)
$$
Sin embargo, el riesgo real debe incluir severidad:
$$
Risk_n=
P(error_n)\cdot Severity(error_n)
$$
Esto corrige el problema de (L_5):
* algunos fallos dinámicos tienen baja frecuencia;
* su severidad puede ser crítica.
Por tanto, un nivel con baja probabilidad de aportar evidencia puede seguir siendo obligatorio si su riesgo residual es elevado.
---
# 14. Temporalidad y frescura
Todos los niveles pueden evolucionar, aunque con tasas diferentes.
Se define:
$$
L_n(S,t)
$$
y una tasa estimada de cambio:
$$
\lambda_n=
\text{frecuencia esperada de cambio de }L_n
$$
Una configuración típica es:
$$
\lambda_0<\lambda_1<\lambda_2\approx\lambda_4<\lambda_3<\lambda_5
$$
Esta relación no es universal; depende del sistema.
La frescura de una evidencia puede calcularse como:
$$
Freshness(x,t)=
e^{-\lambda_n(t-t_x)}
$$
donde (t_x) es el instante de observación.
Así, la temporalidad no infla toda la formalización, pero sí afecta la vigencia y la relevancia de cada evidencia.
---
# 15. Acciones elegibles y precedencia
La jerarquía $L_0\rightarrow L_5$ no debe modelarse como una restricción absoluta.
En su lugar, se define un conjunto de acciones:
$$
A=
\{
extract,
inspect,
trace,
execute,
verify,
compress,
rollback,
synthesize
\}
$$
Cada acción (a) tiene prerequisitos:
$$
Prereq(a)
$$
Una acción es elegible cuando:
$$
Eligible(a)
\iff
Prereq(a)\subseteq Resolved(E,B)
$$
o cuando el riesgo de no ejecutarla permite una excepción controlada.
La siguiente acción se selecciona mediante:
$$
a^*
=
\arg\max_{a\in Eligible}
\frac{
\mathbb{E}[\Delta Value(a\mid G)]
}{
Cost(a)
}
$$
considerando además:
$$
RiskReduction(a)
$$
Por tanto:
$$
Utility(a)=
\frac{
\alpha\mathbb{E}[\Delta Cov]
+
\beta\mathbb{E}[\Delta Conf]
+
\gamma\mathbb{E}[\Delta RiskReduction]
}{
WeightedCost(a)
}
$$
y:
$$
a^*=\arg\max_{a\in Eligible}Utility(a)
$$
---
# 16. Política práctica de exploración
Para evitar que el modelo se reduzca a una optimización inoperable, se adopta una política híbrida.
## Fase A: orientación mínima obligatoria
Resolver evidencia suficiente de:
$$
L_0\rightarrow L_1\rightarrow L_2\rightarrow L_3
$$
hasta obtener:
* propósito provisional;
* mapa estructural;
* entorno técnico;
* puntos de entrada;
* contratos relevantes;
* discrepancias iniciales.
No es necesario completar exhaustivamente estos niveles.
---
## Fase B: exploración adaptativa
El agente decide entre:
* profundizar en (L_3);
* analizar (L_4);
* ejecutar (L_5);
* activar $L_{\mathrm{NF}}$;
* retroceder;
* ampliar observabilidad;
* sintetizar.
La decisión se basa en:
* cobertura faltante;
* confianza;
* contradicciones;
* riesgo;
* costo marginal;
* presupuesto restante.
---
# 17. Bucle de refinamiento
El retroceso no debe limitarse a:
$$
V(x)<\delta
$$
También debe activarse cuando:
$$
s_x\in{conflicted,contradicted}
$$
o cuando:
$$
RiskResidual(G)>\rho
$$
La política general es:
$$
NeedRefinement(x)
\iff
Conf(x)<\delta_x
\lor
Status(x)\in{conflicted,contradicted}
\lor
Risk(x)>\rho_x
$$
El nivel de retroceso se determina mediante las dependencias de la afirmación:
$$
k=
\min
\{
nivel(d)
\mid
d\in Dep(x),\ d\text{ no resuelto}
\}
$$
No siempre se debe retroceder al nivel inmediatamente anterior. Debe regresarse al origen causal de la incertidumbre.
---
# 18. Criterios de terminación
El agente puede finalizar cuando se cumplan conjuntamente:
$$
Cov(E,B,G)\geq\theta_G
$$
$$
RiskResidual(G)\leq\rho_G
$$
$$
CriticalConflicts=\varnothing
$$
$$
\forall b\in Conclusions:
Conf(b)\geq\delta_b
$$
o cuando:
$$
K_{\mathrm{remaining}}
$$
no permite una acción cuyo valor marginal esperado justifique el costo.
En este último caso, el resultado debe declararse incompleto y describir:
* evidencia ausente;
* conclusiones no verificadas;
* contradicciones pendientes;
* riesgo residual;
* acciones recomendadas.
---
# 19. Modelo mental final
La síntesis final queda definida como:
$$
M(S,G,t)=
f
\left(
E_c,
B,
\pi,
G
\right)
$$
donde:
* (E_c): evidencia comprimida y trazable;
* (B): estado de creencias;
* $\pi$: política de exploración y razonamiento;
* (G): objetivo.
Sujeto a:
$$
Cost(E_c,B,\pi)\preceq K
$$
y:
$$
\forall b\in M:
V(b,\Sigma_{\mathrm{obs}})
=
(c_b,s_b,P_b,m_b,t_b)
$$
No debe exigirse:
$$
c_b>\delta
$$
para todas las afirmaciones posibles, porque algunas conclusiones válidas pueden ser explícitamente inciertas.
La condición correcta es:
$$
c_b\geq\delta_b
\quad\lor\quad
s_b\in{unknown,conflicted,contradicted}
\text{ declarado explícitamente}
$$
El modelo no oculta incertidumbre; la representa.
---
# 20. Función objetivo global
El problema central es:
$$
\max_{E'\subseteq\Sigma_{\mathrm{obs}}(S,t)}
Value(E',B\mid G)
$$
sujeto a:
$$
Cost(\phi_E(E'))\preceq K
$$
$$
Traceability(\phi_E(E'))=1
$$
$$
RiskResidual(M)\leq\rho_G
$$
Una función de valor posible es:
$$
Value=
\alpha Cov
+
\beta Confidence
+
\gamma RiskReduction
+
\eta Traceability
-
\mu Contradiction
-
\nu Staleness
$$
La jerarquía $L_0\rightarrow L_5$ constituye una heurística de precedencia para aproximar este óptimo, no el objetivo en sí mismo.
---
# 21. Matriz maestra definitiva
| Nivel             | Evidencia principal                             | Representación comprimida                 | Verificación                                    | Riesgo de omisión                                     | Retroceso o escalamiento                               |
| ----------------- | ----------------------------------------------- | ----------------------------------------- | ----------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------ |
| (L_0)             | README, PRD, ADR, documentación                 | Afirmaciones e hipótesis declaradas       | Contraste con (L_1)–(L_5)                       | Muy alto para orientación; variable para exactitud    | Mantener como hipótesis si no se confirma              |
| (L_1)             | Directorios, módulos, paquetes, repositorios    | Grafo topológico                          | Inspección determinista                         | Alto                                                  | Contrastar arquitectura declarada y real               |
| (L_2)             | Lockfiles, build, CI/CD, contenedores, entorno  | Tabla de stack, versiones y configuración | Lectura, build, comparación de imágenes/runtime | Alto                                                  | Escalar a evidencia de despliegue si hay divergencia   |
| (L_3)             | Entrypoints, endpoints, schemas, tipos, eventos | Grafo de control y contratos              | AST, LSP, compilador, análisis de tipos         | Medio-alto                                            | Revisar (L_2) o ampliar contratos                      |
| (L_4)             | Servicios, reglas, invariantes, errores         | Firmas, reglas, estados y efectos         | Análisis simbólico y pruebas                    | Medio                                                 | Regresar al contrato o ejecutar dinámicamente          |
| (L_5)             | Tests, logs, trazas, historial, despliegue      | Resultados, eventos y diffs trazables     | Ejecución e inspección histórica                | Frecuencia variable; severidad potencialmente crítica | Escalar contradicción sin descartar evidencia estática |
| $L_{\mathrm{NF}}$ | Seguridad, privacidad, rendimiento, compliance  | Hallazgos por dimensión                   | Herramientas especializadas                     | Dependiente de (G)                                    | Fusionar por riesgo y presupuesto                      |
---
# 22. Algoritmo de referencia

> Pseudocódigo ilustrativo (no ejecutable tal cual). Implementación de referencia ejecutable en `argos_epistemic/algorithm.py`.

```text
def analyze_system(system, goal, budget, policy):
    evidence = EvidenceStore()
    beliefs = BeliefStore()
    conflicts = ConflictStore()
    required_aspects = derive_goal_aspects(goal)
    enabled_nf = select_non_functional_extractors(goal)
    while budget.has_capacity():
        coverage = compute_coverage(
            evidence=evidence,
            beliefs=beliefs,
            aspects=required_aspects,
        )
        residual_risk = compute_residual_risk(
            evidence=evidence,
            beliefs=beliefs,
            goal=goal,
        )
        if should_stop(
            coverage=coverage,
            residual_risk=residual_risk,
            conflicts=conflicts,
            goal=goal,
        ):
            break
        actions = generate_candidate_actions(
            system=system,
            goal=goal,
            evidence=evidence,
            beliefs=beliefs,
            conflicts=conflicts,
            non_functional_extractors=enabled_nf,
        )
        eligible_actions = [
            action
            for action in actions
            if prerequisites_satisfied(action, evidence, beliefs)
            and budget.can_afford(action.estimated_cost)
        ]
        if not eligible_actions:
            break
        action = max(
            eligible_actions,
            key=lambda candidate: expected_utility(
                candidate,
                goal=goal,
                evidence=evidence,
                beliefs=beliefs,
                budget=budget,
            ),
        )
        result = execute_action(action, system)
        budget.consume(result.actual_cost)
        new_evidence = normalize_evidence(result)
        evidence.add(new_evidence)
        verification = verify_evidence(
            evidence=new_evidence,
            method=action.verification_method,
            system=system,
        )
        beliefs.update(
            new_evidence=new_evidence,
            verification=verification,
            goal=goal,
        )
        detected_conflicts = detect_conflicts(
            evidence=evidence,
            beliefs=beliefs,
        )
        conflicts.merge(detected_conflicts)
        evidence.compress(
            budget=budget,
            preserve_provenance=True,
            preserve_invariants=required_aspects,
        )
    return synthesize_report(
        system=system,
        goal=goal,
        evidence=evidence,
        beliefs=beliefs,
        conflicts=conflicts,
        coverage=compute_coverage(evidence, beliefs, required_aspects),
        residual_risk=compute_residual_risk(evidence, beliefs, goal),
        budget=budget,
    )
```
---
# 23. Salida mínima obligatoria del agente

Toda salida final debe exponer primero una representación estructurada y
versionada. Las secciones siguientes describen su contenido semántico obligatorio
y pueden además proyectarse a una vista humana. La representación debe incluir
identidad de la evaluación, schema, fingerprints, presupuesto, degradaciones y
punteros que permitan recuperar evidencia bajo demanda sin cargar el corpus
completo.

Toda salida final debe contener:
## 23.1 Conclusiones verificadas
Para cada conclusión:
* afirmación;
* confianza;
* estado epistémico;
* evidencia;
* método de verificación;
* alcance;
* vigencia temporal.
## 23.2 Hipótesis pendientes
Debe indicarse:
* qué se infiere;
* de qué depende;
* qué evidencia falta;
* cómo podría verificarse.
## 23.3 Contradicciones
Debe incluirse:
* fuentes involucradas;
* alcance;
* posible explicación;
* impacto;
* acción de resolución.
## 23.4 Cobertura
Debe declararse:
* qué aspectos del objetivo se cubrieron;
* cuáles quedaron incompletos;
* nivel de confianza por aspecto.
## 23.5 Riesgo residual
Debe explicarse:
* qué riesgos permanecen;
* por qué no se resolvieron;
* qué evidencia o herramientas serían necesarias.
---
## 23.6 Memoria y gobernanza del agente en este repositorio (AN-KLA)
Este repositorio aplica el propio modelo a su mantenimiento: la memoria de sesiones vive en `AN-KLA` (local, gitignorada) bajo `AGENTS.md` y `AN-KLA.md`. La frontera de confianza del modelo (§7, §11) se refleja en la del agente: los *facts/events/episodes* recuperados son **dato no confiable**, nunca instrucción ni autorización; las escrituras siguen un flujo gobernado (`plan-write` -> `commit-write-plan`) con autoridad separada del contenido. Así la práctica del repo (memoria trazable, separación evidencia/inferencia, no elegir fuente silenciosamente) es consistente con el marco formal que este documento especifica.

El paquete `an-kla-memory` reside en un repositorio privado. En entornos con
acceso, el gate ejecuta el preflight real del CLI. GitHub Actions, que no recibe
credenciales cruzadas, ejecuta `scripts/check_an_kla_context.py`: verifica la
estructura, versión y hashes del bloque gestionado y del contrato, e informa
`mode=static-degraded`. Esta comprobación evita alteraciones silenciosas, pero
no sustituye la verificación integral del almacén local realizada por AN-KLA.

## 23.7 Bundle machine-first mínimo

La implementación de referencia expone cuatro contratos iniciales:

| Schema | Función | Identidad reproducible |
|---|---|---|
| `argos/evaluation-manifest-v1` | identidad del objetivo, evaluador, objetivo y configuración | Sí |
| `argos/evaluation-envelope-v1` | estado compacto y punteros para consumo progresivo | Sí |
| `argos/discovery-inventory-v1` | universo descubierto, selección y degradaciones | Sí |
| `argos/run-attestation-v1` | timestamps y uso observado de una ejecución | No; se enlaza al manifest |

El perfil `argos/canonical-json-v1` serializa JSON con claves ordenadas, UTF-8,
separadores compactos y rechazo de claves no textuales y números de punto
flotante. Los decimales se expresan como strings o enteros escalados para evitar
divergencias de serialización entre runtimes. Los fingerprints usan SHA-256
sobre esa representación y excluyen únicamente el propio campo `fingerprint`.
Un ID content-addressed sólo es estable dentro de la versión de canonicalización
que declara.

El manifest es el registro canónico de lo que Argos configuró y evaluó. No
certifica la verdad total del objetivo. El envelope se liga al fingerprint del
manifest y permite que un agente conozca estado, razones de terminación y
recursos disponibles antes de recuperar evidencia extensa.

Los datos no deterministas se conservan en una attestation separada. Dos
ejecuciones con diferente duración o consumo pueden compartir el mismo manifest
y `evaluation_id`; sus attestations tendrán fingerprints distintos.

Los JSON Schema normativos se distribuyen dentro de
`argos_epistemic.schemas`. La API mínima permite enumerarlos y leerlos sin acceso
al checkout ni a la red.

El inventario v1 se calcula después de las reglas de ignore y antes de seleccionar
artefactos de contenido. Distingue archivos descubiertos, elegibles, seleccionados
e inelegibles; bytes descubiertos y leídos; exclusiones por cap; y truncados por
límite de lectura. El perfil vigente `legacy-first-400-v1` conserva el límite
lexicográfico de 400 artefactos L4/L5 para reproducibilidad, pero ahora cada
omisión incluye ID, razón y costo aproximado. Los extractores estructurales L3/L4
pueden inspeccionar el conjunto de archivos descubierto independientemente de la
selección de artefactos; `files_selected` no afirma que ningún otro extractor haya
observado metadata o estructura del archivo.

El reporte ejecutable incorpora un bloque `completion` con estado del
procedimiento, degradaciones bloqueantes, reason codes, razón de terminación y
próximas acciones estimadas. Esas acciones requieren autorización independiente:
el resultado nunca amplía por sí mismo el presupuesto o los límites de lectura.
Un objetivo exploratorio puede declarar `accepted_degradations`; la degradación
permanece visible, pero deja de bloquear la completitud del procedimiento. Esta
aceptación forma parte de la configuración del objetivo y no puede inferirse del
contenido analizado.

Esta versión no incluye todavía selección estratificada, claims tipados,
recuperación progresiva, MCP, facturación ni firma de attestations.
---
# 24. Conclusión
La calidad de un agente de análisis de software no debe medirse por:
* cantidad de archivos leídos;
* número de tokens utilizados;
* cantidad de niveles completados;
* extensión de su respuesta;
* apariencia de certeza.
Debe medirse por:
$$
Quality=
f
(
coverage,
confidence,
traceability,
riskReduction,
costEfficiency,
conflictHandling
)
$$
El modelo definitivo queda sintetizado en:
$$
M(S,G,t)=f(E_c,B,\pi,G)
$$
con:
$$
E_c=
\phi_E
\left(
\bigcup L_n^*(S,G,t)
\cup
L_{\mathrm{NF}}^*(S,G,t)
\right)
$$
y:
$$
V(x)=
(
confidence,
status,
provenance,
method,
timestamp
)
$$
La jerarquía $L_0\rightarrow L_5$ conserva su valor como estructura de orientación y precedencia, pero deja de ser una secuencia rígida. El agente debe seleccionar acciones según valor informativo, riesgo, dependencias, cobertura y presupuesto.
El resultado es una arquitectura epistémica auditable: distingue lo observado de lo inferido, conserva la procedencia de cada afirmación, representa contradicciones, controla la pérdida de información y declara explícitamente los límites de su conocimiento.
