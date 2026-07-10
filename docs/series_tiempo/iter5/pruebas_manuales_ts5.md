# Pruebas Manuales TS-5

## Objetivo

Este archivo sirve como checklist manual para revisar el cierre de TS-5:
migracion, unificacion y hardening del modelo comun de topologia,
parametros, series y resultados. El foco es comprobar que la extraccion de
series embebidas de un draft legacy queda en el catalogo generico y se puede
enlazar a una variante; que las series hidraulicas legacy siguen leyendose
por el adaptador comun mientras las escrituras nuevas van al modelo generico;
que la migracion on-demand preserva metadata de origen y es idempotente; que
la validacion stale sigue fail-closed sin importar el origen del
almacenamiento; que el matriz de permisos se sostiene para analyst, admin y
client; y que el cleanup solo elimina indices reconstruibles, restaurables
via rebuild, sin tocar auditoria.

Tambien cubre regresiones que no deben romperse:

- TS-1: procedencia de topologia/parametros congelada en el snapshot.
- TS-2: catalogo generico de series sigue siendo la fuente editable.
- TS-3: variantes, bindings y stale validation siguen funcionando.
- TS-4: indexacion de resultados, fallback a artifacts y rebuild siguen
  funcionando para corridas antiguas.

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
| Project | `TS-5 Manual Check` |
| Scenario draft | Escenario con estructura one-bus y una fuente CSV mapeada |
| Scenario hidraulico | Escenario con diagrama v3 (reservoir + planta) |
| Legacy hydraulic set | Serie hidraulica sembrada antes de TS5-003 (o repair manual) |
| Run antiguo | Corrida exitosa sin indices TS-4 |

## Extraccion De Series De Draft Legacy

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir el editor estructurado de un draft con una fuente CSV ya mapeada. | El panel "Extract legacy series to catalog" aparece junto al de import mapeado, con nota de deprecacion apuntando al modelo comun. | Pendiente |
| 2 | Ejecutar la extraccion con nombre/version/timezone. | Se crea un `time_series_set` en el catalogo del proyecto con seccion "Origen legacy" mostrando draft, fuente y checksum. | Pendiente |
| 3 | Repetir la extraccion sobre la misma fuente sin cambios. | No se crea un set duplicado; misma revision, mismo id. | Pendiente |
| 4 | Enlazar el set extraido a una variante del caso. | La variante queda enlazada y valida (no stale). | Pendiente |
| 5 | Revisar el draft original. | El documento del draft no cambia (mismo `updated_at`). | Pendiente |

## Adaptador Hidraulico Legacy Y Escrituras Genericas

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Guardar una serie de afluente natural nueva en el diagrama hidraulico. | La serie queda con origen "generic"; no aparece en el listado de series hidraulicas legacy. | Pendiente |
| 2 | Revisar un set hidraulico legacy preexistente (sembrado antes de TS5-003). | Aparece en "Series hidraulicas (origen legacy)" con su signal/entity/periodo correctos. | Pendiente |
| 3 | Abrir el diagrama con ambos tipos de serie (una nativa, una legacy). | Cada nodo muestra su serie con el origen correcto; ambos coexisten sin colision. | Pendiente |

## Migracion On-Demand

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Migrar un set hidraulico legacy desde su pagina de detalle. | Se crea un set generico con origen `hydraulic_legacy_migration` (legacy id, version, hash, migrado por/cuando). | Pendiente |
| 2 | Recargar la pagina del set legacy. | Muestra "Ya migrado a `<link>`" sin necesidad de re-click. | Pendiente |
| 3 | Volver a migrar el mismo set. | Responde "ya migrado", apunta al mismo set generico, no duplica. | Pendiente |
| 4 | Revisar el diagrama hidraulico tras la migracion. | El nodo sigue leyendo la serie legacy original sin cambios (la migracion no reescribe el binding). | Pendiente |
| 5 (admin) | Ejecutar el barrido masivo "Migrar todas las series hidraulicas legacy". | Reporta migradas/ya migradas/fallidas; estable en una segunda ejecucion. | Pendiente |
| 6 (analyst) | Intentar el barrido masivo como analyst. | La accion es rechazada (solo admin). | Pendiente |

## Stale Validation Fail-Closed Entre Origenes

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Con una variante enlazada a un set extraido, materializar el caso. | Materializa correctamente, sin stale. | Pendiente |
| 2 | Editar un valor del set extraido. | La variante queda stale; un intento de materializar es rechazado. | Pendiente |
| 3 | Con un binding hidraulico migrado, repetir edicion. | Mismo comportamiento: stale y bloqueo hasta revalidar. | Pendiente |
| 4 | Editar topologia/parametros del draft (sin tocar series). | La variante queda stale por razon `parameters`, no `time_series_set`. | Pendiente |

## Matriz De Permisos

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 (client) | Intentar acceder al catalogo, adaptador hidraulico o variantes de un proyecto como client. | 403 en cada superficie, incluida la extraccion y la migracion. | Pendiente |
| 2 (analyst/admin) | Acceder a las mismas superficies como analyst y como admin. | Ambos ven el mismo contenido (paridad analyst/admin). | Pendiente |
| 3 (client) | Ver una publicacion publicada de un proyecto con acceso de cliente. | Ve la publicacion, pero no el catalogo ni los resultados crudos del mismo proyecto. | Pendiente |

## Cleanup Y Rebuild De Resultados

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir una corrida antigua exitosa sin indices TS-4. | Carga desde artifacts sin error. | Pendiente |
| 2 | Ejecutar `rebuild-results` sobre esa corrida (admin). | Queda indexada en BBDD. | Pendiente |
| 3 | Ejecutar `cleanup-results` sobre dispatch/asset/summary (admin). | Se eliminan los tres indices; artifacts y scenario version se conservan (razon "immutable audit data"). | Pendiente |
| 4 | Revisar la corrida tras el cleanup. | Sigue siendo legible (fallback a artifacts). | Pendiente |
| 5 | Repetir cleanup sobre la misma corrida. | Idempotente: reporta "already absent", sin error. | Pendiente |
| 6 | Ejecutar rebuild de nuevo. | Los indices vuelven a existir. | Pendiente |

## Inmutabilidad De Scenario Versions

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Intentar un `UPDATE` directo sobre una fila de `scenario_versions` (via consola/DB admin). | La base de datos rechaza el cambio (trigger de inmutabilidad). | Pendiente |
| 2 | Revisar la version tras el intento. | El contenido permanece identico al original. | Pendiente |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Draft editor | Panel de extraccion y nota de deprecacion legibles, sin colisionar con el panel de import mapeado. | Pendiente |
| Catalogo de proyecto | Series genericas y series hidraulicas legacy en secciones separadas y claras. | Pendiente |
| Detalle de set hidraulico | Estado de migracion visible sin necesidad de re-click. | Pendiente |
| Panel de metadata de version | "Nombre del caso" en vez de "Case", sin ambiguedad de cardinalidad. | Pendiente |
| Responsive | Catalogo, diagrama hidraulico y detalle de resultados siguen utilizables en viewport angosto. | Pendiente |

## Verificacion Automatizada Complementaria

Estas pruebas no reemplazan la revision manual, pero sirven como referencia
de aceptacion de TS-5.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts5_acceptance -v
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
contratos Julia, comportamiento del optimizador o formatos de artifacts (fue
ejecutada para las slices de escritura hidraulica BESS-TS5-003/004 durante su
implementacion).

## Cierre TS-5

Antes de aceptar la iteracion, ejecutar la suite automatizada enfocada, la
suite Python completa y la verificacion frontend:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts5_acceptance -v
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
| Extraccion de series de draft legacy | Pendiente | |
| Adaptador hidraulico legacy | Pendiente | |
| Escrituras hidraulicas genericas | Pendiente | |
| Migracion on-demand idempotente | Pendiente | |
| Stale validation entre origenes | Pendiente | |
| Matriz de permisos analyst/admin/client | Pendiente | |
| Cleanup y rebuild de resultados | Pendiente | |
| Inmutabilidad de scenario versions | Pendiente | |
| Revision visual/responsive | Pendiente | |

Decision final:

```text
Aceptado / Rechazado / Aceptado con observaciones
```
