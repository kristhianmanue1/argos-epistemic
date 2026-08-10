# Política de seguridad

## Versiones soportadas

Argos está antes de `1.0`. Sólo la revisión más reciente de `main` recibe
correcciones de seguridad. Las versiones de desarrollo no ofrecen una ventana
formal de soporte.

## Reportar una vulnerabilidad

No publiques detalles de una vulnerabilidad en un issue. Mientras el repositorio
sea privado, GitHub no expone Private Vulnerability Reporting para reporteros
externos. Un colaborador autorizado debe crear únicamente una
[pregunta sin detalles sensibles](https://github.com/kristhianmanue1/argos-epistemic/issues/new?template=question.yml)
solicitando ser invitado a un draft Security Advisory. El mantenedor abre el
advisory e invita allí al reportero antes de intercambiar:

- versión o commit afectado;
- impacto y escenario de amenaza;
- pasos mínimos de reproducción;
- si requiere `run_dynamic`, red o un repositorio malicioso;
- mitigación conocida, si existe.

No incluyas secretos reales ni datos de terceros. El issue inicial sólo debe
decir que existe un posible reporte de seguridad y el nombre de usuario que debe
ser invitado; no debe revelar el hallazgo, el target ni datos sensibles.

Si el repositorio se hace público, se debe habilitar Private Vulnerability
Reporting y actualizar esta política y el selector de issues en el mismo cambio,
antes de solicitar reportes externos.

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
