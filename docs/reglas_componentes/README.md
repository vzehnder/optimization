# Cálculos y restricciones por componente con Python

Fecha: 2026-09-25.
Estado: REG-001 a REG-014 implementados y verificados.

El usuario eligió Python con una API de modelado propia y delegó las respuestas
restantes en las recomendaciones del asistente: «vamos con tu recomendación en
todas las preguntas». Las decisiones y la granularidad siguientes se adoptan
por esa delegación; no representan respuestas individuales a una entrevista
completada. El alcance original fue documentación local; posteriormente el usuario
autorizó implementar la siguiente issue mediante TDD.

- [Plan y decisiones](plan.md): alcance, contratos, integración y comprobaciones.
- [Registro de issues](issues/tracker.md): orden, dependencias, historias y avances.
- [Primer issue](issues/REG-001-probar-regla-python.md): guardar y probar una regla
  Python en un entorno aislado desde el contexto de una unidad hidráulica.
- [Runtime y operación](runtime.md): configuración del worker, Docker Linux,
  desarrollo Windows y verificación.

Se aplicaron `grill-me`/`grilling` para identificar las decisiones y `to-issues`
para dividirlas en entregas verticales. El destino solicitado es este directorio,
no un tracker remoto. REG-001 a REG-014 están en `Done`; `AFK` indica que el plan
resuelve sus decisiones de producto y permite implementarlos sin otra entrevista,
siempre que sus bloqueadores estén completados.

## Entregas utilizables

| Entrega | Issues | Resultado demostrable |
| --- | --- | --- |
| Primer recorrido Python | REG-001 y REG-002 | Escribir un límite de caudal, probarlo y comprobar su efecto en una corrida hidráulica. |
| MVP de series y límites horarios | REG-003 | Calcular mínimos/máximos desde series versionadas y usarlos al optimizar. |
| Reglas hidráulicas expresivas | REG-004 a REG-006 | Relacionar unidades y embalses, limitar rampas y establecer presupuestos por ventana. |
| Reutilización y operación del analista | REG-007 a REG-010 | Publicar series derivadas, reutilizar reglas, gestionar cambios e inspeccionar cumplimiento. |
| Otros componentes existentes | REG-011 a REG-013 | Aplicar el mismo lenguaje a hidro simple, baterías, renovables y conexiones de red. |
| Ejecución operativa | REG-014 | Usar reglas fijadas en consolas y ejecuciones programadas. |

Las filas agrupan valor entregado, no imponen una cadena artificial: el tracker
especifica las dependencias reales. Cada issue incluye su UI, API, persistencia,
ejecución aplicable y pruebas de comportamiento. Permisos, aislamiento y snapshots
son parte de las primeras entregas, no tareas pospuestas al cierre.

La secuencia del tracker está completada. Para operar consolas y programaciones
con reglas, consultar [REG-014](issues/REG-014-consolas-y-programaciones.md) y
la [guía de operación](runtime.md#consolas-y-programaciones-reg-014).
