# Política de seguridad

## Versiones soportadas

Argos está antes de `1.0`. Sólo la revisión más reciente de `main` recibe
correcciones de seguridad. Las versiones de desarrollo no ofrecen una ventana
formal de soporte.

## Reportar una vulnerabilidad

No abras un issue público. Usa la función **Report a vulnerability** de GitHub
Security Advisories en este repositorio. Incluye:

- versión o commit afectado;
- impacto y escenario de amenaza;
- pasos mínimos de reproducción;
- si requiere `run_dynamic`, red o un repositorio malicioso;
- mitigación conocida, si existe.

No incluyas secretos reales ni datos de terceros. Si Security Advisories no está
disponible, solicita al mantenedor un canal privado sin revelar detalles.

## Alcance especialmente sensible

- escape de rutas, symlinks o sandbox;
- ejecución y aislamiento de código analizado;
- filtración de credenciales o contenido del target;
- falsificación de fingerprints, claims o metering;
- elevación de autoridad desde contenido no confiable;
- denegación de servicio que eluda caps o presupuesto.

## Límite actual

La implementación local no es un sandbox de seguridad. No ejecutes análisis
dinámico sobre código no confiable sin aislamiento externo. Consulta
[docs/threat-model.md](docs/threat-model.md).
