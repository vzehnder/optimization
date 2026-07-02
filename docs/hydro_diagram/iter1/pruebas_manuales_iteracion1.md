# Pruebas Manuales Hydro Diagram Iteracion 1

## Objetivo

Probar manualmente que un analista puede construir, validar, promover y correr
una red hidraulica `bess_system_dispatch.v3` desde el editor React sin romper
los flujos `v1` y `v2` existentes.

## Registro De Prueba

| Campo | Valor |
| --- | --- |
| Issue | BESS-HYDRO-DIAGRAM-011 |
| Fecha objetivo | 2026-06-29 |
| Superficie principal | React hydraulic diagram |
| Suite automatizada | `tests.test_hydro_diagram_acceptance` |

## Preparacion Local

1. Crear o verificar `.env` con PostgreSQL local, `ARTIFACT_ROOT`,
   `INPUT_SOURCE_ROOT` y ruta `JULIA`.
2. Iniciar backend y frontend:

```powershell
.\\.venv\\Scripts\\python.exe -m app.main
cd frontend
npm.cmd run dev
```

3. Abrir `/react`, crear o iniciar sesion como usuario `admin` o `analyst`.
4. Confirmar que el motor Julia local ejecuta:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Datos De Prueba

Usar un proyecto nuevo llamado `Hydro Diagram Iter1 Manual`.

Crear un escenario llamado `Hydraulic v3 manual acceptance` y abrir
`Abrir diagrama hidraulico`.

Nodos y activos:

| Tipo | Technical key | Nombre |
| --- | --- | --- |
| Reservoir | `reservoir_1` | Reservoir 1 |
| Junction | `junction_1` | Intake |
| Junction | `junction_2` | Tailrace |
| Plant | `plant_1` | Plant Laja |

Reach:

| Technical key | Desde | Hacia | Tipo | Caudal minimo |
| --- | --- | --- | --- | --- |
| `reach_reservoir_1_junction_1` | `reservoir_1` | `junction_1` | `river` | `0` |

Embalse:

| Campo | Valor |
| --- | --- |
| Storage min hm3 | `5` |
| Storage max hm3 | `50` |
| Initial storage hm3 | `20` |
| Terminal condition | `min_terminal` |
| Terminal min hm3 | `10` |
| Terminal water value USD/hm3 | `8` |

Curva `storage_elevation`:

| storage_hm3 | elevation_masl |
| --- | --- |
| `5` | `700` |
| `50` | `760` |

Serie `natural_inflow_m3s`:

| Timestamp | Duration hours | Value m3/s |
| --- | --- | --- |
| `2026-01-01T00:00:00` | `1` | `5` |
| `2026-01-01T01:00:00` | `1` | `6` |

Unidad:

| Campo | Valor |
| --- | --- |
| Technical key | `unit_1` |
| Intake node | `junction_1` |
| Discharge node | `junction_2` |
| Max power MW | `30` |
| Max flow m3/s | `40` |

Curva `flow_power`:

| flow_m3s | power_mw |
| --- | --- |
| `0` | `0` |
| `40` | `30` |

## Flujo Feliz

1. Crear proyecto y escenario.
2. Abrir el diagrama hidraulico desde la pagina del escenario.
3. Agregar embalse, dos uniones y central.
4. Dibujar o crear por formulario el reach dirigido del embalse a la toma.
5. Editar parametros del embalse y guardar la curva `storage_elevation`.
6. Agregar serie `natural_inflow_m3s` al embalse.
7. Agregar unidad en la central, asignar toma/descarga y guardar la curva
   `flow_power`.
8. Guardar el diagrama y recargar la pagina.
9. Confirmar que nodos, posiciones, reach, curvas y series persisten.
10. Ejecutar `Validar topologia` y confirmar estado valido.
11. Ejecutar `Generar preview v3`.
12. Confirmar que el preview muestra `bess_system_dispatch.v3`, red
    hidraulica, curvas y serie de afluente.
13. Promover la version v3.
14. Abrir la version promovida y lanzar un run manual.
15. Abrir resultados del run.
16. Confirmar `summary.json`, `dispatch.csv`, `asset_dispatch.csv`,
    `system_case_resolved.json` y `model_metadata.json`.
17. Confirmar tablas/charts de potencia hidraulica, caudal, almacenamiento y
    cota de embalse cuando las columnas existen.
18. Descargar `system_case_resolved.json` y confirmar que el snapshot contiene
    `schema_version = bess_system_dispatch.v3`.

## Inmutabilidad Y Stale Validation

1. Despues de promover, abrir el snapshot visual de la version.
2. Volver al caso editable y mover nodos.
3. Confirmar que el snapshot historico no cambia.
4. Cambiar un parametro fisico del embalse.
5. Confirmar que la validacion queda `stale`.
6. Intentar promover sin revalidar.
7. Confirmar que la promocion queda bloqueada.

## Regresiones v1 y v2

1. Crear un escenario desde `data/cases/hybrid_system/system_case.json`.
2. Promoverlo y correrlo como `bess_system_dispatch.v1`.
3. Confirmar resultados y artefactos.
4. Crear o reutilizar un caso `bess_system_dispatch.v2` de hidro simple.
5. Validar, promover y correr.
6. Confirmar que los resultados hidro simple siguen disponibles.

## Errores Manuales A Revisar

| Error | Resultado esperado |
| --- | --- |
| Embalse sin serie de afluente | `missing_natural_inflow_series` |
| Curva de almacenamiento no monotona | `non_increasing_storage_points` |
| Unidad sin curva `flow_power` | `missing_flow_power_curve` |
| Reach con routing distinto de `none` | `unsupported_reach_routing` |
| Ciclo dirigido | `unsupported_cycle` |
| Isla sin embalse ni afluente | `island_without_boundary` |
| Unidad `pump_only` o `reversible` | `unsupported_unit_operation_mode` |
| Generacion `head_dependent` | `unsupported_unit_generation_mode` |

## Verificacion Automatizada Complementaria

```powershell
.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydro_diagram_acceptance -v
.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram -v
.\\.venv\\Scripts\\python.exe -m unittest discover tests -v
julia --project=. -e "import Pkg; Pkg.test()"
cd frontend
npm.cmd test
npm.cmd run check
npm.cmd run api:generate
npm.cmd run api:check
npm.cmd run test:browser -- -g "hydraulic diagram persists"
```

## Cierre Iteracion Hydro Diagram 1

La iteracion queda cerrada cuando el flujo feliz, la inmutabilidad, las
regresiones `v1`/`v2` y las suites automatizadas anteriores pasan.

## Trabajo Futuro Fuera De Alcance

- topology import desde CSV/XLSX para crear nodos y reaches en lote.
- routing hidraulico avanzado y tiempos de viaje discretos.
- head-dependent generation y superficies de eficiencia.
- pumped storage, bombeo puro y unidades reversibles ejecutables.
- collaborative editing con presencia, comentarios y merge de conflictos.
- Vista historica React dedicada para snapshots visuales promovidos.
