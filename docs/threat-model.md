# Modelo de amenazas

## Activos

- código, configuración y secretos del entorno evaluador;
- integridad de evidencia, claims, presupuesto y metering;
- autoridad del agente consumidor;
- disponibilidad del proceso de análisis;
- confidencialidad del target analizado.

## Entradas no confiables

- repositorios y archivos analizados;
- nombres, rutas, symlinks y metadata Git;
- logs, perfiles, resultados de tests e historia;
- bundles producidos por terceros;
- memoria recuperada y texto destinado a otros agentes.

Ninguna entrada puede conceder permisos, modificar políticas o declarar su
propia autoridad.

## Amenazas principales

| Amenaza | Estado actual | Control requerido |
|---|---|---|
| prompt injection en artefactos | contenido tratado como dato | mantener separación dato/instrucción en todas las interfaces |
| ejecución de código hostil | `dynamic.py` puede lanzar tests | no ejecutar terceros sin sandbox fuerte y red denegada |
| escape por rutas o symlinks | mitigación parcial por límites locales | validación de raíz y pruebas específicas antes de servicio remoto |
| exfiltración de secretos | saneamiento de entorno disponible | allowlist de entorno, red denegada y logs saneados |
| agotamiento de recursos | caps y presupuesto visibles | límites de CPU, memoria, disco, procesos y tiempo |
| falsificación de bundle | fingerprints detectan alteración accidental | firmas y trust roots para autenticidad futura |
| autoridad autodeclarada | clases separadas del contenido | política del consumidor fuera del bundle |
| metering manipulado | attestation separada | medición del servicio y firma antes de facturación |
| confusión de alcance | claim incluye scope | normalización y compatibilidad explícita de scopes |
| dependencia comprometida | CI instala herramientas externas | revisión de dependencias, hashes y automatización de alertas |

## Supuestos actuales

La implementación de referencia se ejecuta localmente bajo autoridad del
operador. No es un sandbox de seguridad. `run_dynamic=True` sólo debe usarse con
código confiable o dentro de un aislamiento proporcionado externamente.

Los fingerprints proporcionan integridad content-addressed, no autenticidad,
no repudio ni autorización.

## Requisitos antes de MCP o API remota

- límites estrictos de tamaño, profundidad, tiempo y concurrencia;
- resolución segura de rutas y symlinks;
- política de red denegada por defecto;
- entorno y credenciales saneados;
- separación por job y eliminación gobernada de datos;
- autenticación del caller y grants de costo explícitos;
- rate limits, idempotencia y cancelación;
- auditoría de accesos y metering;
- pruebas adversariales con repositorios maliciosos.

## Reporte

Las vulnerabilidades no deben publicarse inicialmente como issue. Sigue el
proceso de [SECURITY.md](../SECURITY.md).
