# MESA-008 · Ejecución de red hidráulica desde la mesa

Estado: Done. Fecha: 2026-10-21. Responsable: Codex.
Interfaces confirmadas: S1 navegador y S2 HTTP. Sin cambios de motor.

## Ciclos observados

1. S2, red mínima con worker real y recuperación: la nueva ruta de preview
   devolvía 404. Se incorpora el recorrido hidráulico basado en una versión v3
   explícita. El primer intento de Julia quedó bloqueado por `longpath: Acceso
   denegado` en el sandbox ([log](julia-sandbox.txt)); no cuenta como rojo
   funcional. La ejecución se repite con permisos ampliados.

   Verde: run real exitoso, 30 MW y 9.7336 hm³ leídos por HTTP, recuperado desde
   otra conexión SQLite. [Log](cycle01-green.txt).
2. S2, reintento tras reconectar: rojo por run 2 en lugar de 1; verde guardando
   clave, actor y hash en el linaje. Una clave con otro cuerpo devuelve 409.
   [Rojo](cycle02-red.txt), [verde](cycle02-green.txt).
3. S2, CMg editado: rojo 201 con preparación anterior; verde 409, sin snapshot
   adicional y con el snapshot previo intacto. El reintento original sigue
   devolviendo su run. [Rojo](cycle03-red.txt), [verde](cycle03-green.txt).
4. S2, CMg editado mientras corre el validador externo: rojo 201; verde 409
   releyendo bajo transacción antes de guardar. La prueba controla el proceso
   externo, edita por HTTP desde otra conexión y observa versiones/runs por API.
   [Rojo](cycle04-red.txt), [verde](cycle04-green.txt).
5. S2, diagrama promovido junto al snapshot: rojo 404 al consultar el diagrama
   del run; verde conservando layout, caso fuente, opciones y procedencia sin
   variante ficticia. [Rojo](cycle05-red.txt), [verde](cycle05-green.txt).
6. S2, selector de fuentes con identidad y cobertura: rojo 404; verde con los
   seis componentes de la red, IDs, rango UTC y valores terminales originales.
   [Rojo](cycle06-red.txt), [verde](cycle06-green.txt).
7. S1, ejecución completa en navegador: rojo por ausencia de «Preparar ejecución
   hidráulica». Verde con Julia real, doble clic, recarga, potencia/volumen por
   entidad y accesibilidad. [Rojo](cycle07-red.txt), [verde](cycle07-green.txt).
8. S2, consultar la corrida por versión desde otra variante del mismo caso:
   rojo 404; verde sin inventar un binding de variante para la fuente promovida.
   [Rojo](cycle08-red.txt), [verde](cycle08-green.txt).
9. S1, preparación móvil y revalidación: las opciones y el conflicto 409 ya
   se comportaban correctamente, pero Axe detectó que la tabla con desplazamiento
   no admitía foco. Verde al hacerla accesible por teclado, comprobando flecha
   derecha y ausencia de errores Axe. [Rojo](cycle09-red.txt), [verde](cycle09-green.txt).

La fixture tiene un embalse, una central y una unidad, dos aportes de 2 y 4 m³/s,
precios de 10 y 90 USD/MWh y períodos de una hora. A resolución de dos horas se
obtienen 3 m³/s y 50 USD/MWh. Con potencia máxima de 30 MW y 40 m³/s, el volumen
final sin vertimiento es 9.7336 hm³ y la energía 60 MWh. Un valor terminal de
1 USD/hm³ selecciona esa solución. El primer intento con valor cero permitía
verter el agua restante sin cambiar el óptimo económico; se corrigió la fixture,
no el solver, para evitar exigir un volumen arbitrario de una solución degenerada.

## Alcance

Se conserva el trabajo local previo de MESA-001–007, las referencias originales
y los contratos aceptados. La red v3 se ejecuta por su preparación propia;
no se introduce cooptimización con BESS ni se atribuye una variante ficticia
a la fuente versionada. Las ediciones actuales y la versión promovida son
contextos distintos y deben identificarse en la interfaz.

## Contrato y revisión técnica

`GET /api/scenarios/{scenario_id}/mesa/hydraulic-execution/sources?case_id=…`
lista versiones v3 del escenario, componentes del documento congelado, rango
UTC, resolución original, gap y valores terminales. El usuario elige una fuente
explícitamente. Los IDs se interpretan dentro de esa versión, no por nombre.

`POST .../preview` reutiliza `prepare_hydraulic_simulation` y el validador Julia.
Devuelve huella, muestra de hasta doce intervalos y linaje. La interfaz muestra
cobertura comprobada, agregación por promedio ponderado de aportes/CMg, máximo
de caudales mínimos y conservación del valor al refinar pasos. Usa fechas UTC
y fin exclusivo; no adopta la restricción eléctrica de intervalos idénticos.

`POST .../runs` exige huella y clave de solicitud. Valida fuera del bloqueo de
escritura y vuelve a preparar bajo transacción antes de persistir versión,
diagrama y run juntos. El parámetro opcional `commit=False` del guardado de
snapshot permite esa composición; el flujo anterior conserva `commit=True`.
No cambia el esquema ni se crea una tabla hidráulica nueva.

La clave, actor y hash del cuerpo quedan en el linaje del run. SQLite usa la
transacción inmediata existente; PostgreSQL bloquea el escenario para serializar
reintentos y las fuentes del proyecto durante la última comprobación. La prueba
de dos conexiones SQLite confirma un único run y snapshot. PostgreSQL no está
configurado en este entorno; no se afirma validación de concurrencia en ese backend.

`GET .../hydraulic-execution?case_id=…` recupera el último run hidráulico de mesa
del caso con progreso del worker. La UI conserva esa referencia al desconectar,
permite reintentar, muestra el período y la fuente ejecutados, y solo ofrece
resultados tras éxito. Seleccionar otra variante visual no asigna sus bindings
a un run que procede de una versión promovida. La compatibilidad de entidades
y topología sigue siendo la de MESA-005; la comparación histórica ampliada
pertenece a MESA-010.

Pruebas complementarias: objetivo/precio/agua/gap/cobertura inválidos,
aislamiento de escenario/caso/CMg, CSRF y rol externo, concurrencia, opciones
de formulario, pérdida de conexión y fallo sin resultados. Los errores reales
del validador para conexión inválida y bombeo no soportado identifican `unit_1`
([log](topology-validation.txt)). Los estados transitorios de navegador sustituyen
solo HTTP; el recorrido de éxito sí usa el motor real.

La cola sigue siendo `LocalRunQueue`; esta entrega recupera el estado al recargar
el navegador y no añade una cola duradera para reinicios del servidor. Los runs
y resultados actuales se preservan. No hay despliegue ni publicación externa.

## Comandos de verificación

Desde la raíz:

```powershell
.venv/Scripts/python.exe -m unittest -v tests.test_mesa_hydraulic_execution tests.test_hydraulic_simulation tests.test_mesa_hydraulic tests.test_optimization_mesa tests.test_mesa_preferences tests.test_mesa_editing tests.test_hydraulic_diagram tests.test_run_progress tests.test_react_auth tests.test_configuration_layer_access
```

Desde `frontend`:

```powershell
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run build
npx.cmd playwright test --config=playwright.mesa.config.ts
npx.cmd playwright test e2e/react-foundation.spec.ts -g "React auth handles|React analyst workspace|UX-005|UX-006|React hydraulic diagram persists"
npm.cmd test -- --maxWorkers=1 --reporter=verbose
npm.cmd run check
npx.cmd prettier --check src/MesaHydraulicExecution.tsx src/OptimizationMesa.tsx src/optimizationMesa.css e2e/mesa-hydraulic-execution.spec.ts playwright.mesa.config.ts src/api/schema.ts openapi.json
```

## Revisión visual

- [Preparación 1440 px](mesa-red-preparacion-1440.png): opciones, procedencia y
  vista previa con agregación de 2/4 a 3 m³/s y 10/90 a 50 USD/MWh.
- [Resultados 1440×900](mesa-red-resultados-1440.png): corrida completada,
  potencia y volumen por entidad, controles plegados para conservar los paneles.
- [Resultados 390 px](mesa-red-resultados-390.png): disposición vertical,
  procedencia legible y sin desplazamiento horizontal global.
- [Preparación 390 px](mesa-red-preparacion-390.png): formulario vertical y
  desplazamiento local de tabla con foco visible y teclado.

Chromium de Playwright, DPR 1, idioma en-US, America/Santiago, tema claro y
movimiento reducido. La fuente de ejecución se presenta en UTC para hacer
explícitos los instantes del preparador hidráulico existente. La captura móvil
de preparación usa una respuesta HTTP de presentación; las otras tres proceden
del recorrido real con Julia. Los PNG/HTML de referencia permanecen intactos.
Estas capturas no establecen la aceptación humana ni baselines de MESA-014.

## Resultado final y cierre

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| API, mesa, hidráulica, snapshots, progreso y permisos | 145/145 OK; once pruebas nuevas | [Log](api-final.txt) |
| Navegador MESA | 26/26 OK; tres pruebas nuevas | [Log](playwright-final.txt) |
| Autenticación, workspace, diagrama, UX-005 y UX-006 | 5/5 OK | [Log](playwright-regression.txt) |
| React/Vitest | 336/336 OK, 37 archivos | [Log](vitest-final.txt) |
| OpenAPI y tipos generados | OK | [Log](api-schema-final.txt) |
| Build de producción | OK; advertencia existente de chunks mayores de 500 kB | `npm.cmd run build`, dos ejecuciones durante el ciclo S1 |
| TypeScript y ESLint | OK; check global falla después por 16 archivos preexistentes con formato pendiente | [Log](check-final.txt) |
| Formato de archivos de esta entrega | OK | [Log](format-final.txt) |
| Revalidación, opciones, teclado y captura móvil final | OK tras corregir la fixture visual para reflejar un intervalo en el rango de una hora | [Log](browser-options-final.txt) |
| Documentos, tracker, dependencias y referencias | Verificados al cerrar | [Log](docs-final.txt) |

La comprobación de formato global señala exactamente los mismos dieciséis
archivos de MESA-007; se verificó que no tienen cambios respecto de HEAD. No se
presenta ese check como completamente verde. La suite Vitest completa sí pasó
esta vez sin reintentos. Los tests de estado visual y fallo controlado sustituyen
HTTP; el test principal de navegador, la prueba HTTP de red y las regresiones
económicas ejecutan Julia real.

Revisión técnica AFK completada: permisos, identidad de fuente, revalidación
antes/después del proceso externo, atomicidad, reintentos concurrentes, fuente
congelada sin variante ficticia, compatibilidad del flujo anterior y capturas.
MESA-008 pasa de In Review a **Done**. MESA-009 queda como siguiente entrega,
sin iniciarla en este cambio. Se conservaron los cambios locales anteriores.
