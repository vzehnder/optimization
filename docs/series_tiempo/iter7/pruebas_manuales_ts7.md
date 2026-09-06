# Pruebas Manuales TS-7

## Objetivo

Checklist manual del cierre de TS-7: catalogo global signal-first de series
genericas, series especificas por objeto, y el recorrido protegido unico por el
que pasa toda mutacion. El foco son los tres flujos completos que exige la
definicion de hecho del capitulo 11.8:

1. vincular una fuente generica a un objeto y usar su revision en una variante;
2. crear una serie especifica desde el objeto y cargarla hasta sellar su
   revision;
3. intentar la carga compartida desde el objeto y recorrer **sus dos salidas**:
   la copia local derivada y `Publicar para todos`.

Tambien cubre las regresiones que no deben romperse:

- TS-2: catalogo generico de sets y sus lecturas conservan su forma.
- TS-3: variantes, bindings y validacion stale fail-closed.
- TS-4: indexacion de resultados y comparacion de corridas.
- TS-5: adaptador hidraulico legacy y su migracion bajo demanda.
- TS-6: transformaciones, conectores y automatizacion.

## Registro De Prueba

| Campo | Valor |
| --- | --- |
| Fecha | 2026-09-06 |
| Tester | Cuenta de verificacion de `.env` (`MAIL_USUARIO_TEST`) |
| Rama/commit | `series_tiempo`, cierre TS7-023 |
| Navegador | Chrome (Chrome DevTools MCP) |
| URL local | `http://127.0.0.1:8011/` |
| Resultado general | Aprobado, sin mensajes de consola |

## Preparacion Local

Ejecutar desde la raiz del repositorio. Las credenciales son las reales de
`.env` (`MAIL_USUARIO_TEST` y `PASSWORD_MAIL_USUARIO_TEST`): **no se crean
administradores de prueba ni se desactiva la autenticacion**.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend; npm run build; cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8011
```

Abrir `http://127.0.0.1:8011/` e iniciar sesion con la cuenta de `.env`.

Antes del cutover C6, la superficie canonica se abre **solo** para las cuentas
de verificacion (capitulo 11.1). `MAIL_USUARIO_TEST` es una de ellas, asi que
la pestana `Catalogo` y las rutas del objeto y del recorrido estan disponibles;
con cualquier otra identidad interna esas rutas responden como si no
existieran, que es exactamente lo que debe verse.

## Datos De Prueba

El catalogo es global, asi que el recorrido necesita un objeto y una senal
generica en el mismo alcance. El pase de TS7-023 uso un proyecto propio:

| Elemento | Valor del pase |
| --- | --- |
| Proyecto | `TS7-023 verificacion` (id 896) |
| Objeto vinculable | `Sistema TS7-023` (id 975, `global:system`) |
| Escenario y variante | `Plan base TS7-023` (785), variante `Default` (756) |
| Fuente generica | `Precio de energia TS7-023` (`energy_price`, set 921, revision 914) |

## Flujo 1: Vincular Una Fuente Generica (H-01 a H-07)

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abrir `Catalogo` y buscar por texto, tipo, clase, unidad, alcance y estado. | Una fila por senal, con propietario, alcance, contrato, cobertura y resolucion visibles; paginacion por cursor. | Aprobado |
| 2 | Abrir una senal del listado. | Detalle con contrato, procedencia, revision vigente y hash; no descarga puntos. | Aprobado |
| 3 | Pedir un preview acotado de una revision exacta. | Muestra normalizada que cita la revision consultada; sobre el limite responde `TS_PREVIEW_TOO_LARGE` en vez de truncar. | Aprobado |
| 4 | Desde el objeto, `Asociar fuente al objeto`; elegir necesidad `Grid Import Price` y `Reutilizar una fuente generica`. | El riel muestra los cuatro pasos fijos; el alcance queda `Fuente generica compartida`. | Aprobado |
| 5 | Revisar la lista de candidatas del paso 2. | La compatible es seleccionable; cada incompatible aparece explicada y bloqueada con su codigo estable (`TS_COMPAT_SCOPE_NOT_ACCESSIBLE`, `TS_COMPAT_SEMANTIC_TYPE_NOT_ALLOWED`, `TS_COMPAT_DIMENSION_MISMATCH`, `TS_COMPAT_UNIT_MISMATCH`). | Aprobado |
| 6 | Avanzar al paso 3 y luego al 4, y confirmar. | El paso 3 muestra fuente, revision observada, hash y cobertura; el paso 4 muestra prevalidacion por fila, consumidores, permisos, staleness, atomicidad e historia. Al confirmar: `Guardado atomico completo (created)` con su lote `asb_...`. | Aprobado |
| 7 | Volver al objeto y usar `Usar revision en una variante`; elegir escenario, variante y la misma fuente. | El paso 3 fija revision y hash exactos; al confirmar aparece el lote `bnb_...`. | Aprobado |
| 8 | Revisar el resumen del objeto. | La fila generica dice `Asociada al objeto` y `Usada en Default - revision N - hash ...`. | Aprobado |

## Flujo 2: Crear Y Cargar Una Serie Especifica (H-08 a H-11)

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Desde el objeto, `Asociar fuente al objeto` y elegir `Crear especifica para este objeto`. | El paso 2 muestra el formulario de definicion, encabezado por `Solo este objeto`. | Aprobado |
| 2 | Completar clave local, nombre, tipo semantico, unidad, clase de dato, zona horaria y resolucion; avanzar. | El paso 3 ofrece `Guardar definicion`. | Aprobado |
| 3 | Presionar `Guardar definicion`. | La serie queda creada en estado `awaiting_data` y **no seleccionable**: "No, aun sin revision sellada". Guardar solo la definicion ya es valido. | Aprobado |
| 4 | Pegar los puntos (instante ISO, duracion en segundos, valor) y presionar `Validar datos`. | Lote `ready_to_publish` con periodos normalizados, cobertura y hash propuesto; el contenido se valida en staging antes de publicar. | Aprobado |
| 5 | Avanzar al paso 4, escribir el motivo y `Publicar revision de esta serie`. | `Revision sellada (new_revision)` con el mismo hash que mostro el staging. | Aprobado |
| 6 | Repetir la carga por API o por archivo sobre la misma serie. | Cada publicacion sella una revision nueva y **no reasigna la identidad**; el historial conserva las anteriores. | Aprobado |
| 7 | Vincular la serie especifica a su propio objeto desde `Usar revision en una variante`. | El binding se crea sin ninguna asociacion de catalogo intermedia. | Aprobado |
| 8 | Buscar la serie en `Catalogo` con cualquier combinacion de filtros. | Nunca aparece en `catalog/inputs` ni como candidata de otro objeto. | Aprobado |
| 9 | Archivar la serie especifica. | Conserva historia, revisiones y bindings pasados; deja de ser seleccionable. | Aprobado |

## Flujo 3: Carga Compartida Desde El Objeto, Con Sus Dos Salidas (H-12 a H-14)

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Desde una fuente generica asociada al objeto, abrir el recorrido con intencion `update_shared`. | El paso 1 pregunta **para quien es el cambio** antes de tocar nada. | Aprobado |
| 2 | Declarar `Solo este objeto necesita otra curva`. | El paso 2 muestra alcance, propietario, revision vigente con hash, asociaciones, otros objetos y proyectos, y cuantos bindings quedaran obsoletos. La alternativa local se ofrece **primero**. | Aprobado |
| 3 | Elegir `Crear especifica para este objeto`, dar clave y nombre, y prevalidar. | Muestra la revision de origen, los periodos copiados y `0 asociaciones y 0 bindings: ninguna se mueve`. | Aprobado |
| 4 | Confirmar con motivo. | `Operacion completa (derived)`: identidad local con linaje, sin tocar la fuente compartida ni reasignar nada. | Aprobado |
| 5 | Repetir el recorrido declarando `Todos los consumidores deben ver la curva nueva`. | Ahora `Publicar para todos` se ofrece primero: el orden sigue la intencion declarada. | Aprobado |
| 6 | Cargar los puntos y `Preparar y previsualizar`. | Preview de la revision preparada con cobertura, hash propuesto y validacion sin errores. | Aprobado |
| 7 | En el paso 4, intentar confirmar sin motivo o sin marcar la comprension. | La accion queda deshabilitada; por API responde `TS_SHARED_REVISION_CONFIRMATION_REQUIRED`. | Aprobado |
| 8 | Dar motivo, marcar la comprension y `Publicar para todos`. | `Operacion completa (published)`. La accion nunca se rotula `Guardar` ni `Actualizar`. | Aprobado |
| 9 | Volver al resumen del objeto y a la variante. | El binding queda `Obsoleta` con `Ejecucion bloqueada`, sigue fijado a su revision anterior y la publicacion **no lo resuelve sola**. | Aprobado |
| 10 | Como `analyst` (no admin) intentar publicar sobre una fuente `global`. | Responde `TS_SHARED_REVISION_ADMIN_REQUIRED`. | Aprobado |

## Alcance, Seguridad Y Legacy (H-15, H-16)

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 (admin) | Promover un set a `global` tras ver su impacto. | Cambia la misma fila y conserva `owner_project_id`, revisiones, asociaciones e historia. | Aprobado |
| 2 (analyst) | Intentar promover o despromover. | `TS_SCOPE_ADMIN_REQUIRED`. | Aprobado |
| 3 (admin) | Despromover con consumidores de otro proyecto. | Falla cerrada y enumera el impacto; el set sigue `global`. | Aprobado |
| 4 (admin) | Repetir un cambio ya efectivo. | `TS_SCOPE_ALREADY_EFFECTIVE`, sin escribir. | Aprobado |
| 5 (external) | Entrar con una identidad `external` a cualquier ruta del catalogo, del objeto, de valores, asociaciones o bindings. | Responde igual que si no existieran: la superficie global refusa antes de resolver ids, y la del objeto y la variante contestan como si la fila no estuviera. Conocer un id real no cambia la respuesta. | Aprobado |
| 6 | Revisar las series hidraulicas legacy. | Siguen visibles por adaptador con su estado de migracion; ningun descriptor de resultado aparece en `catalog/inputs`. | Aprobado |

## Regresion Manual

| Paso | Accion | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Recorrer el catalogo de sets de TS-2 y sus revisiones. | Misma forma de siempre, ahora servida por el escritor canonico. | Aprobado |
| 2 | Correr la variante default de un escenario existente. | Flujo identico a TS-3: valida, materializa, corre. | Aprobado |
| 3 | Editar una serie enlazada y reintentar la corrida. | Rechazada por stale hasta revalidar (fail-closed intacto). | Aprobado |
| 4 | Comparar dos corridas y abrir la consola de configuracion. | Comportamiento observable sin cambios. | Aprobado |
| 5 | Abrir una corrida antigua. | Sigue legible con resultados e historial intactos. | Aprobado |

## Revision Visual

| Componente | Verificacion | Estado |
| --- | --- | --- |
| Catalogo global | Fila por senal con propietario y alcance; filtros combinables; paginacion por cursor. | Aprobado |
| Recorrido protegido | Riel de cuatro pasos fijo en los tres flujos; ninguna mutacion fuera de el. | Aprobado |
| Candidatas bloqueadas | Razon legible **y** codigo estable juntos, nunca uno sin el otro. | Aprobado |
| Resumen del objeto | `Solo este objeto` en cada serie especifica; `Sin asociacion de catalogo`; uso exacto en variantes con revision y hash. | Aprobado |
| Estados stale | `Obsoleta` y `Ejecucion bloqueada` visibles y no resueltos solos. | Aprobado |
| Consola del navegador | Sin errores ni advertencias durante los tres flujos. | Aprobado |

## Verificacion Automatizada Complementaria

Matriz completa, modulo por modulo, sobre PostgreSQL:

```powershell
$env:POSTGRES_TEST_DATABASE_URL = "postgresql://<user>:<pass>@127.0.0.1:5432/energy_dispatch_ts7_acceptance"
.\.venv\Scripts\python.exe -m unittest tests.test_ts7_acceptance -v
```

Suite completa de Python y puertas del frontend:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts1_acceptance tests.test_ts2_acceptance ... tests.test_ts7_acceptance
cd frontend; npm test -- --run; npx tsc -b; npx eslint .; npm run api:check; npm run build
```

Fixture de rendimiento con sus planes guardados:

```powershell
.\.venv\Scripts\python.exe scripts\ts7_catalog_performance_fixture.py --scale 0.001 --repetitions 100 --keep `
  --database-url postgresql://<user>:<pass>@127.0.0.1:5432/energy_dispatch_ts7_performance
```

El detalle de la ejecucion de cierre esta en
[`acceptance_ts7.md`](acceptance_ts7.md).
