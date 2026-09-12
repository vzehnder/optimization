# UX-000 · Línea base reproducible y propuesta de fronteras

Fecha: 2026-09-12. Responsable: Codex. Estado: **In Review; falta confirmar las fronteras**.
Ticket: [UX-000](../../issues/UX-000-acordar-fronteras-y-linea-base.md).

Se preparó la línea base del siguiente ticket disponible, UX-000. Esta entrega incluye un servidor desechable, un registrador de recorridos, observaciones y capturas. No cambia el producto ni añade pruebas. La primera prueba RED corresponde a UX-001 después de la confirmación indicada abajo.

## Base y decisiones vigentes

- Commit inspeccionado y compilado: `428b6adf90f7c7204ff9e72585f83ee06f7162a9` (`docs(ux): add TDD implementation plan and issue tracker`). El árbol estaba limpio al iniciar; no había trabajo local ajeno que preservar. Los cambios de esta tarea están dentro de `docs/mejora_experiencia_usuario/`.
- Se leyeron los 17 Markdown originales del paquete: diagnóstico, experiencia objetivo, matriz funcional, estrategia TDD, validación, README, diez issues y tracker. No se encontraron `AGENTS.md` ni `CONTEXT.md` en el repositorio.
- [TS-1: jerarquía](../../../series_tiempo/iter1/decision_record_ts1_hierarchy.md): caso editable, versión ejecutable inmutable; layout hidráulico separado de topología física.
- [TS-3: variantes](../../../series_tiempo/iter3/decision_record_ts3_variant_semantics.md): referencias a fuentes, un default por caso, rango en la ejecución, cobertura exacta y desactualización bloqueante. Ejecutar una variante materializa la versión.
- [Arquitectura de configuración](../../../capa_configuracion/architecture_configuration_layer_final.md): raíces hermanas, capacidades independientes, autorización por request y payload externo construido con allowlist.
- [TS-7, apartados 10.10 y 11.1](../../../series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md): C6 no se infiere de la lectura canónica por identidad; escritor único y recorrido protegido vigentes.
- [TS7-024: purga de proyecto](../../../series_tiempo/iter7/decision_record_ts7_project_purge.md): única excepción explícita a la retención del historial, sin relajar la inmutabilidad de revisiones.

Archivos que deberá tocar o comprobar UX-001: `frontend/src/App.tsx` (`AnalystRoot`, `LandingRedirect`, `AuthenticatedRoutes`), `frontend/src/Workspace.tsx` (`ProjectDetailView`, `ScenarioDetailView`, breadcrumbs), `frontend/src/styles.css`, `frontend/src/DraftEditor.tsx` (entrada y protección de cambios pendientes), `frontend/src/api/client.ts` (consultas públicas ya disponibles), `ApplicationRoots.test.tsx`, `App.test.tsx` y `frontend/e2e/react-foundation.spec.ts`. No se requiere cambiar OpenAPI para el primer comportamiento.

## Entorno aislado e identidades

Windows NT `10.0.26200.0`; Node `v24.14.1`; Python `3.14.3`; Chromium `149.0.7827.55` mediante Playwright instalado en el proyecto. Recorrido final iniciado a `2026-09-12T16:10:18.433Z`, con zona de navegador `America/Santiago`.

El [servidor de referencia](serve_baseline.py) fuerza `sqlite:///:memory:` antes de importar la aplicación y entrega ese mismo almacén a `create_app`. Escucha solamente en `127.0.0.1:8124`. Los artefactos van a `.tmp/ux-000/<token>/`; cada ejecución exige una carpeta nueva. No lee ni modifica proyectos de la instalación habitual. Los E2E existentes usan su propio servidor en `8123`, con otra base en memoria.

El estado leído del almacén del servidor de referencia fue `cutover_active=false`, `status=not_started`, `migration_run_id=null`, escritura canónica y aliases deshabilitados. Se habilitó la cuenta ficticia `verification@ux.example.local` en `TS_NEXT_CANONICAL_READ_ACCOUNTS`; esto **no ejecutó C6**.

Las cinco sesiones siguientes se iniciaron mediante el formulario real; `/api/auth/me` y la URL visible quedaron registrados en [observaciones.json](observaciones.json):

| Cuenta ficticia | Rol / capacidades en el proyecto principal | Entrada indicada por backend y observada | Lectura canónica |
| --- | --- | --- | --- |
| `admin@ux.example.local` | `admin` | `/react/projects` | No |
| `analyst@ux.example.local` | `analyst` | `/react/projects` | No |
| `verification@ux.example.local` | `analyst`, cuenta de verificación | `/react/projects`; permite abrir Catálogo | Sí |
| `operator@ux.example.local` | `external`, solo `operate` | `/react/console/1` | No |
| `reader@ux.example.local` | `external`, solo `portal_view` | `/react/client` | No |

El operador recibe «No encontrado» al intentar abrir `/react/projects`. El lector abre el informe publicado desde su propia sesión. Los rechazos API y la independencia de capacidades también están cubiertos por las regresiones ejecutadas; estas capturas no sustituyen autorización de backend.

## Datos y repetición

Los preparadores reutilizan `operator_draft_document`, `create_console_price_set`, `console_document_with_scalar_parameter` y `create_indexed_run` de las pruebas existentes. No se añade un fixture de producto ni se altera el runner habitual.

| Recurso | Condición conocida al iniciar |
| --- | --- |
| Proyecto `UX-000 Planta de prueba`, escenario `Sin modelo` | Sin draft guardado, versiones ni corridas; abrir la vista puede crear la variante default de forma perezosa. |
| `Preparacion parcial` | Batería de 8 MWh, carga/descarga de 4 MW, estado inicial de 4 MWh; draft guardado sin fuentes. |
| `Operacion preparada` | Precios horarios 50, 51 y 52 USD/MWh; rango `2026-01-01T00:00:00-03:00, 2026-01-01T03:00:00-03:00)`; variante validada. |
| `Fuente modificada`, en proyecto de revisión separado | Mismo fixture de precio: primera revisión validada, luego primer valor cambiado de 50 a 999. Evita invalidar la consola del proyecto principal. |
| `Comparacion de referencia` | Dos corridas ya indexadas del fixture de comparación, mismo escenario y rango; KPIs 1000 y 1500 USD, diferencia conocida 500 USD. |
| Consola `Plan diario Planta Norte` | Variante propia validada; parámetro de carga BESS entre 0 y 4 MW; valor inicial 4; operador con `operate`. |
| CSV `ux-inputs.csv` | Dos períodos: precio 55/60 USD/MWh y demanda 2/2,5 MW; preparado a partir del ejemplo del E2E de ingestión. Se agrega el componente load por UI antes de medir la importación. |

Desde la raíz del repositorio, si no existe un build vigente:

```powershell
Push-Location frontend
npm.cmd run build
Pop-Location
```

En una primera terminal de PowerShell, usar un token nuevo en cada repetición:

```powershell
$env:UX_BASELINE_TOKEN = 'ux000-repeticion-01'
try {
    ./.venv/Scripts/python.exe docs/mejora_experiencia_usuario/evidencia/ux-000/serve_baseline.py
} finally {
    Remove-Item Env:UX_BASELINE_TOKEN
}
```

En una segunda terminal, después de que el servidor esté escuchando:

```powershell
node docs/mejora_experiencia_usuario/evidencia/ux-000/capture_baseline.mjs ux000-repeticion-01
```

El registrador comprueba que el token servido coincide antes de iniciar sesión o mutar datos. Guarda JSON y PNG bajo `.tmp/ux-000/ux000-repeticion-01/capture`. No reutilizar una base ya recorrida: la grabación importa datos, ejecuta y publica recursos ficticios. Detener la primera terminal con Ctrl+C descarta la base. Para un recorrido manual, abrir `http://127.0.0.1:8124/react` con cualquiera de las cuentas de la tabla y la contraseña exclusiva de prueba `ux-baseline-only`. No se guardan cookies, CSRF ni sesiones en la evidencia.

La grabación archivada se obtuvo con el token `baseline-20260912-e`. El servidor se detuvo al terminar la tarea. Los scripts son herramientas exploratorias de esta evidencia, no una suite nueva ni un benchmark.

## Recorridos observados

Una repetición automatizada final por tarea, a 1280×720. El autor del registrador conocía el código y consultó las pruebas existentes: **no hubo participantes humanos ni medición de tiempo de decisión**. Los milisegundos incluyen interacción automatizada y latencia local React/API; excluyen preparación de fixtures y capturas. No hubo solver Julia real. No usar estos valores para afirmar mejoras del 25 %, ausencia de necesidad de ayuda ni tasas de éxito con usuarios.

| Tarea e inicio → final de la medición | Tiempo automático | Resultado observado y evidencia |
| --- | --- | --- |
| Abrir proyecto → retomar el editor de `Preparacion parcial` | 308 ms | `grid_battery_case` recuperado; navegación Proyecto → escenario → «Abrir draft». [Captura (`capturas/01-retomar.png`). |
| Archivo preparado → importar y ver las dos necesidades vinculadas | 815 ms | Set `Precio y demanda UX`, revisión 1, valores 55/60 y 2/2,5. Los usos se guardaron mediante «Vincular y correr variante», que además creó una corrida. Captura (`capturas/02-importar.png`). |
| Abrir escenario preparado → abrir la corrida aceptada | 199 ms | Corrida 4, variante default, rango de tres horas con offset; sin promoción manual. Captura (`capturas/03-ejecutar.png`). |
| Desactualización visible → terminar revalidación | 83 ms | Motivo `time-series set 2 changed since last validation`; ejecución deshabilitada antes y habilitada después. Captura (`capturas/04-recuperar-desactualizada.png`). |
| Abrir resultado base → comparar contra segunda corrida | 1488 ms | Retorno por breadcrumb al escenario, «Comparar corridas», selección base 1/candidata 2. Fila visible `objective_value_usd: 1000 / 1500 / 500`. Captura (`capturas/05-interpretar-comparar.png`). |
| Abrir resultado → crear borrador, preview y publicar explícitamente | 950 ms | Publicación 1. Se prepararon plantilla y configuración por API fuera de la medición; se comprobaron el preview y la sesión lectora. Publicación (`capturas/06-entregar-informe.png`), portal (`capturas/09-portal.png`). |
| Abrir consola → cambiar 4 a 3 MW, guardar y ejecutar | 267 ms | «Guarda los cambios antes de ejecutar»; botón bloqueado hasta guardar. Envío aceptado HTTP 201, actor `UX operator`. Captura (`capturas/07-operar.png`). |

Las duraciones son referencias de la automatización, no umbrales para Vitest/Playwright. El JSON conserva los valores devueltos por las interfaces públicas y las URLs finales. El histórico de corridas de prueba y los PNG se conservan; no se tocó historia de trabajo.

## Errores de preparación y límites descubiertos

1. El primer armado repitió el nombre/version del fixture `Console price` dentro del mismo proyecto; el almacén rechazó el duplicado. Se separó el proyecto de la fuente desactualizada. Fue un error del preparador, anterior al recorrido.
2. Las primeras grabaciones usaron coincidencia exacta de texto en labels que incluyen un select, un enlace duplicado fuera del breadcrumb y «Despublicar» donde el producto dice «Unpublicar». Se corrigieron los localizadores del registrador. No fueron fallos de producto ni ciclos RED → GREEN.
3. El `dispatch.csv` de `SmokeRunQueue` carece de `market_value_usd`, exigido por el índice TS-4. Incluso después del rebuild público, la comparación lo rechaza por índice incompleto. La medición final reutiliza `create_indexed_run`; no se modificaron artefactos ni comportamiento de corridas para forzar una comparación. El recorrido de ejecución/portal sigue usando smoke y sus resultados sintéticos (KPI 1250,5 USD, dos filas de salida fijas aunque el rango del caso tenga tres horas). No prueba paridad temporal o corrección matemática.
4. Consulta CIM de versión de Windows denegada por el entorno; se obtuvo la versión con `System.Environment.OSVersion`. Git advirtió falta de lectura de su ignore global, pero pudo inspeccionar estado y diffs. No bloquearon las verificaciones.
5. Build con advertencia de chunk mayor de 500 kB; Python avisó de deprecación del adaptador `httpx` de Starlette. No hubo fallos en las suites seleccionadas.

Los ensayos de preparación `a` a `d` permanecen en `.tmp/ux-000/` cuando contienen artefactos; solo la repetición final `e` se archiva en esta evidencia. No se mezclan sus tiempos ni sus interrupciones con los siete resultados finales.

## Revisión visual y accesibilidad

Se capturaron proyecto y escenario a 1280×720 (`capturas/escenario-1280.png`), 1440×900 (`capturas/escenario-1440.png`) y 320×900 (`capturas/escenario-320.png`). Las capturas de proyecto están en 1280 (`capturas/proyecto-1280.png`), 1440 (`capturas/proyecto-1440.png`) y 320 (`capturas/proyecto-320.png`). También se archivaron rechazo de acceso interno (`capturas/08-operador-acceso-interno.png`), catálogo de verificación (`capturas/10-catalogo-verificacion.png`) y entrada actual al editor (`capturas/11-primer-comportamiento.png`).

Hallazgos que deberá atender la implementación:

- En `Sin modelo`, a 1280×720 aparecen selector de variante, clonación y comienzo de rango antes de explicar qué falta. La entrada al editor dice «Abrir draft».
- La navegación principal dice «Analista» y «Sistema»; el proyecto apila escenarios, series y configuración. El formulario de proyecto se reorganiza en una columna a 320 px en la captura de referencia.
- La corrida comienza con `Run state` y `Lineage`; sus KPIs quedan más abajo. La comparación usa claves como `objective_value_usd` sin una columna separada de unidades.
- El portal muestra título y KPI con `USD` en su propia superficie; la consola conserva el aviso de guardado pendiente y su bloqueo de ejecución.
- Activar «Abrir draft» con foco y Enter llega al editor del mismo escenario, pero `document.activeElement` queda en `BODY`. Es evidencia para el manejo de foco de UX-001, no una declaración de accesibilidad completa.

El E2E axe existente pasó en auth, admin, editor, resultados y portal, con su comprobación de teclado. Su filtro es serious/critical; no audita todo el producto ni certifica WCAG. No se hicieron sesiones con lectores de pantalla, zoom elevado ni auditoría exhaustiva de conflictos/pérdida de cambios. Esos controles corresponden a los tickets que modifiquen esas interacciones.

## Regresiones ejecutadas en esta base

Comandos de frontend ejecutados desde `frontend/`:

```powershell
npm.cmd test -- src/ApplicationRoots.test.tsx src/App.test.tsx
$env:DATABASE_URL = 'sqlite:///:memory:'
npm.cmd run test:browser -- --grep 'React (auth handles|analyst workspace|hydraulic diagram|client portal|admin users)'
npm.cmd exec playwright test -- --grep 'representative React pages'
```

| Comprobación | Resultado real | Alcance |
| --- | --- | --- |
| Vitest `ApplicationRoots` + `App` | 2 archivos, **62 passed**, 39,40 s | Raíces, contexto, navegación, draft, variantes, hidráulica, versiones, resultados y catálogo cubiertos por esas suites. |
| Build incluido en `test:browser` | TypeScript + Vite correctos | Se compiló el frontend existente; sin cambio de contrato. |
| Playwright `react-foundation`, cinco recorridos seleccionados | **5 passed**, 29,0 s | Auth/roles/logout/desactivación, hidráulica persistida, administración/accesos, portal/descargas/revocación y creación/recarga/atrás/adelante de proyecto/escenario. |
| Playwright accesibilidad y teclado | **1 passed**, 15,0 s | Muestra existente de cinco pantallas; mismos límites de axe descritos arriba. |

Comandos de Python ejecutados desde la raíz:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
./.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_react_foundation.py' -v
./.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_configuration_layer_access.py' -v
./.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_ts7_019_layered_catalog_surface.py' -v
```

| Suite API | Resultado real | Alcance |
| --- | --- | --- |
| React foundation | **4 OK**, 2,602 s | Rutas React/redirects históricos, contrato de identidad y caché de assets. |
| Configuration layer access | **9 OK**, 9,230 s | Capacidades independientes, revocación por request, denegaciones y semántica del alias histórico `client`. |
| TS7-019 layered catalog | **5 OK**, 3,859 s | Cuenta normal, allowlist explícita, cuenta de verificación, externo rechazado y detalle del inspector. |

Total: **86 pruebas existentes aprobadas** (62 componentes, 6 navegador, 18 Python). Las variables de las invocaciones de verificación se limitaron a sus procesos PowerShell; no se editó `.env` ni la configuración persistente.

No se ejecutaron la suite completa, PostgreSQL, C6 activo, Julia real, `npm run check` ni regeneración OpenAPI. UX-000 no modifica producto, SQL, contratos ni generación. Estas omisiones no cuentan como aprobaciones; UX-001 debe ejecutar su regresión tras cada cambio y los tickets de datos deben incorporar ambos estados C6 que afecten.

## Capacidades a conservar en UX-001

Esta selección remite a las filas de la [matriz funcional](../../03_matriz_funcional.md). Constituye el alcance de regresión de UX-001, no una afirmación de que se ejecutó toda la matriz.

| Fila / capacidad | Acceso actual que debe seguir disponible | Evidencia de preparación |
| --- | --- | --- |
| Bootstrap, sesiones y tres raíces | Entrada del backend; admin, analista, consola y portal | Fichas de identidad, `ApplicationRoots`, E2E auth/accesos y API de capacidades. |
| Proyectos y escenarios | `/projects`, `/projects/:id`, `/scenarios/:id`; crear, recargar, regresar | E2E de workspace y capturas; `App.test.tsx`. |
| Editor y cambios pendientes | `/scenarios/:id/draft`; documento persistido sin promoción implícita | Retomar e importar por UI; regresión de editor en `App.test.tsx`. |
| Diagrama hidráulico v3 | `/scenarios/:id/hydraulic-diagram`, desde el editor de hidro | E2E hidráulico y pruebas de componente existentes aprobadas. |
| Variantes y ejecución | Selector/clonación, fuentes/rango, revalidación, ejecución por variante | Recorridos 02–04 y regresión `App.test.tsx`; no cambiar escritor por el flag de lectura. |
| Versiones y JSON experto | Entrada experta en escenario; `/scenario-versions/:id` | Pruebas existentes de pegar/subir, detalle y borrado protegido en `App.test.tsx`. |
| Corridas y comparación | `/runs/:id`, `/scenarios/:id/runs/compare` | Recorridos 03 y 05; resultados, polling y snapshot en `App.test.tsx`. |
| Datos, portal, templates y consolas | Catálogo por proyecto; configuración/plantillas; consola por escenario | Recorridos 02, 06, 07; E2E portal y accesos. El catálogo con todas sus mutaciones no se auditó exhaustivamente. |
| Borrado y accesos | Borrado contextual confirmado; accesos visibles solo a admin | Prueba de confirmación en `App.test.tsx` y E2E de administración. No se repitió la purga PostgreSQL de TS7-024. |

## Fronteras propuestas para aprobación

La habilidad [TDD local](../../../../.agents/skills/tdd/SKILL.md) exige explícitamente:

> Before writing any test, write down the seams under test and confirm them with the user.

Se propone el siguiente acuerdo para UX-001. La autorización para ejecutar UX-000 permitió preparar esta evidencia y ejecutar pruebas existentes; no se registra como confirmación implícita de fronteras nuevas.

| Frontera | Alcance concreto propuesto | Estado |
| --- | --- | --- |
| F1: navegador → React → FastAPI aislado | Recorrido visible de proyecto/escenario a editor, retornos, enlaces directos, recarga y persistencia; cookies/permisos reales. Reusar Playwright y servidor smoke. | Pendiente de confirmación del usuario. |
| F2: React renderizado con Testing Library | Nombres/roles accesibles, navegación, carga/error/desconocido, foco y cambios pendientes; HTTP controlado en la frontera. Sin mocks de hooks ni detalles privados. | Pendiente de confirmación del usuario. |
| F3: API pública autenticada → almacén de prueba | Solo si la primera implementación amplía contrato, permisos, precondiciones o persistencia. Si no cambia API, bastan sus regresiones existentes. | Propuesta condicional, pendiente de confirmación. |
| F4: API/CLI pública de Julia | No necesaria para UX-001: no se propone cambiar generación, materialización ni matemática. Reabrir el acuerdo si el alcance cambia. | No aplica al alcance actual; no solicitada. |

Fecha propuesta: 2026-09-12. Persona que confirma y referencia de confirmación: **pendientes de respuesta del usuario**. Tras la aceptación, actualizar esta tabla, la estrategia TDD, el ticket y el tracker. No marcar UX-000 `Done` antes de ese acuerdo.

## Primer comportamiento de UX-001

**Condición inicial:** analista autenticado en el proyecto ficticio, escenario `Sin modelo`, sin draft guardado; las consultas públicas necesarias han terminado correctamente. Una variante creada de forma perezosa o la ausencia de versiones no sustituyen la consulta del modelo.

**Acción:** abrir el escenario y activar el enlace accesible «Crear modelo».

**Resultado esperado:** se identifica el proyecto/escenario y se llega con una acción a `/react/scenarios/<mismo-id>/draft`, donde se puede iniciar el modelo. La navegación no ejecuta, no promueve y no crea otra identidad de escenario. Un fallo de consulta no se presenta como ausencia de modelo ni como preparación válida.

Primera frontera propuesta: **F2**, renderizando la aplicación y navegando con Testing Library. Una sola prueba RED del enlace/contexto esperado (hoy dice «Abrir draft»), GREEN mínimo y regresión pertinente; después adaptar el recorrido F1. No se escribió esa prueba ni las conductas posteriores. El error de consulta será un ciclo separado si el primer cambio introduce esa decisión de estado.

## Aceptación pendiente

- [x] Registro nuevo de línea base con commit, entorno, datos, capturas, comandos y límites.
- [x] Tarea principal repetible sin proyectos de trabajo, con siete recorridos automatizados documentados.
- [x] Capacidades de UX-001 identificadas y primer comportamiento redactado.
- [x] Pruebas existentes ejecutadas y resultados explícitos.
- [ ] Fronteras F1/F2 y uso condicional de F3 confirmados por el usuario; aceptación de UX-000.

No aplica RED → GREEN a esta preparación, tal como indica UX-000. El commit `docs(ux): record reproducible UX-000 baseline` registra la evidencia para revisión; no cierra el issue ni confirma las fronteras. No hay PR de resolución todavía.
