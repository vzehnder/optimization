# REG-001: Guardar y probar una regla Python desde una unidad hidráulica

Status: Done
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

- [x] El editor contextual guarda y reabre código, parámetros con unidades y metadatos del borrador; conserva objeto, proyecto y retorno de navegación.
- [x] Guardar usa revisión esperada: dos editores no sobrescriben cambios silenciosamente. Las revisiones publicables se distinguen del borrador mutable.
- [x] El analista puede iniciar, consultar y cancelar la prueba; los estados y errores de línea aparecen en UI y API sin bloquear el servidor HTTP.
- [x] La ejecución usa CPython/SDK fijados en un contenedor efímero con la frontera y cuotas del plan, sin acceso a red, secretos, repositorio ni datos de otro trabajo.
- [x] La ausencia del runtime muestra indisponibilidad y no activa un fallback inseguro. El procedimiento de desarrollo Windows y CI usa la misma frontera Linux.
- [x] La API resuelve autorización y pertenencia del objeto; usuarios externos no pueden leer código ni crear trabajos, incluso invocando rutas directamente.
- [x] Código inválido, salida no finita, importación no admitida, exceso de salida, timeout y cancelación terminan con error acotado y limpieza del contenedor; un reinicio recupera trabajos interrumpidos.
- [x] La prueba no aplica restricciones ni modifica series; devuelve hash de código/contexto y versión de runtime para distinguir resultados obsoletos.

## Demonstration and validation

Guardar una fórmula «capacidad por disponibilidad», recargar y comprobar el
resultado. Cambiar el código a un bucle sin fin y cancelarlo; comprobar que otra
solicitud sigue funcionando. Probar aislamiento con el runtime real, permisos por
HTTP, concurrencia/persistencia en SQLite y PostgreSQL y el recorrido del editor.
No sustituir la prueba de recursos por mocks del ejecutor.

### Evidencia de implementación (2026-09-21)

Interfaces de TDD confirmadas por el usuario: HTTP autenticado con persistencia
SQLite/PostgreSQL, editor contextual y ejecutor OCI real. Se ejecutaron ciclos
rojo–verde para guardado, concurrencia, parámetros, indisponibilidad, ejecución
asíncrona, cancelación, logs, navegación, cola, revisión sellada y límites de memoria.

- `python -m unittest tests.test_reg001_rules tests.test_reg001_runtime -v`:
  **32 pruebas aprobadas, sin omisiones**, con PostgreSQL 18 temporal y Docker
  28.5.1 en Ubuntu WSL. CPython 3.12.14, SDK/política `reg-001.1`. Resultado
  observado: 80 m³/s × 0.75 = **60 m³/s**. Incluye caída real del proceso worker,
  limpieza de huérfanos, timeout, cancelación y muerte por límite de 512 MiB.
- Regresión Python de clasificación, diagrama hidráulico, autenticación,
  autorización y registro de objetos: **89 pruebas, 83 aprobadas y 6 omitidas**
  por las condiciones de esas suites. La persistencia nueva sí se probó en ambos
  motores en las 32 pruebas anteriores.
- `ComponentRules.test.tsx`: **5 pruebas** del recorrido y de resultados/errores.
- `playwright test e2e/component-rules.spec.ts`: recorrido real en Chromium
  aprobado; captura revisada visualmente. El smoke no necesita un worker activo;
  cálculo y cancelación reales se verifican en la suite HTTP/OCI.
- OpenAPI regenerado y `api:check`, TypeScript, ESLint y build verificados.
- La suite global de frontend no está íntegramente verde: una pasada dio
  287 aprobadas y 2 fallidas. El fallo de selección del panel hidráulico se
  reprodujo en una copia limpia de `HEAD`; las suites de reportes/resultados
  presentaron fallos intermitentes de foco/navegación. La pasada completa de
  `HEAD` también dio 2 fallos (panel hidráulico y un caso de resultados).
  No se cambiaron esos tests ni se registró la suite global como aprobada.
- El chequeo global de Prettier señala archivos ajenos a REG-001; los archivos
  frontend modificados por esta entrega están formateados.

Se corrigió además el orden de creación de `time_series_sets` respecto a su
foreign key hidráulica, necesario para inicializar PostgreSQL vacío, y se añadió
`dimensionless` al catálogo canónico mediante semillas aditivas. Las unidades
guardadas en el diagrama se registran para resolver su identidad contextual.

Operación, límites concretos, reproducción y configuración Windows/CI:
[runtime.md](../runtime.md). El workflow de CI está incluido; su ejecución remota
no se ha disparado desde esta sesión. Publicar/aplicar al optimizador sigue siendo
REG-002; este issue conserva borrador mutable y revisiones `sealed_preview`.

## Blocked by

None - can start immediately.
