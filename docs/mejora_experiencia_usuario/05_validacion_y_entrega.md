# Validación, medición y entrega

## Evidencia posterior: UX-000

La [línea base del 2026-09-12](evidencia/ux-000/README.md) registra la base `428b6ad`, cinco identidades en SQLite aislado, estado C6 separado de lectura canónica, siete recorridos automatizados, 17 capturas y **86 pruebas existentes aprobadas** (62 componentes, 6 navegador, 18 Python). Incluye límites del servidor smoke, errores corregidos en el registrador y comandos para repetir la tarea. No es un estudio con participantes ni una prueba de Julia real. UX-000 quedó Done tras confirmar el usuario las fronteras F1/F2 y F3 condicional para UX-001 el 2026-09-12.

## Evidencia posterior: UX-001

La [implementación sobre `aeeb22e`](evidencia/ux-001/README.md) queda In Review con navegación por tareas, secciones contextuales, continuidad del modelo y foco al destino. Se registran siete ciclos RED → GREEN, **197 pruebas funcionales aprobadas** (166 componentes, 13 navegador, 18 API), siete capturas y paridad de las capacidades afectadas.

TypeScript, ESLint, formato de los archivos de código cambiados y `git diff --check` pasan. `npm.cmd run check` **no pasa** porque Prettier detecta 25 archivos previos sin modificaciones, enumerados en la evidencia. La comprobación visual cubre 1440 × 900, 1280 × 720, 320 × 900 y ampliación CSS al 200 %; axe sin serious/critical en las nuevas vistas comprobadas. No equivale a una auditoría con lectores de pantalla ni a validación de usabilidad con participantes. No se modificó backend y no se ejecutó Julia/PostgreSQL ni toda la suite Python.

## Evidencia posterior: UX-005

La [implementación sobre `e4eec65`](evidencia/ux-005/README.md) queda In Review. Se separan confirmar fuentes, revisar preparación y ejecutar; el servidor expone capacidades según C6 y fuentes exactas. Los ciclos F2/F3 cubren necesidades y modelo faltantes, período conservado, revisión invalidada, aceptación parcial, conflicto, doble clic y envío incierto. F1 comprueba el recorrido completo con persistencia tras recarga y una sola corrida aceptada.

Resultado: **250 pruebas funcionales aprobadas** (179 componentes, 14 navegador y 57 Python). Se omiten 13 pruebas PostgreSQL por falta de configuración dedicada. TypeScript, ESLint, build, contrato OpenAPI, formato del código frontend modificado y `git diff --check` pasan. `npm.cmd run check` falla en Prettier por 24 archivos previos no modificados; lista y salida en la evidencia. La comprobación visual incluye 1440, 1280 y 320 píxeles, ampliación CSS al 200 %, teclado y axe sin serious/critical en la vista comprobada. No se ejecutó Julia real porque no cambian generación, materialización ni lógica matemática; se usan sus validadores existentes para revisar cobertura. No es una prueba con participantes ni una auditoría completa de accesibilidad.

## Evidencia posterior: UX-006

La [implementación sobre `61dc87a`](evidencia/ux-006/README.md) queda In Review:
resultados antes de auditoría, diagnóstico accesible, tablas paginadas,
recuperación de consultas y comparación con base en el enlace, unidades y
advertencia de períodos diferentes. F1/F2 se confirmaron antes de las pruebas.

Resultado: **273 pruebas funcionales aprobadas** (195 componentes, 15 navegador,
63 Python), sin duplicar la línea base ni las repeticiones focalizadas.
TypeScript, ESLint, build y formato del frontend modificado pasan. El chequeo
global falla en Prettier por 23 archivos previos no modificados. Las capturas
locales regenerables comprueban resultado, fallo y comparación; resultado a
1280×720, 1440×900, 320×900 y ampliación CSS al 200 %, comparación a 1280 y 320.
Axe no detecta serious/critical en resultado, comparación ni diagnóstico; el
teclado abre y enfoca el diagnóstico. La suite conserva Plotly, descargas,
publicaciones y revocación del portal. No se cambian contratos de producción
ni se ejecuta Julia real, PostgreSQL o toda la suite Python. Las ejecuciones
indexadas del servidor smoke son sintéticas; no validan resultados matemáticos.

## Evidencia histórica de la revisión del plan

El 2026-09-12 se ejecutó desde `frontend/`:

```powershell
npm.cmd test -- src/ApplicationRoots.test.tsx src/GlobalCatalog.test.tsx src/ProtectedMutationJourney.test.tsx src/OperatorConsole.test.tsx src/PortalResults.test.tsx
```

Resultado: **5 archivos y 78 pruebas aprobadas**, duración reportada de 55,87 s. La invocación inicial con `npm` fue rechazada por la política local de PowerShell para `npm.ps1`; se usó `npm.cmd` sin cambiar esa política.

Es una muestra de regresión de componentes, no la suite completa. No se ejecutaron en esta revisión Playwright, Python, PostgreSQL ni Julia. Tampoco se recorrió la interfaz en un navegador ni se midió usabilidad. El plan no afirma que todas las funciones o todos los tamaños de pantalla hayan sido comprobados hoy.

Se verificaron los enlaces relativos de los 16 archivos Markdown iniciales del paquete, sin destinos faltantes. Después se añadió el [tracker de resolución](issues/tracker_ux.md), con lo que el paquete contiene 17 archivos Markdown. Los dos manuales que ya tenían modificaciones locales permanecen fuera de las modificaciones de contenido de este plan y se incluyen en un commit de documentación separado, solicitado por el usuario.

## Línea base antes de implementar

Realizar UX-000 en una instalación de prueba con el estado TS-7 anotado. Registrar versión, navegador, viewport, zona horaria, rol, datos de ejemplo, tarea, tiempo, ayuda requerida, errores y capacidad de recuperación. No medir tiempo de cálculo del solver como si fuera tiempo perdido navegando.

| Tarea repetible | Inicio y final de medición | Qué observar |
| --- | --- | --- |
| Retomar un escenario preparado parcialmente | Abrir proyecto → localizar la tarea pendiente correcta | Desvíos, pantallas consultadas, ayuda |
| Importar y vincular dos señales | Archivo disponible → revisión/fuente visible en la necesidad del modelo | Reintentos, errores de columnas/unidades y comprensión del destino |
| Ejecutar una variante | Escenario preparado → corrida aceptada por API | Decisiones manuales, promociones innecesarias, doble clic y errores |
| Recuperar una variante desactualizada | Mostrar cambio de fuente → preparación válida o rechazo entendido | Si identifica causa, acción y efecto en históricos |
| Interpretar y comparar | Abrir resultado → explicar KPI y diferencia contra otra corrida | Búsqueda de datos, confusión de unidades y rango |
| Entregar informe | Corrida exitosa → preview comprobado y publicación explícita | Si distingue borrador, preview y publicación |
| Operar con cambios de parámetros | Abrir consola → ejecutar valores guardados | Si identifica pendientes y bloqueos; no requiere vocabulario interno |

Metas iniciales propuestas, a ajustar con la línea base: al menos 4 de 5 analistas completan la tarea principal sin ayuda; reducir un 25 % la mediana del tiempo de interacción para ejecutar un caso ya preparado; cero cambios perdidos y cero ejecuciones aceptadas con precondiciones inválidas en la batería de aceptación. Los porcentajes son objetivos de producto, no hallazgos ni garantías estadísticas. Si no hay cinco participantes, registrar evidencia exploratoria sin presentar porcentajes como validación concluyente.

Usar datos equivalentes, alternar el orden antes/después cuando sea posible y registrar familiaridad del participante. La reducción de clics es secundaria: una confirmación de impacto necesaria no se elimina para mejorar una métrica.

## Verificación por ticket

1. Confirmar las fronteras necesarias y ejecutar una prueba RED del comportamiento nuevo.
2. Implementar GREEN y correr la prueba focalizada más la regresión de capacidades tocadas de la matriz.
3. Verificar teclado y foco, estados vacío/cargando/error/conflicto, recarga y navegación atrás/adelante.
4. Revisar en navegador las pantallas modificadas a 1440×900 y 1280×720; probar formularios a 320 píxeles CSS y zoom elevado. Tablas/diagramas mantienen navegación y scroll propios.
5. Si se toca una superficie externa, probar permisos por API, revocación y ausencia de vocabulario/datos internos en respuesta y UI.
6. Registrar capturas o trazas con datos de prueba, comandos, resultado y límites. Marcar únicamente los criterios efectivamente comprobados.

## Puerta de integración de una entrega

Tras integrar los tickets incluidos, desde `frontend/`:

```powershell
npm.cmd run check
npm.cmd test
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser
```

`test:browser` compila y levanta el servidor aislado en 8123; `scripts/run_react_smoke_app.py` crea un almacén SQLite en memoria y escribe sus artefactos en `.tmp/react-smoke-artifacts`. La variable evita depender de PostgreSQL durante el import de `app.main`. Si faltan dependencias o Chromium, instalar mediante los comandos documentados del repo antes de verificar. No apuntar las pruebas al servidor de uso habitual; restaurar las variables de la sesión al terminar.

Para cambios de API/persistencia, ejecutar las suites Python afectadas. Antes de cerrar una entrega transversal, ampliar a la suite de aceptación apropiada o completa desde la raíz, según el alcance:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Si se modifican transacciones, constraints o corte canónico, verificar además en un PostgreSQL de prueba explícitamente dedicado mediante el mecanismo de configuración de sus tests; una omisión por falta de servidor no cuenta como prueba aprobada.

Si cambia el contrato/generación/materialización del caso o cualquier lógica matemática:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

No exigir Julia para un cambio exclusivamente de etiquetas/layout. No repetir suites completas después de que pasen si no hubo cambios, fallos o riesgos nuevos. La auditoría axe actual cubre una muestra de páginas y filtra impactos serious/critical; ampliarla sobre las nuevas interacciones no certifica por sí sola toda la accesibilidad.

## Entrega gradual y reversión

- Una PR por ticket o por subconjunto vertical coherente del ticket. Describir problema, comportamiento final, filas de paridad, pruebas y riesgos.
- Primero integrar orientación, preparación y resultado. Después introducir editores/importación/configuración con revisión de sus propios recorridos.
- Mantener las URLs soportadas y el backend compatible. Preferir reorganizar rutas existentes; añadir redirects solo cuando se necesiten y probar links directos.
- No usar un nuevo flag visual para decidir permisos, C6 o escritor de datos. Si un cambio exige contrato nuevo, hacerlo aditivo y desplegar el backend compatible antes de la UI que lo usa.
- Como el plan no requiere migración de datos, la reversión habitual es restaurar el frontend anterior conservando APIs y registros creados legítimamente. No borrar corridas, revisiones ni publicaciones para revertir una presentación.
- Si un ticket termina necesitando migración, detener ese supuesto del plan y documentar una decisión específica con compatibilidad y reversión antes de incluirla.
- Actualizar los tutoriales al comportamiento finalmente aceptado, incorporando los cambios locales del autor. No reemplazar los manuales completos por una guía corta que elimine funciones avanzadas.

## Definición de terminado

La entrega termina cuando sus tareas se completan desde la interfaz sin ayuda no prevista, todas las capacidades afectadas tienen acceso comprobado, las garantías del backend permanecen, los cambios pendientes y conflictos son recuperables, las pruebas aplicables pasan y la revisión visual está registrada. Cualquier prueba omitida queda identificada con su motivo y consecuencia. Los tickets fuera de la entrega conservan estado pendiente.
