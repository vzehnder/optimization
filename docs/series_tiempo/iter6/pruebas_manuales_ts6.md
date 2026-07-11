# Pruebas Manuales TS-6

## Objetivo

Este archivo sirve como checklist manual para revisar el cierre de TS-6:
transformaciones declarativas allowlisted, ingesta por conector externo y
automatizacion de reruns programados sobre el modelo comun de series. El foco
es comprobar que cada transformacion allowlisted produce un set derivado con
lineage completo sin mutar su origen; que un cambio en el origen marca el set
derivado como desactualizado y la regeneracion crea una nueva revision sin
reescribir historia; que los datos externos (forecast y programas oficiales)
entran por el mismo camino source/set que un archivo, con emisor y vigencia
por revision; y que los reruns programados (rango fijo y rolling horizon)
producen los mismos snapshots inmutables e indices de resultados que una
corrida manual, con fallas de gate visibles.

Tambien cubre regresiones que no deben romperse:

- TS-1: procedencia de topologia/parametros congelada en el snapshot.
- TS-2: catalogo generico de series sigue siendo la fuente editable.
- TS-3: variantes, bindings y stale validation fail-closed siguen
  funcionando, incluso con sets derivados de por medio.
- TS-4: indexacion de resultados y comparacion de corridas siguen
  funcionando, ahora tambien para corridas programadas.
- TS-5: adaptadores legacy, permisos y retencion no cambian.

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
| Project | `TS-6 Manual Check` |
| Set base | CSV horario con demanda y precio (24 periodos) |
| Set con gap | CSV horario con 1 hora faltante |
| Sets para combinar | Un set solo-precio y un set solo-demanda con horizonte comun |
| API externa fake | Servidor JSON local (por ejemplo `http://127.0.0.1:8766/forecast.json`) |
| Scenario para automation | Escenario one-bus con variante default validada |

## Transformaciones Allowlisted

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | En el detalle de un set del catalogo, abrir el panel "Transformaciones". | Solo aparecen los tipos allowlisted (`scale_signal`, `resample`, `interpolate_gaps`); no hay campo de script libre. | Pendiente |
| 2 | Aplicar `scale_signal` (factor 2.0) sobre una senal. | Se crea un set derivado (`data_kind = derived`) con la senal duplicada y las demas intactas; el set origen no cambia (mismo content_hash). | Pendiente |
| 3 | Revisar el panel "Lineage de transformacion" del set derivado. | Muestra tipo, version de implementacion, version de schema, parametros validados y el input (set id, revision, hash, senales). | Pendiente |
| 4 | Aplicar `resample` a resolucion 2h con metodo `mean`. | Set derivado con la mitad de periodos y valores promediados; validacion rechaza upsampling o resoluciones que no dividen. | Pendiente |
| 5 | Aplicar `interpolate_gaps` (`linear`, max gap 2h) al set con gap. | Set derivado con el periodo faltante rellenado, fila destacada con badge "interpolado"; el origen conserva el gap. | Pendiente |
| 6 | Repetir la interpolacion con `max_gap_hours` menor al gap real. | Error visible nombrando el rango del gap y las senales; no se escribe nada. | Pendiente |
| 7 | En el catalogo del proyecto, usar "Combinar series" con los dos sets de horizonte comun. | Set derivado con ambas senales; con un tercer set sin horizonte comun el error nombra los sets en conflicto y no escribe nada. | Pendiente |
| 8 | Volver a aplicar la misma transformacion con identicos parametros. | Converge al mismo set derivado (no se duplica). | Pendiente |

## Staleness Y Regeneracion De Sets Derivados

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Editar un valor del set origen de un derivado. | El derivado muestra badge "Desactualizado" en el catalogo y banner con la razon en su detalle. | Pendiente |
| 2 | Con una variante enlazada al derivado stale, intentar materializar/correr. | Rechazado (fail-closed) hasta resolver el staleness. | Pendiente |
| 3 | Presionar "Regenerar set derivado". | Nueva revision del mismo set (no un set nuevo) con valores recalculados y lineage actualizado; el badge/banner se limpia. | Pendiente |
| 4 | Revisar el historial de revisiones del derivado. | La revision 1 conserva su content_hash original (historia inmutable). | Pendiente |
| 5 | Revalidar la variante y correr. | La corrida usa la nueva revision; corridas anteriores siguen apuntando al hash que consumieron. | Pendiente |

## Conector Externo (Forecast Y Programas)

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | En el catalogo del proyecto, usar "Ingesta de pronostico (conector externo)" contra la API fake. | Se crea un set `data_kind = forecast`, `status = validated`; la seccion "Origen" muestra conector, target, hora de fetch y cantidad de registros. | Pendiente |
| 2 | Re-ingerir sin cambios en la API. | Mensaje "Datos sin cambios"; misma revision, sin filas source duplicadas. | Pendiente |
| 3 | Cambiar un valor en la API fake y re-ingerir. | Nueva revision con nuevo hash; la revision 1 se conserva. | Pendiente |
| 4 | Ingerir con URL invalida (404). | Error visible `connector ... received HTTP 404`; no se escribe nada. | Pendiente |
| 5 | Ingerir marcando "Programa oficial" con emisor/emision/vigencia. | Set `data_kind = programmed`; catalogo y detalle muestran la linea "Programa oficial". | Pendiente |
| 6 | Re-emitir el mismo programa (valores identicos, nueva vigencia). | Nueva revision con el mismo content_hash; el historial muestra la vigencia propia de cada revision. | Pendiente |

## Reruns Programados (Rango Fijo)

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 (admin) | Crear un schedule (caso + variante + rango + cadencia) en la seccion de schedules. | El schedule aparece listado con su proximo disparo; nunca se pega un JSON de caso a mano. | Pendiente |
| 2 (analyst) | Intentar crear un schedule como analyst. | Rechazado (solo admin). | Pendiente |
| 3 (admin) | Ejecutar "run due" (o `scripts/run_due_schedules.py`) con un schedule vencido y datos validos. | Tick `queued` con run creado (`trigger_type = scheduled`); el schedule avanza su proximo disparo desde la hora due, no desde el reloj. | Pendiente |
| 4 | Revisar la corrida programada en el listado de runs y su detalle. | Aparece junto a las manuales, con nombre/id del schedule y tick id; el snapshot registra la variante, el rango y el lineage de automation. | Pendiente |
| 5 | Al completarse la corrida, revisar tablas/graficos. | Resultados indexados en BBDD igual que una corrida manual (TS-4). | Pendiente |
| 6 | Ejecutar "run due" con un schedule cuyo rango no tiene cobertura o cuya variante esta stale. | Tick `failed` visible con el motivo; no se crea run y el schedule sigue activo. | Pendiente |

## Rolling Horizon

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 (admin) | Crear un schedule `rolling` (offset y duracion en horas). | El listado muestra la regla de rango rolling, no un rango fijo. | Pendiente |
| 2 | Disparar dos ticks en dias consecutivos. | Cada tick resuelve su propio rango anclado en su hora due; el snapshot de cada corrida registra el rango concreto usado. | Pendiente |
| 3 | Dejar que el segundo tick caiga fuera de la cobertura de datos. | Falla visible en el historial de ticks; el schedule sigue activo y avanza. | Pendiente |

## Regresion Manual

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Con derivados y schedules existentes en el proyecto, correr la variante default manualmente. | Flujo identico a TS-3: valida, materializa, corre; el snapshot no tiene campos de automation. | Pendiente |
| 2 | Editar una serie enlazada y reintentar la corrida manual. | Rechazada por stale hasta revalidar (fail-closed intacto). | Pendiente |
| 3 | Revisar una corrida antigua (pre-TS-6). | Sigue legible con sus resultados e historial intactos. | Pendiente |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Panel de transformaciones | Selector de tipo y campos por transformacion legibles; errores de validacion visibles. | Pendiente |
| Panel de lineage | Parametros anidados legibles (sin `[object Object]`); inputs con set/revision/hash. | Pendiente |
| Catalogo | Badge "Desactualizado" en derivados stale; linea "Programa oficial" en sets programmed. | Pendiente |
| Valores interpolados | Filas rellenadas destacadas con badge "interpolado". | Pendiente |
| Schedules | Formulario fijo/rolling, historial de ticks con fallas visibles, lineage de schedule en el detalle del run. | Pendiente |
| Responsive | Catalogo, paneles de transformacion y seccion de schedules utilizables en viewport angosto. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia
de aceptacion de TS-6.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts6_acceptance -v
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

Julia no es requerida para este cierre salvo que el cambio haya tocado
contratos Julia, comportamiento del optimizador o formatos de artifacts
(TS-6 reutiliza el pipeline manual y materializa inputs por el contrato
existente, sin cambiarlo).

## Cierre TS-6

Antes de aceptar la iteracion, ejecutar la suite automatizada enfocada, la
suite Python completa y la verificacion frontend:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts6_acceptance -v
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

| Area | Resultado | Evidencia / notas |
| --- | --- | --- |
| Transformaciones allowlisted con lineage | Pendiente | |
| Staleness y regeneracion de derivados | Pendiente | |
| Conector externo forecast/programmed | Pendiente | |
| Reruns programados de rango fijo | Pendiente | |
| Rolling horizon con snapshots auditables | Pendiente | |
| Regresion de corridas manuales | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
