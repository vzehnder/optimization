# Plan de simplificación de la experiencia de BESS Workspace

Fecha de revisión: 2026-09-12. Base: commit `58cf602` y árbol de trabajo local.
Estado: UX-000 en revisión con [línea base reproducible](evidencia/ux-000/README.md); falta confirmar las fronteras TDD. No se han modificado funcionalidades.

La recomendación es organizar la experiencia por tareas: **preparar el modelo, conectar datos, revisar y ejecutar, interpretar resultados y entregar un informe**. La plataforma ya tiene esas capacidades. El cambio consiste en orientar al usuario, reducir lo que debe decidir simultáneamente y mantener disponibles los controles expertos.

## Cómo usar este paquete

1. Leer el [diagnóstico basado en el repositorio](01_diagnostico.md).
2. Adoptar como propuesta de producto los [flujos y reglas de interacción](02_experiencia_objetivo.md).
3. Usar la [matriz de conservación funcional](03_matriz_funcional.md) para comprobar que ninguna capacidad queda inaccesible.
4. Confirmar las fronteras de prueba propuestas en la [estrategia TDD](04_estrategia_tdd.md) antes de escribir pruebas nuevas.
5. Implementar los tickets de esta página, un comportamiento completo por ciclo, y actualizar el [tracker de resolución](issues/tracker_ux.md).
6. Cerrar con el [protocolo de validación y entrega](05_validacion_y_entrega.md).

Las rutas de archivos y los nombres de funciones de cada ticket permiten localizar el código. Los archivos nuevos mencionados dentro de los tickets son propuestas, salvo indicación contraria. Cada ticket requiere una PR revisable con su propio resultado visible; no se exige completar todos para obtener valor.

El [tracker](issues/tracker_ux.md) centraliza estado, responsable, dependencias, bloqueos, PR/commit y evidencia de cierre. UX-000 tiene evidencia preparada; UX-001 a UX-009 siguen pendientes de implementación.

## Orden recomendado

| Ticket | Resultado para el usuario | Prioridad | Dependencias | Tamaño orientativo |
| --- | --- | --- | --- | --- |
| [UX-000](issues/UX-000-acordar-fronteras-y-linea-base.md) | Alcance verificable y recorridos de referencia | P0 | Ninguna | S |
| [UX-001](issues/UX-001-orientacion-y-navegacion.md) | Saber dónde está y qué hacer después | P0 | UX-000 | M |
| [UX-005](issues/UX-005-revisar-y-ejecutar.md) | Resolver bloqueos y ejecutar con contexto claro | P0 | UX-001 | L |
| [UX-006](issues/UX-006-resultados-y-comparacion.md) | Ver primero el resultado y comparar sin perder contexto | P0 | UX-001 | M |
| [UX-002](issues/UX-002-edicion-progresiva-del-modelo.md) | Editar el modelo sin enfrentarse a todos los campos a la vez | P1 | UX-001 | M |
| [UX-003](issues/UX-003-importacion-guiada.md) | Importar datos con errores localizables y recuperación | P1 | UX-002 | L |
| [UX-004](issues/UX-004-catalogo-contextual.md) | Encontrar y usar la fuente correcta desde la necesidad del modelo | P1 | UX-001 | M |
| [UX-007](issues/UX-007-configurar-y-publicar-informes.md) | Preparar y publicar un informe con una vista previa fiel | P1 | UX-006 | M |
| [UX-008](issues/UX-008-consola-de-operador.md) | Configurar y operar sin JSON obligatorio para las tareas habituales | P1 | UX-001 | L |
| [UX-009](issues/UX-009-administracion-comprensible.md) | Entender accesos, tareas programadas y acciones irreversibles | P2 | UX-001 | S |

S/M/L expresan incertidumbre relativa, no fechas comprometidas. UX-005 requiere revisar el contrato de asociaciones y ejecución bajo TS-7; UX-003 requiere probar CSV y XLSX; UX-008 debe preservar concurrencia y configuración completa. Dimensionar después de UX-000.

Primera entrega útil: UX-001 + UX-005 + UX-006. Las demás mejoras pueden entregarse individualmente. Al integrar UX-003/004 con UX-005, repetir el recorrido completo de datos a resultado. No esperar al último ticket para comprobar accesibilidad o regresiones.

## Límites e invariantes

- Mantener React + FastAPI + Julia y las tres raíces: analista, consola y portal. El backend decide la entrada y los permisos.
- Mantener las diferencias entre escenario, caso, variante, rango, versión inmutable y corrida. Usar lenguaje accesible sin fusionar entidades ni cambiar cardinalidades.
- La ejecución por variante ya materializa el snapshot: no obligar a promover manualmente una versión en ese recorrido.
- No ejecutar datos desactualizados, reescribir historia, actualizar revisiones silenciosamente ni convertir unidades o resoluciones implícitamente.
- Conservar el recorrido protegido TS-7 y su confirmación de impacto. Simplificar su lenguaje y contexto, no sus garantías.
- Mantener el editor hidráulico v3 y los caminos expertos; el modelo hidráulico no se convierte en un formulario one-bus.
- No introducir un constructor libre de pantallas, un sistema de i18n, un nuevo motor de ejecución ni una migración de datos como requisito de esta mejora.

## Alcance de la revisión

Se inspeccionaron rutas, componentes, cliente API, endpoints relevantes, pruebas y decisiones de arquitectura. El diagnóstico identifica hechos de código e hipótesis de usabilidad por separado. No constituye una sesión observada con usuarios ni una auditoría visual en navegador. La evidencia de ejecución de pruebas y sus límites se registra en [validación](05_validacion_y_entrega.md).

Se conservaron los cambios locales existentes en `docs/tutorials/guia_analista.md` y `docs/tutorials/manual_completo_uso_pagina_web.md`. Los manuales sirven como contexto, pero el código y las decisiones vigentes prevalecen sobre instrucciones históricas.
