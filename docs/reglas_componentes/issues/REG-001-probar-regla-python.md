# REG-001: Guardar y probar una regla Python desde una unidad hidráulica

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 4, 5 y 8.
User stories covered: HU-01.

## What to build

Un analista abre «Cálculos y restricciones» en una unidad hidráulica v3, escribe
una función Python con parámetros tipados, guarda un borrador y obtiene una
salida numérica de prueba. El recorrido incluye almacenamiento versionado,
editor, API autenticada, trabajo asíncrono y ejecución real en el sandbox.
El código aún no altera corridas; la UI lo indica. La prueba inicial calcula un
máximo escalar de caudal y lo muestra con unidad.

El ejecutor y la política de capacidades son parte de este recorrido, no un
servicio pendiente que se sustituya temporalmente por ejecución dentro del backend.
Solo se construye la superficie mínima necesaria para esta prueba.

## Acceptance criteria

- [ ] El editor contextual guarda y reabre código, parámetros con unidades y metadatos del borrador; conserva objeto, proyecto y retorno de navegación.
- [ ] Guardar usa revisión esperada: dos editores no sobrescriben cambios silenciosamente. Las revisiones publicables se distinguen del borrador mutable.
- [ ] El analista puede iniciar, consultar y cancelar la prueba; los estados y errores de línea aparecen en UI y API sin bloquear el servidor HTTP.
- [ ] La ejecución usa CPython/SDK fijados en un contenedor efímero con la frontera y cuotas del plan, sin acceso a red, secretos, repositorio ni datos de otro trabajo.
- [ ] La ausencia del runtime muestra indisponibilidad y no activa un fallback inseguro. El procedimiento de desarrollo Windows y CI usa la misma frontera Linux.
- [ ] La API resuelve autorización y pertenencia del objeto; usuarios externos no pueden leer código ni crear trabajos, incluso invocando rutas directamente.
- [ ] Código inválido, salida no finita, importación no admitida, exceso de salida, timeout y cancelación terminan con error acotado y limpieza del contenedor; un reinicio recupera trabajos interrumpidos.
- [ ] La prueba no aplica restricciones ni modifica series; devuelve hash de código/contexto y versión de runtime para distinguir resultados obsoletos.

## Demonstration and validation

Guardar una fórmula «capacidad por disponibilidad», recargar y comprobar el
resultado. Cambiar el código a un bucle sin fin y cancelarlo; comprobar que otra
solicitud sigue funcionando. Probar aislamiento con el runtime real, permisos por
HTTP, concurrencia/persistencia en SQLite y PostgreSQL y el recorrido del editor.
No sustituir la prueba de recursos por mocks del ejecutor.

## Blocked by

None - can start immediately.
