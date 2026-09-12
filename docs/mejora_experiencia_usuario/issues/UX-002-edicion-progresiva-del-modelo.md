# UX-002 · Editar el modelo con complejidad progresiva

Estado: In Review. Prioridad: P1. Dependencias: UX-001. Tamaño: M.

## Problema y resultado

IDs, schema, solver y opciones poco frecuentes compiten con los parámetros de cada componente. La persona debe poder editar lo habitual y desplegar el detalle técnico sin perder ningún valor del modelo.

## Código y contratos

- `frontend/src/DraftEditor.tsx`: `DraftEditor`, inputs, estado de guardado y acciones del caso generado.
- `frontend/src/Workspace.tsx`: editor hidráulico y acceso al mismo; `frontend/src/styles.css`.
- APIs existentes de lectura/guardado del draft y validación/promoción en `app/main.py`; reglas en `app/draft_editor.py`.
- Regresión: `App.test.tsx`, `tests/test_structured_draft_editor.py`, `tests/test_draft_generated_system_case.py`, `tests/test_stale_hierarchy_validation.py`, prueba de hidráulica en Playwright.

## Pasos de implementación

1. Mostrar una lista de componentes con nombre, tipo y estado de errores. Abrir el componente seleccionado y conservar acceso a agregar/quitar cada tipo soportado.
2. Agrupar campos por propósito: capacidad/límites, estado inicial, operación y economía. Colocar IDs, schema y solver en opciones técnicas. Los campos obligatorios de hidro y otras tecnologías permanecen descubribles y se abren cuando hay errores.
3. Mantener una única fuente de datos del formulario fuera de paneles desmontables. Preservar campos omitidos, `null`, `0`, booleanos y estructuras JSON soportadas; no recrear el documento desde solo los inputs visibles.
4. Conservar la barra de guardado existente y mejorar sus mensajes: pendiente, guardando, guardado y error. No introducir autoguardado de modelo ni validación en cada pulsación.
5. Al enviar un formulario inválido, abrir el panel necesario, listar el error con enlace y enfocar el campo. Una respuesta tardía de guardado no debe declarar guardados cambios hechos después del envío.
6. Extender la protección de salida a la navegación nueva y comprobar atrás/adelante además de enlaces y recarga. La confirmación permite seguir editando o descartar; no ejecutar ni promover al guardar.
7. Mantener accesos a preview, validación y creación de versión experta. El editor hidráulico v3 conserva herramientas, curvas y reglas propias; cambiar su ubicación no implica reescribir su canvas.

## Secuencia TDD sugerida

F1/F2 propuestas:

1. RED: editar capacidad de una batería, guardar, recargar y ver el valor aceptado. GREEN: primera sección de edición progresiva.
2. RED: abrir opciones avanzadas, modificar una condición terminal, cerrarlas, cambiar un campo básico y reabrir después de guardar; ambos valores se conservan. GREEN: documento compartido y round-trip.
3. RED: un error de curva hidro dentro de un panel cerrado lleva al campo sin perder los otros cambios. GREEN: resumen y foco contextual.
4. RED: navegar atrás con cambios pendientes permite seguir editando y no pierde valores; un guardado fallido tampoco. GREEN: protección del recorrido nuevo.

No agregar pruebas de cada acordeón o clase CSS. Si los pasos no modifican el contrato, ejecutar regresiones API existentes sin inventar nuevas pruebas de backend. Si cambia el payload, F3 debe confirmarse y comprobar el documento por lectura pública.

## Aceptación

- Todos los parámetros y tipos de componentes existentes siguen editables y se conservan tras guardar/reabrir.
- Un error oculto se hace visible y enfocable; el estado de guardado describe la versión real del formulario.
- Crear/quitar activos mantiene sus confirmaciones y referencias. Los IDs no cambian por renombrar una etiqueta.
- El modelo guardado y la versión ejecutable siguen siendo conceptos distintos.
- Mover un elemento del diagrama sin cambiar topología física conserva la semántica actual de validación; las pruebas existentes aplicables siguen pasando.

Revisar posteriormente extracciones pequeñas de componentes si reducen duplicación. No refactorizar todo el editor antes de demostrar el primer comportamiento.

## Resolución

- Responsable: Codex. Inicio y entrega para revisión: 2026-09-12.
- Estado: In Review; aceptación de producto pendiente.
- PR/commit: `feat(ux): add progressive model editing and protect unsaved changes`,
  sobre `9c24c1b`, solicitado por el usuario. Sin PR nueva.
- Implementación: selector de componentes, campos por propósito, opciones
  técnicas desplegables, conservación del documento completo, errores enlazados
  con foco, estados de guardado y protección de Atrás/Adelante. Se conserva el
  acceso a hidráulica v3 y a preview/validación/promoción.
- Fronteras: el usuario confirmó «Confirmo F1 y F2 para UX-002» antes de la
  primera prueba. F3 solo regresiones existentes, sin cambios de contrato.
- TDD: ocho ciclos RED → GREEN y una prueba complementaria de respuesta tardía;
  [registro y resultados](../evidencia/ux-002/README.md).
- Validación: 201 pruebas frontend, 17 navegador y 25 API aprobadas. TypeScript,
  ESLint, build y formato del frontend modificado pasan. El chequeo global falla
  por formato previo en 23 archivos sin modificar; no se cuenta como aprobado.
- Paridad: guardar/persistir, red y cuatro tecnologías, campos avanzados,
  hidráulica v3 y generación/validación/promoción comprobadas en las fronteras
  descritas en la evidencia. No cambia el significado de IDs, revisiones ni
  versiones inmutables.
- Presentación: cinco capturas revisadas a 1440, 1280, 320 y ampliación CSS al
  200 %; teclado, foco y axe sin serious/critical en la vista comprobada.
- Documentación: guía del analista, manual completo, estrategia, validación y
  tracker actualizados. Capturas locales regenerables excluidas de Git.
- Límites: sin Julia real, PostgreSQL, suite Python completa, lectores de pantalla
  ni estudio con participantes. No hay revisión/aceptación externa registrada.
