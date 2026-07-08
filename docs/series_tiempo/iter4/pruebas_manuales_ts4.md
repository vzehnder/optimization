# Pruebas Manuales TS-4

## Objetivo

Este archivo sirve como checklist manual para revisar el flujo final de
resultados indexados en BBDD entregado en TS-4. El foco es comprobar que una
corrida exitosa indexa `dispatch.csv`, `asset_dispatch.csv` y `summary.json`
sin dejar de registrar artifacts; que la UI lee desde BBDD cuando existe
indice y cae a artifacts para corridas historicas; que el rebuild recupera
una corrida antigua; que señales hybrid y hydro quedan consultables; y que la
comparacion de dos corridas del mismo caso muestra KPIs, variante/rango y
diffs por periodo.

Tambien cubre regresiones que no deben romperse:

- TS-1: procedencia de topologia/parametros congelada en el snapshot.
- TS-2: catalogo editable de series sigue separado de los resultados.
- TS-3: variante, rango y bindings de series siguen apareciendo en lineage.
- Iteracion 3 a 6: run detail, charts, dashboards, publicaciones y portal
  cliente siguen leyendo superficies parciales con fallback por surface.

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

Ejecutar desde la raiz del repositorio. Editar `DB_PASSWORD` en `.env` para
que coincida con el rol local de PostgreSQL.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir:

```text
http://127.0.0.1:8000/
```

Si el puerto `8000` esta ocupado, usar otro puerto con `--port 8001` y ajustar
la URL de revision.

## Datos De Prueba

| Tipo | Valor sugerido |
| --- | --- |
| Project | `TS-4 Manual Check` |
| Scenario | `Indexed results` |
| Baseline run | Corrida indexada del mismo caso |
| Candidate run | Segunda corrida indexada con otra variante/rango |
| Legacy run | Corrida historica exitosa sin indices TS-4 |
| Hydro run | Corrida hydro-only o hydraulic-diagram con `dispatch.csv` hydro |

## Flujo Feliz: Indexacion Y Lectura BBDD-First

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Ejecutar una corrida exitosa de un caso hybrid con grid, bateria, carga y renovable. | La corrida queda `succeeded`, artifacts registrados y sin cambio en el flujo normal de run. | Pendiente |
| 2 | Abrir detalle/resultados de la corrida. | La tabla de dispatch, asset dispatch, summary y charts cargan normal. | Pendiente |
| 3 | Revisar BBDD o endpoint interno correspondiente. | Existen indices TS-4 para `dispatch`, `asset dispatch` y `summary` ligados al `run_id` y `scenario_version_id`. | Pendiente |
| 4 | Confirmar signal families indexadas para hybrid. | Aparecen grid import/export, precios, market value, carga, renovable, costos y BESS. | Pendiente |
| 5 | Confirmar asset dispatch indexado. | La tabla de assets muestra al menos filas separadas para grid, battery y renewable. | Pendiente |
| 6 | Eliminar temporalmente `dispatch.csv`, `asset_dispatch.csv` o `summary.json` de una corrida ya indexada. | La vista sigue cargando desde BBDD sin regression visible. | Pendiente |

## Legacy Fallback Y Rebuild

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir una corrida historica exitosa que aun no tenga indices TS-4. | La vista sigue cargando desde artifacts. | Pendiente |
| 2 | Invocar `POST /api/admin/runs/{run_id}/rebuild-results` para esa corrida. | Respuesta `indexed` o equivalente; se crean indices TS-4 para superficies disponibles. | Pendiente |
| 3 | Eliminar temporalmente los artifacts de esa corrida ya reconstruida. | La vista vuelve a cargar desde BBDD y mantiene summary/tablas. | Pendiente |
| 4 | Volver a correr rebuild sobre corrida ya reconstruida. | El proceso converge sin duplicados ni corrupcion; se reporta `skipped` o reindex limpio. | Pendiente |

## Hydro, Lineage Y Comparacion

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Ejecutar o reconstruir una corrida hydro-only. | Se indexan `total_hydro_power_mw`, inflow, turbine flow, spill, storage y elevation/terminal value si existen. | Pendiente |
| 2 | Abrir una corrida indexada generada desde variante TS-3. | El lineage muestra variante, rango y contexto congelado del snapshot, no estado mutable actual. | Pendiente |
| 3 | Abrir `Comparar corridas` para dos runs indexados del mismo caso. | La vista muestra contexto lado a lado, KPIs y selector de series. | Pendiente |
| 4 | Elegir una serie indexada (por ejemplo `grid_import_power_mw`). | La tabla periodo-a-periodo muestra baseline/candidate/delta y usa `null` cuando un lado no tiene ese timestamp. | Pendiente |
| 5 | Intentar comparar dos runs de casos distintos. | La API/UI responde error controlado indicando que deben pertenecer al mismo caso. | Pendiente |
| 6 | Intentar comparar un run aun no indexado. | La API/UI responde error controlado apuntando al endpoint `rebuild-results`. | Pendiente |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Run results | Tablas, summary y charts cargan igual con y sin artifacts cuando existe indice. | Pendiente |
| Asset dispatch | Filas por asset siguen legibles y consistentes. | Pendiente |
| Provenance / lineage | Variante y rango se leen claramente cuando existen. | Pendiente |
| Comparison view | KPIs, series selector y diff por periodo son legibles y no confunden baseline/candidate. | Pendiente |
| Responsive | Run results y comparison siguen utilizables en viewport angosto. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia de
aceptacion de TS-4.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts4_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Desde `frontend/`:

```powershell
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

TS-4 solo lee resultados luego de una corrida exitosa. Ejecutar Julia solo si
un cambio posterior toca comportamiento del optimizador, `system_case_json` o
formatos de artifacts:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Cierre TS-4

Antes de aceptar la iteracion, ejecutar la suite automatizada enfocada, la
suite Python completa y la verificacion frontend:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts4_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
cd frontend
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

Julia no es requerida para este cierre salvo que el cambio haya tocado
contratos Julia, comportamiento del optimizador o formatos de artifacts.

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Indexacion dispatch hybrid | Pendiente | |
| Indexacion asset dispatch | Pendiente | |
| Indexacion summary KPI | Pendiente | |
| Lineage congelado | Pendiente | |
| Idempotencia / reindex | Pendiente | |
| Fallback a artifacts | Pendiente | |
| Rebuild historico | Pendiente | |
| Cobertura hydro | Pendiente | |
| Comparacion baseline/candidate | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
