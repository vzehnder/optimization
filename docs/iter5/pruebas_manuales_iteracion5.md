# Pruebas Manuales Iteracion 5

## Objetivo

Este archivo sirve como checklist manual para revisar el flujo web entregado en
Iteracion 5. El foco es comprobar que un analista puede crear un caso one-bus
con hidraulica simple desde la pagina web, cargar series CSV/XLSX, mapear
afluentes en `m3/s`, validar con Julia, promover a una version inmutable,
ejecutar una corrida manual y revisar resultados hidraulicos.

Tambien cubre regresiones que no deben romperse:

- Iteracion 1: fisica BESS, outputs y reporte base.
- Iteracion 2: contrato one-bus `v1`, CLI Julia y outputs auditables.
- Iteracion 3: flujo web `Project -> Scenario -> ScenarioVersion -> Run`.
- Iteracion 4: editor estructurado, CSV/XLSX, precios separados y resultados.
- Iteracion 5: contrato `v2`, activo `hydro`, embalse simple, curvas,
  vertimiento, valor terminal del agua y resultados hidraulicos.

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
$env:DATABASE_URL = "sqlite:///.tmp/manual_iter5.sqlite3"
$env:ARTIFACT_ROOT = ".tmp/manual-artifacts"
$env:INPUT_SOURCE_ROOT = ".tmp/manual-input-sources"
$env:JULIA = "julia"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir:

```text
http://127.0.0.1:8000/projects
```

## Datos De Prueba Lineal

Usar estos valores para un caso hidro lineal.

| Campo | Valor |
| --- | --- |
| `case_name` | `iter5_manual_hydro_linear_case` |
| `pcc_id` | `bus_1` |
| `grid_id` | `grid_1` |
| `grid_import_power_max_mw` | `20.0` |
| `grid_export_power_max_mw` | `20.0` |
| `hydro_id` | `hydro_1` |
| `storage_min_hm3` | `1.0` |
| `storage_max_hm3` | `5.0` |
| `initial_storage_hm3` | `2.5` |
| `generation_mode` | `linear` |
| `power_per_flow_mw_per_m3s` | `0.08` |
| `turbine_flow_max_m3s` | `40.0` |
| `power_max_mw` | `3.0` |
| `minimum_release_m3s` | `0.0` |
| `spill_penalty_usd_per_hm3` | `100.0` |
| `terminal_condition` | `min_terminal` |
| `terminal_storage_min_hm3` | `2.0` |
| `terminal_water_value_usd_per_hm3` | `500.0` |
| `solver_name` | `HiGHS` |
| `solver_options_json` | `{}` |

Reservoir curve:

| storage_hm3 | elevation_masl |
| ---: | ---: |
| 1.0 | 700.0 |
| 3.0 | 710.0 |
| 5.0 | 720.0 |

CSV:

```csv
period_start,hours,buy_price,sell_price,hydro_inflow_m3s
2026-01-01T00:00:00,1.0,55.0,45.0,25.0
2026-01-01T01:00:00,1.0,60.0,80.0,30.0
2026-01-01T02:00:00,1.0,70.0,120.0,10.0
```

Mapeo:

| Campo del editor | Columna fuente |
| --- | --- |
| `timestamp` | `period_start` |
| `duration_hours` | `hours` |
| `import_price_usd_per_mwh` | `buy_price` |
| `export_price_usd_per_mwh` | `sell_price` |
| `hydro_inflow_m3s.hydro_1` | `hydro_inflow_m3s` |

## Datos De Prueba Piecewise

Usar un escenario nuevo con:

| Campo | Valor |
| --- | --- |
| `case_name` | `iter5_manual_hydro_piecewise_case` |
| `hydro_id` | `hydro_pw_1` |
| `generation_mode` | `piecewise_linear` |
| `power_max_mw` | `5.0` |

Generation curve no monotona:

| flow_m3s | power_mw |
| ---: | ---: |
| 0.0 | 0.0 |
| 15.0 | 1.8 |
| 30.0 | 2.4 |
| 45.0 | 4.0 |
| 60.0 | 3.8 |

Reservoir curve:

| storage_hm3 | elevation_masl |
| ---: | ---: |
| 1.0 | 700.0 |
| 3.0 | 710.0 |
| 5.0 | 720.0 |

Usar CSV o XLSX equivalente con columna `hydro_inflow_m3s`.

## Flujo Feliz Hidro Lineal

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir `/projects`. | La pagina carga sin errores visibles. | Pendiente |
| 2 | Crear proyecto `Iter5 Manual Hydro`. | Redirige al detalle del proyecto. | Pendiente |
| 3 | Crear escenario `Hydro Linear`. | Redirige a la pagina del escenario. | Pendiente |
| 4 | Abrir `Open Draft`. | La pagina muestra editor estructurado con seccion hidro. | Pendiente |
| 5 | Completar parametros hidro lineales y curva de embalse. | El draft se guarda sin errores. | Pendiente |
| 6 | Subir CSV lineal. | Aparece preview con columnas y filas. | Pendiente |
| 7 | Guardar mapeo incluyendo `hydro_inflow_m3s.hydro_1`. | Validation muestra filas validas. | Pendiente |
| 8 | Revisar preview generado. | El `system_case` es `bess_system_dispatch.v2` e incluye nodo `hydro`. | Pendiente |
| 9 | Validar generado. | Julia validation muestra `Valid`. | Pendiente |
| 10 | Promover a version. | Se crea version inmutable con schema `v2`. | Pendiente |
| 11 | Lanzar corrida. | La corrida termina `succeeded`. | Pendiente |
| 12 | Revisar artefactos. | Estan `summary.json`, `dispatch.csv`, `asset_dispatch.csv`, metadata e input snapshot. | Pendiente |
| 13 | Revisar resultados. | Tablas muestran columnas hidro. | Pendiente |
| 14 | Revisar charts hidro. | Hay charts de potencia, caudales, almacenamiento y cota. | Pendiente |

## Flujo Feliz Hidro Piecewise

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Crear escenario `Hydro Piecewise`. | El escenario carga correctamente. | Pendiente |
| 2 | Configurar hidro `piecewise_linear`. | La tabla de breakpoints acepta curva no monotona. | Pendiente |
| 3 | Subir CSV/XLSX y mapear afluente. | La validacion de mapping pasa. | Pendiente |
| 4 | Revisar preview generado. | El nodo hydro incluye breakpoints potencia-caudal y curva de embalse. | Pendiente |
| 5 | Validar, promover y correr. | La corrida termina `succeeded`. | Pendiente |
| 6 | Revisar outputs. | `asset_dispatch.csv` muestra fila `asset_type=hydro` por periodo. | Pendiente |

## Regresiones

| Caso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| JSON v1 paste | Pegar `data/cases/hybrid_system/system_case.json`. | Valida y corre como legacy `v1`. | Pendiente |
| Editor sin hidro | Crear caso BESS/renovable/load sin hidro. | El editor genera `v2` y la corrida sucede. | Pendiente |
| Legacy result charts | Abrir resultados de run sin hidro. | Charts existentes siguen disponibles; hidro no rompe la pagina. | Pendiente |

## Errores Manuales A Revisar

| Caso | Como provocarlo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| Falta curva embalse | Guardar hydro sin reservoir curve. | Error antes de promocion. | Pendiente |
| Storage fuera de curva | `storage_max_hm3` mayor al ultimo breakpoint. | Julia validation rechaza. | Pendiente |
| Breakpoints flow duplicados | Dos puntos con mismo `flow_m3s`. | Error de generacion o Julia validation. | Pendiente |
| Potencia negativa | Breakpoint `power_mw = -1`. | Julia validation rechaza. | Pendiente |
| Inflow faltante | No mapear `hydro_inflow_m3s`. | Mapping error. | Pendiente |
| Inflow negativo | Usar valor negativo en CSV/XLSX. | Python validation rechaza. | Pendiente |
| Min release alta | Configurar release imposible. | Run falla de forma auditable o validation detecta si corresponde. | Pendiente |
| Promocion obsoleta | Validar, editar curva y promover sin revalidar. | Promocion bloqueada. | Pendiente |

## Verificacion Automatizada Complementaria

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter5_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

## Cierre Iteracion 5

La suite final automatizada cubre el flujo linear hydro desde draft estructurado
hasta corrida y resultados, el flujo piecewise hydro con CSV/XLSX, preview
`bess_system_dispatch.v2`, validacion Julia, promocion, artefactos, tablas y
charts. Tambien cubre compatibilidad paste/upload `bess_system_dispatch.v1`,
casos estructurados sin hydro generados como `v2`, y errores claros para
afluentes hydro invalidos antes de promocion.

La revision manual debe usar esta checklist para inspeccion visual y operativa
final; la automatizacion anterior es la evidencia minima esperada antes de
marcar la iteracion como aceptada.

## Cierre

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Flujo hidro lineal | Pendiente | |
| Flujo hidro piecewise | Pendiente | |
| CSV/XLSX con afluentes | Pendiente | |
| Resultados y charts hidro | Pendiente | |
| Regresion v1 | Pendiente | |
| Regresion editor sin hidro | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
