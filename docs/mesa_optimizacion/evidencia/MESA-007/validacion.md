# MESA-007 · Ejecución eléctrica desde la mesa

Estado: Done. Fecha: 2026-10-20. Responsable: Codex.
Interfaces confirmadas: S1 navegador y S2 HTTP. El motor y su formato no cambian.

## Recorrido implementado

La mesa permite editar y guardar una entrada, abrir «Preparar ejecución eléctrica»,
seleccionar inicio, fin exclusivo, zona y resolución, validar y ejecutar v1/v2.
La preparación usa las variantes, fuentes canónicas o anteriores y validadores
existentes. El worker y el panel de progreso son los del producto.

La zona debe coincidir con la de las fuentes y la resolución con todos sus
intervalos. Se comprueban cobertura exacta, huecos, límites y compatibilidad,
sin remuestreo. Los controles usan fecha y hora con fin explícitamente exclusivo;
no hay una fecha final inclusiva que convertir ni un límite ficticio de siete días.
Se rechazan zonas desconocidas y horas locales inexistentes o ambiguas; los
timestamps con offset se interpretan como instantes, sin reemplazar su offset.

`POST /api/scenarios/{scenario_id}/mesa/execution/preview` valida el documento
con Julia y devuelve la huella, rango normalizado, número de intervalos y linaje.
`POST .../runs` exige esa huella y una clave de solicitud. Comprueba el contexto,
materializa y valida; vuelve a materializar bajo la transacción antes de guardar.
Un cambio durante la validación produce 409 sin snapshot ni run nuevo.

Snapshot y run se confirman juntos reutilizando `create_scenario_version` y
`create_run`, con confirmación diferida solo dentro de esta unidad atómica.
Las llamadas anteriores conservan su comportamiento. La validación Julia ocurre
fuera del bloqueo de escritura. SQLite usa `BEGIN IMMEDIATE`; PostgreSQL conserva
el bloqueo de variante y entradas del materializador existente.

La clave de solicitud, actor y hash del cuerpo se guardan en el linaje del run.
Un reintento devuelve el mismo identificador aun después de abrir otra conexión
o de editar las entradas. La misma clave con otro cuerpo produce 409. Dos
conexiones SQLite enviando simultáneamente la misma solicitud crean un solo run.
No se crea otra cola, tabla, migración ni historial de resultados.

`GET .../execution?case_id=…&variant_id=…` recupera el último run de ejecución
desde esta mesa y su progreso real, incluidos éxito y fallo. La UI conserva el
run durante una desconexión, permite reconectar, muestra etapas/log y recupera
el mismo run al recargar. En éxito permite consultar sus salidas en la mesa;
en fallo conserva las entradas y ofrece revisar y volver a validar. El período
congelado se muestra junto al avance y no se reconstruye desde el formulario.

Los controles de preparación se invalidan al cambiar fechas o guardar entradas;
una edición abierta impide ejecutar. El servidor solo acepta entradas guardadas
referenciadas por la preparación, nunca un cuerpo con valores locales arbitrarios.
Los permisos internos, CSRF y aislamiento escenario/caso/variante se mantienen.

## Ciclos rojo → verde observados

| Ciclo | Conducta | Rojo observado | Verde |
| --- | --- | --- | --- |
| 1 · S2 | Preparar, ejecutar y recuperar desde otra conexión | Preview 404. | Run en cola recuperable, variante, cuatro bindings y demanda `[10, 12]` congelados. |
| 2 · S2 | Reintentar tras reconectar | Segundo envío devolvía run 2 en vez de 1. | Mismo run y una sola fila observable en el listado HTTP. |
| 3 · S2 | Huella exacta | Aceptaba una huella de 64 ceros con 201. | 409; no crea run. |
| 4 · S2 | Editar, revalidar y ejecutar | La revisión local fallaba por hash y formato temporal. | Snapshot con demanda `[10, 15]` y los instantes originales. |
| 5 · S2 | Resolución compatible | Aceptaba 2 h para entradas de 1 h. | 400 explícito, sin remuestreo. |
| 6 · S2 | Timestamps equivalentes con offset | Trataba 03:00 UTC como 03:00 Santiago y fallaba cobertura. | Normaliza a 00:00 Santiago y conserva el instante. |
| 7 · S2 | Hora inexistente por DST | Daba un error genérico de cobertura. | Explica que 2026-09-06 00:00 no existe en America/Santiago. |
| 8 · S2 | Zona del modelo | Aceptaba etiquetar la grilla local con UTC. | Rechazo explícito con la zona de la fuente. |
| 9 · S1 | Preparar y ejecutar en la mesa | No existía «Preparar ejecución eléctrica». | Recorrido con worker/Julia real, doble clic, recarga y resultados. |
| 10 · S2 | Contrato de red hidráulica | Informaba solo que faltaba un binding. | La ruta eléctrica explica que requiere v1/v2; v3 conserva su camino propio. |
| 11 · S1 | Geometría de cuatro paneles | Segunda fila terminaba en 938.64 px y se ocultaba un pie hidráulico. | Preparación compacta junto al contexto; ambas filas dentro de 900 px y pies visibles. |
| 12 · S1 | Período recuperado | El avance no mostraba el rango del run. | Rango, zona y resolución congelados visibles junto al log. |
| 13 · S2 | Variante del catálogo anterior | Preview rechazaba parámetros cambiados como obsoletos sin revalidarlos. | Revalidación canónica existente desde la mesa y ejecución de la preparación nueva. |

La prueba de entrada cambiada ya rechazaba inicialmente por una incompatibilidad
de hash; no se cuenta como otro rojo. Tras corregir esa incompatibilidad sigue
rechazando por la huella obsoleta. Se añadieron verificaciones de permisos,
concurrencia, snapshot histórico, cambio durante validación, desconexión,
invalidez del formulario y fallo real sin atribuirles ciclos rojos inexistentes.

## Correcciones necesarias en la base

La publicación de series específicas devuelve `sha256:<digest>` en su vínculo,
mientras la revisión canónica expone el digest sin prefijo. La materialización
ahora compara ambos formatos normalizados y sigue recalculando el hash completo
para detectar corrupción.

Las revisiones canónicas almacenan timestamps sin offset como UTC. Se adaptan
explícitamente a la zona de la revisión antes de generar las horas locales que
usa el contrato ejecutable existente. La cobertura se compara por instantes;
no por orden lexicográfico de strings. La preparación de variantes reutiliza el
mismo adaptador. Las regresiones anteriores de TS-3 y TS7-009 permanecen cubiertas.

## Evidencia de ejecución real

La prueba HTTP edita la segunda demanda de 12 a 15 MW, valida con Julia,
encola mediante `LocalRunQueue` y espera el resultado del `JuliaRunExecutor`.
El solver finaliza `OPTIMAL`; la API de mesa devuelve las dos muestras de salida
BESS con el mismo run. La prueba de navegador repite editar → guardar → validar
→ doble clic → recargar → completar → consultar sin salir de la mesa.

Otro caso real guarda demanda `[10, 100]`, superior a la capacidad disponible.
El worker termina fallido, conserva el run y su explicación, no ofrece salidas
y la mesa mantiene la entrada guardada. [Verificación focalizada](worker-failure.txt).

La primera ejecución con Julia dentro del sandbox falló por acceso denegado al
entorno instalado (`longpath`). Se repitió fuera del sandbox con autorización
automática y datos temporales. Ese fallo de infraestructura no es un rojo TDD.
Los tests de estados transitorios y de invalidación del formulario sustituyen
solo HTTP en el navegador; no se usan como prueba de exactitud del solver.

## Comprobaciones finales

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| API, variantes, mesa, worker y permisos | 156 descubiertas: 151 OK, cinco PostgreSQL omitidas | [Log](api-final.txt) |
| Navegador MESA completo | 23 OK; tres pruebas nuevas | [Log](playwright-final.txt) |
| Autenticación, workspace, hidráulica, UX-005 y UX-006 | 5 OK | [Log](playwright-regression.txt) |
| React/Vitest | 335/336 en suite; archivo de foco 4/4 al repetir sin cambios. 336 distintas verificadas entre ambas ejecuciones | [Suite](vitest-final.txt), [reintento](vitest-retry.txt) |
| OpenAPI y tipos | OK | [Log](api-schema-final.txt) |
| Build | OK; advertencia existente de chunks mayores de 500 kB | [Log](build-final.txt) |
| TypeScript y ESLint | OK; check global falla después por formato previo de 16 archivos ajenos | [Log](check-final.txt) |
| Prettier de archivos de la entrega | OK | [Log](format-final.txt) |
| Documentos y referencias | Enlaces, tickets, dependencias y hashes verificados al cerrar | [Log](docs-final.txt) |

El [primer intento Vitest](vitest-initial.txt) se interrumpió antes de completar,
sin resultados parciales del reporter. `RunProgress.test.tsx` pasó 3/3. Se repitió
la suite con el capturador de MESA-006: tardó 269.89 s y pasó 335/336. Falló la
aserción de foco de `ReportExperience.test.tsx`, exactamente la incidencia registrada
en MESA-005. Repetir ese archivo sin cambios pasó 4/4. No se presenta la suite
completa como verde ni se modifican las pruebas ajenas para ocultar ese resultado.

Comandos desde la raíz:

```powershell
.venv/Scripts/python.exe -m unittest -v tests.test_mesa_execution tests.test_mesa_editing tests.test_optimization_mesa tests.test_mesa_hydraulic tests.test_mesa_preferences tests.test_input_variants tests.test_ts3_input_variants tests.test_ts3_case_variant_api tests.test_ts7_009_run_materialization tests.test_run_progress tests.test_manual_runs tests.test_react_auth tests.test_configuration_layer_access
```

Desde `frontend`:

```powershell
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run build
npx.cmd playwright test --config=playwright.mesa.config.ts
npx.cmd playwright test e2e/react-foundation.spec.ts -g "React auth handles|React analyst workspace|UX-005|UX-006|React hydraulic diagram persists"
npm.cmd test -- --maxWorkers=1
npm.cmd test -- src/RunProgress.test.tsx --maxWorkers=1
npm.cmd test -- --maxWorkers=1 --reporter=verbose
npm.cmd test -- src/ReportExperience.test.tsx --maxWorkers=1 --reporter=verbose
npm.cmd run check
npx.cmd prettier --check src/MesaExecution.tsx src/OptimizationMesa.tsx src/optimizationMesa.css e2e/optimization-mesa.spec.ts src/api/schema.ts openapi.json
```

Capturas inspeccionadas:

- [Preparación validada y entrada editada, 1440×900](mesa-ejecucion-1440.png).
- [Run completado y selección recuperada, 390 px](mesa-ejecucion-390.png).
- [Matriz 2×2 con preparación plegada, 1440×900](mesa-paneles-1440.png).

Chromium de Playwright, DPR 1, en-US, America/Santiago, tema claro y movimiento
reducido. La preparación se despliega para mostrar rango y validación, y se
pliega junto al contexto para mantener los cuatro paneles visibles. El log
también se despliega bajo demanda. Las capturas conservan la cabecera del producto
y datos de fixture de dos intervalos; no imitan las cifras ficticias del prototipo.
Geometría, ausencia de desbordamiento móvil, teclado y Axe quedan verificadas.

## Límites y revisión

PostgreSQL no está configurado en este entorno; no se afirma haber validado su
concurrencia. SQLite en disco sí se prueba con conexiones independientes.
La reanudación de un worker tras reiniciar el servidor no forma parte del
recorrido de recarga/reconexión del navegador ni añade una cola duradera.

Se conserva el contrato de horas locales del motor: no se convierten zonas entre
fuentes ni se remuestrean resoluciones para hacerlas compatibles. Las reglas
activas mantienen el bloqueo del dominio para impedir ejecutarlas sin compilar;
su recorrido especializado sigue disponible fuera de esta mesa. La red v3 queda
para MESA-008. No hay cambios al motor, despliegue ni publicación externa.

Las capturas de referencia originales y el HTML permanecen intactos. Las nuevas
capturas validan implementación; no establecen la aceptación humana de MESA-014.

Cierre AFK: revisados permisos y CSRF, vigencia antes/después de Julia,
atomicidad, idempotencia entre conexiones, procedencia, compatibilidad temporal,
estados de ejecución y capturas. MESA-007 pasa de In Review a Done. Siguiente:
MESA-008, con sus dependencias satisfechas. Se conservan los cambios locales
previos; no se inicia la siguiente entrega ni se publica el repositorio.
