# UX-008 · Simplificar configuración y preparación de la consola

Estado: Todo. Prioridad: P1. Dependencias: UX-001. Tamaño: L.

## Problema y resultado

La consola operativa ya tiene edición, bloqueos y resultados completos, pero su configurador exige JSON para parámetros y resultados. El ingeniero debe configurar las opciones habituales con formularios; el operador debe entender los pendientes sin vocabulario interno.

## Código y contratos

- `frontend/src/OperatorConsole.tsx`: `ConsoleDocumentForm`, `OperatorConsoleEditorView`, `ConsoleShellView`, `ConsoleGroupEditor`.
- `frontend/src/signalCatalog.ts`, `PortalResults.tsx` y cliente API existente.
- `app/operator_console.py`, `app/console_series.py`, `app/surface_payloads.py`; `operator_console_config.v1`.
- Regresión: `OperatorConsole.test.tsx`, `tests/test_configuration_layer_operator_console.py`, `tests/test_configuration_layer_console_series_editing.py`, `tests/test_configuration_layer_console_fail_closed.py`, `tests/test_configuration_layer_console_series_selection.py`.

## Pasos de implementación

1. Añadir formularios de parámetros sobre el documento actual: selección de activo/campo permitido, etiqueta, unidad, límites y defaults soportados. Consultar catálogo/contrato existente; no copiar una lista estática de señales.
2. Añadir controles para resultados sobre el mismo esquema: KPIs, gráficos, tablas y opciones admitidas. Mantener los grupos/columnas y controles de fuentes existentes.
3. Conservar «Editar JSON avanzado». Sincronizar con un único documento; un JSON inválido bloquea guardado/cambio de modo sin descartar el texto. Preservar todas las propiedades soportadas que el formulario no edite.
4. Conservar `expected_revision` y errores de conflicto. Un refetch o guardado ajeno no sustituye silenciosamente el formulario local. Activar sigue siendo una acción distinta y usa la revisión vigente.
5. En la consola externa, añadir un resumen de preparación que indique período, parámetros pendientes, grupos de series pendientes y bloqueo real. Cada mensaje dirige al grupo/campo disponible.
6. Mantener guardados de parámetros y series con sus alcances actuales; no agregar «Guardar todo» con falsa atomicidad. Ejecutar solo después de aceptación del guardado y del `run_gate` del backend.
7. Conservar tabla virtualizada, pegado rectangular, columnas bloqueadas, diff opcional, historial, deshacer autorizado, cambio de fuente, leases y recuperación. No convertir el diff opcional en una confirmación obligatoria nueva.
8. Conservar solicitud de revisión solo para bloqueos de ingeniería, acciones internas exactas de reparación y espera de lease para conflictos entre operadores. No habilitar forzar desbloqueo a externos.
9. Mantener resultado/comparación operativos con el payload externo permitido, aunque comparta componentes de presentación con el portal.

## Secuencia TDD sugerida

F1/F2; F3 si cambia esquema o contrato:

1. RED: el ingeniero modifica un límite de parámetro sin JSON, guarda/reabre y prueba la consola con su identidad real; el límite visible corresponde al fixture. GREEN: primer formulario vertical.
2. RED: cambiar un campo simple conserva configuración avanzada de resultados existente tras round-trip. GREEN: edición sobre documento completo.
3. RED: un conflicto de revisión mantiene los cambios locales y explica que aún no se guardaron. GREEN: recuperación sin sobrescritura.
4. RED: el operador con cambios pendientes ve la sección que falta guardar; guardado aceptado habilita ejecutar, pero una pérdida de lease conserva bloqueo y explica la acción posible. GREEN: resumen y enlaces.

Reusar pruebas existentes de 8760 filas, pegado ambiguo, deshacer y comparación como regresión. No duplicarlas con aserciones a filas internas o estado del componente. Agregar un E2E de consola contra API aislada si el recorrido actual no está cubierto: los tests de componentes no prueban cookies y autorización reales.

## Aceptación

- Se configura al menos un parámetro y un bloque de resultados habitual sin escribir JSON.
- El modo experto sigue disponible y no pierde propiedades soportadas; el backend conserva validación final del esquema.
- Activación, desactivación, prueba interna, preparación por variante y coordinación de series conservan sus contratos.
- El operador distingue cambios sin guardar, bloqueo de ingeniería y edición de otra persona.
- Revisión, actor, copia operativa, overrides y revisiones materializadas siguen auditables internamente.
- No aparecen drafts, bindings, hashes, paths ni logs en respuestas/pantallas externas nuevas.

Dividir el ticket en PRs verticales si el configurador es grande: primero un parámetro completo, luego un bloque de resultado y después preparación operativa. Cada una debe ser utilizable y verificable. No comenzar por una refactorización general de la consola.
