# MESA-005 · Consulta hidráulica por identidad

Estado: **Done**. Fecha: 2026-10-20. Responsable: Codex. Interfaces S1 navegador y S2 HTTP,
confirmadas en MESA-001. Revisión técnica AFK; sin cambios al motor.

## Recorrido y contrato

La mesa ofrece centrales, embalses, unidades, nodos y tramos del diagrama del
caso. Dos centrales llamadas «Central Norte» siguen siendo dos componentes.
Cada uno conserva `linkable_object_id`, clave técnica, `base_entity_id` y
`case_entity_id`. Las unidades identifican su central con `parent_entity_id`;
unidades y tramos exponen sus conexiones en `from_entity_id`/`to_entity_id`.
Los selectores y paneles muestran la pertenencia y distinguen objetos inactivos.
Las preferencias siguen referenciando la identidad base/técnica; el identificador
numérico de la participación actual puede cambiar al guardar el diagrama, como
ya sucede en el dominio hidráulico.

La proyección de lectura `read_hydraulic_case_inventory` reutiliza el diagrama,
sus detalles y las relaciones existentes por caso. El registro vinculable se
resuelve por tipo y ID base, evitando colisiones por nombre o clave de otro
sistema. No crea tablas, migraciones, catálogos ni copias persistidas de muestras.
No cambia el checkpoint de BBDD hidráulico.

`GET /api/scenarios/{scenario_id}/mesa` conserva caso/variante/rango y amplía la
consulta de `run_id` a resultados v3. Los nuevos campos de componente son
aditivos; OpenAPI y tipos React están sincronizados.

Las entradas de aporte/caudal mínimo tienen esta precedencia:

1. Revisión canónica vinculada al objeto en la variante seleccionada.
2. Fuente del catálogo anterior vinculada explícitamente a esa variante.
3. Fuente del diagrama solo en la variante predeterminada sin bindings protegidos.

Una variante sin preparar no hereda silenciosamente el aporte del diagrama.
Se reutilizan las lecturas del catálogo y el adaptador hidráulico vigentes,
con `source`, ID de fuente, revisión/hash cuando existen, unidad e intervalos.
La consulta no remuestrea ni rellena huecos. El volumen inicial es un parámetro
escalar, separado de la trayectoria calculada de volumen.

Los resultados se leen primero del índice por activo y luego del CSV registrado
si falta el índice. Se emparejan por tipo, clave, señal, período y duración del
snapshot. Los DateTime sin offset escritos por Julia se corresponden con las
horas del snapshot; no se usa la zona mutable de una fuente actual.

La potencia y el caudal de una central suman exclusivamente sus unidades del
snapshot, con pertenencia completa y conexiones compatibles. No se atribuye el
aporte del embalse a la central ni se muestran los ceros de columnas que no
corresponden al tipo de entidad. Los enlaces con tránsito compilado se resuelven
mediante `diagram_link` del snapshot, sin inferir identidades por nombre.
Embalses exponen volumen/cota/vertimiento; unidades potencia/caudal; tramos su
caudal. Hidro simple v2 conserva entrada, parámetros y resultados por activo en
su propio contrato eléctrico. La red v3 mantiene su contrato hidráulico separado.

Objetos inactivos/archivados, centrales no modeladas, columnas ausentes/vacías,
miembros incompletos y conexiones incompatibles producen estados explicativos.
Una unidad archivada tampoco contribuye al total de su central. Los runs ajenos,
de otra variante o no exitosos se rechazan; sesión anónima y usuario externo no
obtienen esta consulta interna.

## Ciclos rojo → verde observados

Cada fila fue ejecutada antes de implementar su solución. Las observaciones son
HTTP/navegador; las llamadas al almacén solo preparan las fixtures y artefactos.

| Ciclo | Interfaz y conducta | Rojo observado | Verde |
| --- | --- | --- | --- |
| 1 | S2, centrales homónimas | Inventario devolvía `[]`. | Dos identidades base/caso distintas, unidades y tramo recuperables. |
| 2 | S2, aporte y volumen inicial | El embalse ofrecía potencia en vez de aporte. | Aporte [2, 4] m3/s con fuente y períodos; volumen inicial 10 hm3 escalar. |
| 3 | S2, resultados existentes v3 | Seleccionar el run devolvía 404. | Centrales [3, 6] y [9, 12] MW; volumen [9.8, 9.6] hm3; cota y caudales propios. |
| 4 | S1, recorrido hidráulico | No existía la región identificada como embalse. | Selección, parámetros, tablas/gráficos, escalas separadas y recarga. |
| 5 | S2, unidad inactiva | Seguía mostrando [3, 6] MW. | Identidad conservada, sin muestras y con mensaje de inactividad. |
| 6 | S2, variante canónica | Devolvía aporte del diagrama [2, 4]. | Devuelve [7, 9] de la revisión canónica seleccionada. |
| 7 | S2, variante sin preparar | Devolvía `available` por herencia implícita. | `unbound`, explicación y muestras vacías. |
| 8 | S2, hidro simple v2 | No aparecía `hydro_1`. | Parámetro inicial 2.5 hm3 y potencia [0.5, 1] MW del activo. |
| 9 | S2, central no modelada | Seguía mostrando su resultado histórico como compatible. | Estado «Central no modelada», sin muestras. |
| 10 | S2, mínimo canónico de tramo | Solo ofrecía salida de caudal. | Entrada [7, 9] con revisión canónica, sin exigir binding del diagrama. |
| 11 | S2, variante anterior | Aporte devolvía `[]`. | Lee [11, 13] de su fuente del catálogo anterior. |
| 12 | S1, pertenencia | El panel de unidad no mostraba su central. | Central y conexiones visibles en unidad/tramo. |
| 13 | S2, unidad archivada | La central aún sumaba [3, 6] MW. | Sin contribución archivada; otra central conserva [9, 12] MW. |
| 14 | S2, tránsito de conexión | La central con enlace compilado devolvía `[]`. | Recupera [3, 6] MW por el linaje de la conexión original. |
| 15 | S1, geometría con selector de run | Segunda fila terminaba en 956.015625 px. | Paneles ajustados en escritorio para conservar ambas filas a 1440×900. |
| 16 | S1, procedencia visible | El pie de una serie única tenía ratio visible 0 por compartir panel con parámetros. | El gráfico único ajusta su altura y mantiene el pie visible; las series múltiples conservan scroll local. |

También se verifican fallback a CSV, columna incompleta, cambio de conexión,
cobertura incompleta/fuente ausente, aislamiento y permisos, y suma de dos
unidades de la misma central: [4, 8] MW. Son regresiones de las guardas del
contrato, sin atribuirles ciclos rojos adicionales.

## Comandos y resultados

- API: ejecución amplia de **176 pruebas**, inicialmente 169 OK, cinco
  PostgreSQL omitidas y dos problemas de pruebas. Tras corregirlos y añadir el
  caso de tránsito, la ejecución final focalizada pasa **18/18**: las 17 nuevas
  de mesa hidráulica y la regresión de promoción. En conjunto: **172 pruebas
  distintas verificadas y cinco omitidas**. La primera ejecución amplia no fue
  verde. [Inicial](api-initial.txt), [final focalizada](api-final.txt).
- Frontend: **335/336** en la primera suite; falló una aserción de foco en
  `ReportExperience.test.tsx`. Repetir ese archivo sin cambios pasa **4/4**;
  las 336 quedan verificadas entre ambas ejecuciones.
  [Suite](vitest-final.txt), [reintento](vitest-retry.txt).
- Navegador MESA y geometría: **15/15**, incluidas las dos nuevas pruebas
  hidráulicas. [Resultado final](playwright-final.txt).
- Regresión de navegador: **5/5**, autenticación, escenario, preparación,
  resultados y edición del diagrama hidráulico. [Log](playwright-regression.txt).
- Build, TypeScript, ESLint y [OpenAPI/tipos](api-schema-final.txt) OK.
  El [check global](check-final.txt) llega a Prettier y conserva los 16 avisos
  preexistentes. El [chequeo de formato de archivos modificados](check-changed-files.txt) pasa.
- Documentación: enlaces locales, estados de los 14 tickets y tracker,
  dependencias sin ciclos y hashes/dimensiones originales comprobados en
  [verificación final](docs-final.txt).

Desde la raíz:

```powershell
.venv/Scripts/python.exe -m unittest -v tests.test_mesa_hydraulic tests.test_optimization_mesa tests.test_mesa_preferences tests.test_hydraulic_diagram tests.test_hydraulic_time_series_adapter tests.test_ts5_hydraulic_series_catalog_adapter tests.test_ts5_hydraulic_series_generic_write tests.test_ts3_case_variant_api tests.test_ts7_009_run_materialization tests.test_ts4_result_indexing tests.test_results_review tests.test_react_auth tests.test_configuration_layer_access
.venv/Scripts/python.exe -m unittest -v tests.test_mesa_hydraulic tests.test_hydraulic_diagram.HydraulicDiagramApiTests.test_validated_v3_diagram_promotes_to_version_and_manual_run_artifacts
```

Desde `frontend`:

```powershell
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run build
npx.cmd playwright test --config=playwright.mesa.config.ts
npx.cmd playwright test e2e/react-foundation.spec.ts -g "React auth handles|React analyst workspace|UX-005|UX-006|React hydraulic diagram persists"
npm.cmd test -- --maxWorkers=1
npm.cmd test -- src/ReportExperience.test.tsx --maxWorkers=1
npm.cmd run check
npx.cmd prettier --check src/OptimizationMesa.tsx src/MesaPreferences.tsx src/optimizationMesa.css e2e/optimization-mesa.spec.ts src/api/schema.ts openapi.json
```

## Revisión e incidencias

- El primer ciclo tuvo un error de plural SQL (`reachs`), corregido antes de
  confirmar verde. No se cuenta como un ciclo adicional.
- La nueva fixture de dos unidades no podía reutilizar el ID de curva de otra
  entidad. Se corrigió para crear su curva propia; no cambió la validación del dominio.
- La regresión antigua de promoción omitía `progress_log` en el conjunto de
  artefactos esperado. Se actualizó esa expectativa al worker vigente, conservando
  la comparación exacta del conjunto.
- Al mostrar la central en las opciones de unidad, el selector del test basado
  en substring pasó a coincidir con dos opciones. Se precisó la clave técnica de
  la opción; [primera suite](playwright-initial.txt), sin relajar la comprobación
  de identidad ni los criterios de producto.
- Un intento de lanzar simultáneamente ambos servidores de navegador terminó
  durante el arranque de MESA. [Log](playwright-startup.txt). El servidor aislado
  arrancó correctamente; se repitió la suite de mesa por separado.
- Los primeros envoltorios de comandos no podían imprimir símbolos Unicode en
  la consola cp1252 después de guardar los logs. Los logs conservaron los
  resultados; se corrigió la salida del envoltorio a UTF-8.

Las salidas son artefactos de prueba deterministas persistidos/indexados, con
literales independientes; no son una nueva ejecución real de Julia. Esta entrega
valida consulta. Ejecutar desde la mesa y comparar antes/después permanecen en
MESA-008/010. No modifica datos operativos ni publica cambios externamente.

Capturas de implementación, conservando los originales:

- [Escritorio 1440×900](mesa-hidraulica-1440.png).
- [Móvil 390 px, página completa](mesa-hidraulica-390.png).

Entorno: Chromium de Playwright 1.61.0, DPR 1, en-US, America/Santiago, tema claro
y movimiento reducido. Se conserva la cabecera del producto y la organización
de paneles de la referencia A; parámetros y series adicionales tienen scroll
local. No hay scroll horizontal global móvil. La consulta usa 2 intervalos reales
de fixture, no las 24 horas ficticias del prototipo. Axe y las regresiones de
teclado/foco están incluidas. No se crean baselines de aceptación humana MESA-014.

Cierre AFK: criterios revisados, capturas de escritorio/móvil inspeccionadas y
regresiones registradas. MESA-005 pasa de In Review a Done; MESA-006 queda como
siguiente entrega, con su dependencia satisfecha, sin iniciarla en este cambio.
