# UX-009 · Administración y acciones sensibles comprensibles

Estado: Todo. Prioridad: P2. Dependencias: UX-001. Tamaño: S.

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
