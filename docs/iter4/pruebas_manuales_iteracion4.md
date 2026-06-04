# Pruebas Manuales Iteracion 4

## Objetivo

Este archivo sirve como checklist manual para revisar el flujo web entregado en
Iteracion 4. El foco es comprobar que un analista puede crear un caso one-bus
desde la pagina web sin escribir `system_case.json`, cargar series CSV/XLSX,
mapear columnas, validar con Julia, promover a una version inmutable, ejecutar
una corrida manual y revisar resultados.

Tambien cubre regresiones que no deben romperse:

- Iteracion 1: fisica BESS, outputs y reporte base.
- Iteracion 2: contrato `bess_system_dispatch.v1`, grafo one-bus, CLI Julia y
  outputs auditables.
- Iteracion 3: flujo web `Project -> Scenario -> ScenarioVersion -> Run ->
  Artifacts -> Results`.
- Iteracion 4: editor estructurado, borradores, CSV/XLSX, precios separados,
  preview generado, promocion y metadatos de procedencia.

## Registro De Prueba

| Campo | Valor |
| --- | --- |
| Fecha | |
| Tester | |
| Rama/commit | |
| Navegador | |
| URL local | |
| Resultado general | Pendiente |

## Preparacion Local

Ejecutar desde la raiz del repositorio.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///.tmp/manual_iter4.sqlite3"
$env:ARTIFACT_ROOT = ".tmp/manual-artifacts"
$env:INPUT_SOURCE_ROOT = ".tmp/manual-input-sources"
$env:JULIA = "julia"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir:

```text
http://127.0.0.1:8000/projects
```

Si el puerto `8000` esta ocupado, usar otro puerto con `--port 8001` y ajustar
la URL de revision.

## Datos De Prueba

### Valores Del Draft

Usar estos valores en el formulario estructurado del draft.

| Campo | Valor |
| --- | --- |
| `case_name` | `iter4_manual_csv_case` o `iter4_manual_xlsx_case` |
| `pcc_id` | `bus_1` |
| `grid_id` | `grid_1` |
| `grid_import_power_max_mw` | `10.0` |
| `grid_export_power_max_mw` | `10.0` |
| `prevent_simultaneous_grid_import_export` | marcado |
| `battery_id` | `battery_1` |
| `charge_power_max_mw` | `4.0` |
| `discharge_power_max_mw` | `4.0` |
| `energy_min_mwh` | `0.0` |
| `energy_max_mwh` | `8.0` |
| `initial_energy_mwh` | `4.0` |
| `charge_efficiency` | `0.95` |
| `discharge_efficiency` | `0.95` |
| `degradation_cost_per_mwh_delta_soc` | `0.0` |
| `terminal_condition` | `none` |
| `terminal_energy_min_mwh` | vacio |
| `prevent_simultaneous_charge_discharge` | marcado |
| `degradation_linear_delta_soc` | marcado |
| `renewable_id` | `solar_1` |
| `renewable_category` | `solar` |
| `curtailment_penalty_usd_per_mwh` | `0.0` |
| `load_id` | `load_1` |
| `solver_name` | `HiGHS` |
| `solver_options_json` | `{}` |

### CSV

Contenido esperado para el archivo CSV manual:

```csv
period_start,hours,buy_price,sell_price,solar_mw,load_mw
2026-01-01T00:00:00,0.5,55.0,42.0,3.5,2.0
2026-01-01T00:30:00,0.5,60.0,48.0,4.0,2.5
```

### XLSX

Crear un workbook `.xlsx` simple con una hoja llamada `Inputs`.

| period_start | hours | buy_price | sell_price | solar_mw | load_mw |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2026-01-01T00:00:00` | `0.5` | `55.0` | `42.0` | `3.5` | `2.0` |
| `2026-01-01T00:30:00` | `0.5` | `60.0` | `48.0` | `4.0` | `2.5` |

### Mapeo De Columnas

Usar este mapeo para CSV y XLSX:

| Campo del editor | Columna fuente |
| --- | --- |
| `timestamp` | `period_start` |
| `duration_hours` | `hours` |
| `price_usd_per_mwh` | vacio |
| `import_price_usd_per_mwh` | `buy_price` |
| `export_price_usd_per_mwh` | `sell_price` |
| `renewable_available_power_mw.solar_1` | `solar_mw` |
| `load_demand_mw.load_1` | `load_mw` |

## Flujo Feliz CSV

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir `/projects`. | La pagina `Projects` carga con formulario `New Project`; no hay errores visibles ni texto superpuesto. | Pendiente |
| 2 | Crear proyecto `Iter4 Manual CSV`. | Redirige al detalle del proyecto y muestra el proyecto creado. | Pendiente |
| 3 | Crear escenario `Structured CSV`. | Redirige a la pagina del escenario; aparece seccion `Structured Draft` y enlace `Open Draft`. | Pendiente |
| 4 | Abrir `Open Draft`. | La pagina `Structured Draft` muestra formularios `Case Metadata`, `PCC And Grid`, `Battery Asset`, `Renewable And Load Assets`, `Solver`, `CSV Time-Series Source`, `Draft Document`. | Pendiente |
| 5 | Completar valores del draft y presionar `Save Structured Draft`. | Vuelve al draft y muestra `Active draft ... last saved at ...`; el textarea `structured_draft_json` refleja los datos guardados. | Pendiente |
| 6 | Subir el CSV en `source_file` y presionar `Upload Source`. | Aparece `CSV Time-Series Source`, nombre del archivo, columnas detectadas y tabla de preview con 2 filas. | Pendiente |
| 7 | Completar el mapeo de columnas y presionar `Save Mapping`. | Aparece `Time-Series Validation` con `Valid mapped rows: 2`. | Pendiente |
| 8 | Revisar `Generated System Case Preview`. | El textarea `generated_system_case_preview` es readonly e incluye `schema_version: bess_system_dispatch.v1`, `case_name`, nodos `bus_1`, `grid_1`, `battery_1`, `solar_1`, `load_1`, edges al PCC y 2 periodos. | Pendiente |
| 9 | Verificar precios separados en el preview. | Cada periodo tiene `import_price_usd_per_mwh` y `export_price_usd_per_mwh`; no depende de `price_usd_per_mwh`. | Pendiente |
| 10 | Presionar `Validate Generated System Case`. | Aparece `Generated System Case Validation` con `Valid: Validation succeeded`. | Pendiente |
| 11 | Confirmar boton de promocion. | Aparece `Promote To Scenario Version` solo despues de una validacion exitosa actual. | Pendiente |
| 12 | Presionar `Promote To Scenario Version`. | Redirige al escenario y aparece `Version 1` con el `case_name` del draft, schema `bess_system_dispatch.v1`, periodo count y conteo de assets. | Pendiente |
| 13 | Presionar `Launch Run` en la version creada. | Redirige a `/runs/{id}`; el estado pasa por `queued`/`running` y termina en `succeeded`. | Pendiente |
| 14 | Revisar artefactos. | La seccion `Artifacts` muestra links para `input_snapshot`, `stdout_log`, `stderr_log`, `summary_json`, `dispatch_csv`, `asset_dispatch_csv`, `model_metadata_json`. | Pendiente |
| 15 | Abrir descargas de artefactos principales. | `summary.json`, `dispatch.csv`, `asset_dispatch.csv` y `model_metadata.json` descargan o abren con HTTP 200. | Pendiente |
| 16 | Revisar resultados. | La pagina muestra `Run Summary`, `Basic Charts`, `System Dispatch` y `Asset Dispatch`. | Pendiente |
| 17 | Revisar precios separados en resultados. | `System Dispatch` incluye `import_price_usd_per_mwh`, `export_price_usd_per_mwh`, `import_cost_usd`, `export_revenue_usd`, `net_market_value_usd` y `period_profit_usd`. | Pendiente |
| 18 | Revisar chart de precios. | En `Basic Charts`, el chart de precios usa series separadas de importacion y exportacion. | Pendiente |

## Flujo Feliz XLSX

Repetir el flujo CSV en un escenario nuevo llamado `Structured XLSX`, usando
`iter4_manual_xlsx_case` como `case_name`.

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir draft del escenario `Structured XLSX`. | La pagina muestra el mismo editor estructurado. | Pendiente |
| 2 | Guardar valores del draft. | Se guarda un unico draft activo para el escenario. | Pendiente |
| 3 | Subir el `.xlsx`; si se usa la hoja `Inputs`, completar `xlsx_sheet_name` con `Inputs`. | Aparece `XLSX Time-Series Source`, nombre del archivo, `Sheet: Inputs`, columnas y preview con 2 filas. | Pendiente |
| 4 | Guardar el mismo mapeo de columnas. | Aparece `Time-Series Validation` con `Valid mapped rows: 2`. | Pendiente |
| 5 | Revisar preview generado. | El `system_case` generado es equivalente al CSV y contiene precios separados. | Pendiente |
| 6 | Validar, promover y lanzar corrida. | La corrida termina `succeeded` y registra los mismos tipos de artefactos. | Pendiente |
| 7 | Revisar resultados. | Tablas y charts muestran precios separados, costos de importacion, ingresos de exportacion y valor neto de mercado. | Pendiente |

## Inmutabilidad Y Draft Editable

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Volver al draft despues de promover una version. | El draft sigue editable; la promocion no lo elimina. | Pendiente |
| 2 | Cambiar `case_name` a `iter4_manual_csv_case_v2` y guardar. | El draft cambia, pero `Version 1` conserva el nombre original. | Pendiente |
| 3 | Validar y promover otra vez. | Aparece `Version 2`; `Version 1` permanece listada e inmutable. | Pendiente |
| 4 | Usar `Use as draft base` desde una version existente. | El draft se inicializa desde esa version sin modificar la version fuente. | Pendiente |

## Regresion JSON Iteracion 3

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Crear escenario `Legacy JSON Paste`. | La pagina del escenario muestra formulario `New Version`. | Pendiente |
| 2 | Pegar el contenido de `data/cases/hybrid_system/system_case.json` en `system_case_json` y presionar `Validate And Save`. | Se crea una version con `case_name` `hybrid_system`; no se usa el editor estructurado. | Pendiente |
| 3 | Lanzar corrida de esa version. | La corrida termina `succeeded`. | Pendiente |
| 4 | Revisar resultados legacy. | `System Dispatch` contiene `price_usd_per_mwh`; el chart de precio usa una sola serie legacy. | Pendiente |
| 5 | Crear escenario `Legacy JSON Upload`. | El escenario carga correctamente. | Pendiente |
| 6 | Subir `data/cases/hybrid_system/system_case.json` con `Upload JSON` y `Validate And Save`. | Se crea otra version valida con el mismo contrato legacy. | Pendiente |

## Errores Manuales A Revisar

Cada prueba debe hacerse en un draft de prueba o corrigiendo el dato despues de
verificar el error.

| Caso | Como provocarlo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| Solver options no JSON | Escribir `not-json` en `solver_options_json` y guardar el formulario estructurado. | La pagina muestra un error de draft; no se genera caso valido. | Pendiente |
| ID duplicado | Usar el mismo ID para `pcc_id` y `battery_id`, o duplicar IDs en `structured_draft_json`. | La generacion/preview falla antes de promocion; no se crea version. | Pendiente |
| Mapeo incompleto | Dejar vacio `duration_hours` o mapear solo `import_price_usd_per_mwh` sin `export_price_usd_per_mwh`. | `Time-Series Validation` muestra `Mapping Error`. | Pendiente |
| Valor no numerico | Usar texto en una columna numerica, por ejemplo `load_mw = abc`. | `Time-Series Validation` muestra `Python Validation Error`. | Pendiente |
| Duracion invalida | Usar `hours = 0` o valor negativo. | `Time-Series Validation` rechaza la fuente antes de Julia. | Pendiente |
| Timestamp duplicado o desordenado | Repetir `period_start` o invertir el orden temporal. | `Time-Series Validation` rechaza timestamps duplicados o no ordenados. | Pendiente |
| Renovable o carga negativa | Usar `solar_mw = -1` o `load_mw = -1`. | `Time-Series Validation` rechaza valores fisicos negativos. | Pendiente |
| XLSX invalido | Subir workbook con headers duplicados, header vacio o sheet inexistente. | La pagina muestra categoria `Source-file Error`. | Pendiente |
| Julia validation error | Generar un caso con un parametro que Julia rechace, por ejemplo `terminal_condition` invalido. | `Generated System Case Validation` muestra `Invalid` o categoria `Julia Validation Error`; no aparece promocion valida. | Pendiente |
| Promocion obsoleta | Validar un draft, editar un campo y tratar de promover sin revalidar. | La promocion se bloquea porque el snapshot validado ya no coincide con el draft actual. | Pendiente |

## Revision Visual De Componentes

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Project list | Lista y formulario legibles; estados vacios claros. | Pendiente |
| Project detail | Lista escenarios y formulario `New Scenario` sin superposicion. | Pendiente |
| Scenario detail | Muestra versiones, `Open Draft`, `Use as base`, `Use as draft base`, `Launch Run`. | Pendiente |
| Structured draft | Campos alineados, labels visibles, checkboxes claros y textarea raw usable. | Pendiente |
| Source preview | Tabla horizontal desplazable si hay muchas columnas; no rompe layout. | Pendiente |
| Column mapping | Campos para timestamp, duracion, precio legacy, precios separados, renovable y carga. | Pendiente |
| Generated preview | Textarea readonly, scroll usable, JSON completo visible. | Pendiente |
| Validation notices | Mensajes de exito/error se distinguen visualmente. | Pendiente |
| Run page | Polling actualiza estado; fechas, exit code y error son visibles. | Pendiente |
| Artifacts | Links de descarga tienen nombre, tipo, media type y peso. | Pendiente |
| Results | Summary, charts, tablas y scroll horizontal se ven correctamente. | Pendiente |
| Responsive | Revisar desktop y ancho movil; no debe haber texto superpuesto ni botones cortados. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia de
aceptacion de Iteracion 4.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter4_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

## Cierre

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Flujo CSV estructurado | Pendiente | |
| Flujo XLSX estructurado | Pendiente | |
| Promocion y corrida manual | Pendiente | |
| Resultados con precios separados | Pendiente | |
| Regresion JSON paste/upload | Pendiente | |
| Errores de ingestion/mapping/validacion | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
