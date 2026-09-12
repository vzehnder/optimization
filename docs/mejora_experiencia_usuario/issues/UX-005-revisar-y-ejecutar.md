# UX-005 · Revisar la preparación y ejecutar con contexto

Estado: In Review. Prioridad: P0. Dependencias: UX-001. Tamaño: L.

## Problema y resultado

«Vincular y correr variante» agrupa cambios de datos y ejecución, mientras otros controles ofrecen validación/promoción manual. El usuario debe saber qué va a ejecutar, qué impide hacerlo y cómo corregirlo. Ejecutar una variante válida sigue materializando automáticamente una versión inmutable.

## Código y contratos

- `frontend/src/Workspace.tsx`: `CaseInputVariantPanel`, `CaseInputVariantBindingEditor`, `ExpertVersionForm`, `ScenarioVersionRunControl`.
- `frontend/src/DraftEditor.tsx`: acciones de validación y promoción, estado dirty y avisos de desactualización.
- Cliente: `listCaseInputVariants`, `validateCaseInputVariant`, `runCaseInputVariant`, operaciones de bindings existentes.
- Backend: `app/main.py` rutas `/api/scenarios/{scenario_id}/case/variants/*`, `input_variants.py`, `required_signals.py`, `variant_staleness.py`, `time_series_bindings.py`.
- Regresión: `App.test.tsx`, `tests/test_ts3_case_variant_api.py`, `tests/test_variant_staleness.py`, `tests/test_ts7_009_run_materialization.py` y `tests/test_ts7_008_case_time_series_bindings.py`.

## Pasos de implementación

1. Mostrar el estado de preparación descrito en el diseño: modelo, necesidades, rango, cambios y validación. Derivarlo de contratos existentes, incluyendo el detalle de variantes. Carga/error/desconocido nunca equivalen a listo.
2. Mantener selector de variante y clonación; exponer clonación bajo «Gestionar variantes». No crear otra variante por defecto ni fusionar escenario y caso.
3. Separar la elección/confirmación de fuentes de la acción de ejecutar. En canónico, enlazar al recorrido protegido y sus prevalidaciones. En compatibilidad, reutilizar los endpoints/adaptadores permitidos; no crear un escritor nuevo ni un bypass de impacto.
4. Retirar del botón final la responsabilidad de hacer un bucle oculto de nuevos bindings. «Ejecutar» opera con la selección ya confirmada. Si el guardado compatible requiere varios requests, explicar aceptación parcial, refrescar el estado público y no ejecutar después de un fallo.
5. Si la UI necesita saber qué operación está permitida y el contrato no lo expone, extender de forma aditiva el detalle público de variante/objeto con capacidades calculadas en backend. Confirmar F3, describir el esquema y probar C6 activo/inactivo antes de usarlo. `ts_next_canonical_read` no es ese contrato.
6. Reemplazar la entrada habitual de rango por fecha/hora con zona/offset explícitos y resumen de `[inicio, fin)`. Conservar entrada ISO avanzada. Mostrar cobertura común como ayuda, sin asumir que intervalos superpuestos garantizan ausencia de huecos o igualdad de resolución.
7. Al cambiar una fuente, conservar el rango digitado y marcar su incompatibilidad si corresponde. No reiniciarlo silenciosamente. Ofrecer «Usar cobertura disponible» como acción explícita, con la cobertura validada por backend.
8. «Revisar preparación» reutiliza la validación de variante. Muestra causas de desactualización y enlaces correctos. Una validación aceptada solo aplica a la selección/rango revisados; todo cambio posterior invalida esa presentación.
9. «Ejecutar» llama al endpoint de variante, bloquea doble clic durante el envío y navega al ID aceptado. El servidor vuelve a validar. No reintentar automáticamente una mutación si hubo timeout; consultar el historial y mostrar «No pudimos confirmar el envío» antes de proponer un nuevo intento. No prometer idempotencia que el API no ofrece.
10. Mantener importar JSON, validar/promover, abrir/borrar versión cuando corresponda y ejecución manual dentro de Avanzado. Señalar que ese camino es independiente del recomendado por variante.

## Secuencia TDD sugerida

F1/F2 y F3 propuestas:

1. RED: escenario con una señal faltante muestra la necesidad y enlaza a corregirla; ejecutar permanece bloqueado. GREEN: primer estado y enlace.
2. RED: después de confirmar fuentes y validar un período de dos horas, el usuario ve variante y período, ejecuta y abre una corrida en cola; no necesita promoción manual. GREEN: primera ejecución guiada completa.
3. RED: cambiar una fuente conserva el rango digitado y expone el hueco del fixture; no acepta ejecución. GREEN: edición de rango y feedback.
4. RED: otra sesión cambia una dependencia tras revisar; el envío es rechazado, la selección se conserva y por la API no aparece una corrida de ese intento. GREEN: conflicto y recarga del estado.
5. RED en F3 si se toca el contrato: una ejecución aceptada conserva revisión exacta, actor y rango en su versión consultable; la histórica previa permanece igual. GREEN: cambio mínimo compatible.
6. RED: doble clic durante un envío pendiente lleva a una sola corrida aceptada; timeout muestra resultado incierto y acceso a historial, sin envío automático repetido. GREEN: protección/reconciliación de UI.

Cada conducta es un ciclo separado. No crear un orquestador genérico ni reescribir validación/runner para facilitar los tests.

## Aceptación

- La persona puede responder «qué falta» y «qué se ejecutará» desde la revisión.
- Ejecución por variante no exige crear versiones manuales ni reconfirma bindings ya aceptados.
- Guardados parciales, timeout y rechazo del servidor no se representan como éxito ni como ausencia garantizada de efectos.
- Staleness por modelo, parámetros y series permanece fail-closed. No hay actualización silenciosa a la última revisión.
- Se respetan `[inicio, fin)`, offsets, huecos y resolución sin conversiones implícitas.
- Casos hidráulicos, versiones expertas, corridas históricas y ambos estados C6 relevantes conservan su comportamiento.

Si cambia materialización o generación, ejecutar integración con Julia real según el protocolo. Si solo cambia presentación, usar regresiones del backend y del navegador apropiadas. La revisión posterior decide extracciones del componente; no forma parte del ciclo RED → GREEN.

## Resolución

- Responsable: Codex. Inicio y entrega para revisión: 2026-09-12.
- Estado: In Review; aceptación del resultado pendiente.
- Base: `e4eec65`, que integra la implementación de UX-001. Commit solicitado por el usuario: `feat(ux): guide variant preparation and execution`; sin PR.
- Implementado: preparación y bloqueos con destinos de corrección, fuentes confirmadas antes de revisar/ejecutar, período con fecha/hora y offset, cobertura comprobada por servidor, gestión de variantes, revisión exacta TS-7 y recuperación de fallos parciales/inciertos.
- Contrato aditivo: detalle `preparation` calculado por backend y revisión canónica mediante `/validate`; no se cambia el escritor, el generador ni el materializador de corridas.
- Fronteras: F1/F2/F3 confirmadas explícitamente por el usuario con «confirmo» en esta conversación.
- Evidencia: [ciclos RED → GREEN, comandos, paridad y límites](../evidencia/ux-005/README.md).
- Pruebas: 179 componentes, 14 navegador y 57 Python aprobadas; 13 PostgreSQL omitidas. Build, TypeScript, ESLint y contrato OpenAPI comprobados. El formato global conserva 24 fallos previos.
- Revisión visual: formulario en 1440, 1280 y 320 píxeles, ampliación CSS al 200 %, teclado y axe; capturas locales regenerables.
- Guías actualizadas: [analista](../../tutorials/guia_analista.md) y [manual completo](../../tutorials/manual_completo_uso_pagina_web.md).
- Revisión posterior: se mejoró el formato de los cambios; no se introduce un orquestador ni una extracción general del workspace. Sin modificaciones de lógica matemática, transacciones o esquema persistente.
