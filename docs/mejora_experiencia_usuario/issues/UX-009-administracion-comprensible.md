# UX-009 · Administración y acciones sensibles comprensibles

Estado: In Review. Prioridad: P2. Dependencias: UX-001. Tamaño: S.

Responsable: Codex. Inicio: 2026-09-14, sobre `902662a`.
F1/F2 confirmadas por el usuario antes de las pruebas nuevas.
[Acuerdo y evidencia](../evidencia/ux-009/README.md).

## Problema y resultado

Los nombres técnicos de roles/capacidades y la mezcla de administración con programación aumentan la carga de lectura. El administrador debe entender qué acceso otorga y qué efecto tendrá cada acción.

## Código y contratos

- `frontend/src/Admin.tsx`: `CreateUserForm`, accesos externos, desactivación y programación.
- `frontend/src/Workspace.tsx`: acceso por proyecto y confirmación de borrado.
- `app/auth.py`, `app/schedules.py`, endpoints de acceso y proyectos en `app/main.py`.
- Regresión: `Admin.test.tsx`, `ExternalAccess.test.tsx`, `tests/test_configuration_layer_access.py`, `tests/test_ts6_008_schedules.py`, `tests/test_ts7_024_project_purge.py`.

## Pasos de implementación

1. Mostrar nombres de roles comprensibles manteniendo `admin`, `analyst`, `external` como valores canónicos. Revisar la opción visible `client`: si es alias de compatibilidad, presentarla como la misma identidad externa en el formulario, conservando el soporte API/migración que siga siendo necesario.
2. Presentar las capacidades por proyecto como dos decisiones independientes: «Ver informes» y «Operar consolas», con explicación de alcance. No preseleccionar ambas por comodidad ni cambiar permisos existentes al guardar una etiqueta.
3. Organizar usuarios/accesos y programación en secciones distintas. Mantener todas las operaciones de schedules ya expuestas, incluidos rangos, variantes, estado y ejecución de vencidos.
4. Mostrar mensajes de efecto para revocación/desactivación y mantener confirmaciones existentes. Tras aceptación, actualizar la lista sin afirmar que se cancelaron corridas ya iniciadas.
5. Mantener borrado de proyecto accesible desde su acción contextual, con nombre del proyecto y advertencia de que elimina escenarios, versiones, corridas, series y publicaciones. No ofrecer «Deshacer» donde la API no lo garantiza ni suavizar la consecuencia real.
6. Asociar errores de formulario a campos y mantener reintento sin borrar valores. Conservar los controles de autorización del servidor; ocultar un botón no sustituye un rechazo API.

## Secuencia TDD sugerida

F1/F2; F3 si se modifica contrato/permisos:

1. RED: crear un externo con la etiqueta única de UI y reabrirlo muestra su identidad canónica. GREEN: presentación/formulario compatible, después de verificar la semántica real del alias.
2. RED: conceder solo «Ver informes» habilita portal pero no operación; cambiar la segunda capacidad no elimina la primera. GREEN: edición clara e independiente.
3. RED: revocar una capacidad en una sesión activa conserva la otra según contrato y el siguiente request rechaza la revocada. GREEN: feedback/caché, manteniendo la frontera backend.
4. Para programación y borrado sin cambio funcional, ejecutar regresiones existentes y revisión visual de acceso/confirmación. Agregar RED nuevo solo si se introduce un comportamiento observable nuevo.

## Aceptación

- No se presentan dos identidades externas ambiguas para crear un usuario nuevo.
- Solo admin puede administrar capacidades; analista/externo no ganan permisos por reorganización.
- Usuario, proyecto y capacidades efectivas quedan identificados antes de confirmar.
- Programación conserva sus operaciones y reglas; no se añade ejecución automática nueva.
- Eliminar proyecto conserva purga transaccional y confirmación; fallos no se presentan como borrado exitoso.
- Los usuarios externos no reciben diagnóstico administrativo ni detalles de programas no autorizados.

No cambiar el modelo de roles ni migrar tablas en este ticket. Cualquier conflicto con compatibilidad vigente se documenta y se resuelve con una extensión acotada del alcance antes de implementar. Revisión estructural posterior al ciclo TDD.

## Resolución

- Responsable: Codex. Inicio y entrega para revisión: 2026-09-14.
- Estado final: In Review, pendiente de aceptación del resultado.
- PR o commits: `feat(ux): clarify administration and sensitive actions`, sobre
  `902662a`, solicitado por el usuario el 2026-09-15; sin PR.
- Implementación: roles legibles con una sola identidad externa; capacidades
  independientes sin preselección, revisión explícita y efecto de revocación;
  usuarios y programación separados conservando formularios al alternar;
  errores de email/fechas vinculados al campo, reintentos y foco de teclado.
- Criterios y conservación funcional: identidad/autorización, acceso a informes,
  usuarios/capacidades, programación y eliminación de proyectos comprobados en
  [la evidencia](../evidencia/ux-009/README.md). La API ya rechazaba crear `client`;
  se conserva la migración histórica a `external + portal_view` sin cambios.
- Fronteras: «Confirmo F1 y F2 para UX-009», antes de las pruebas nuevas.
  Nueve ciclos F2 y dos fallos de layout F1 corregidos; regresiones existentes F3.
- Validación: 267 React, 23 navegador y 45 Python aprobadas; dos PostgreSQL
  omitidas. TypeScript, ESLint, build, formato de los siete archivos frontend
  modificados y diff pasan. El chequeo global falla solo por formato previo
  en 21 archivos sin modificaciones.
- Visual/accesibilidad: 14 capturas locales regenerables, 1440/1280/320 px y
  ampliación CSS 200 %, foco/teclado y axe sin serious/critical en las tres
  superficies comprobadas. Confirmaciones de desactivación y borrado revisadas.
- Revisión estructural: estados de revisión locales y HTTP como frontera;
  contratos, permisos y purga conservados. Sin refactorización ajena al alcance.
- Límites: sin Julia real, PostgreSQL, suite Python completa ni evaluación con
  participantes/lectores de pantalla. El servidor smoke usa resultados sintéticos.
- Persona que revisó/aceptó: revisión técnica local de Codex; aceptación del
  producto pendiente.
