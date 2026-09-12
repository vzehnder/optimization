# Guia Del Analista: Primeros Pasos Con BESS Workspace

Audiencia: analistas con experiencia en herramientas de optimizacion
(formulacion LP/MIP, solvers, analisis de escenarios, series de tiempo) pero
sin experiencia previa con esta aplicacion en particular.

Objetivo: al terminar esta guia deberias poder crear un proyecto, modelar un
caso one-bus, cargar series de tiempo, correr la optimizacion, revisar
resultados, comparar corridas, configurar una consola de operador y entregar
resultados a un usuario externo.

Si buscas un recorrido paso a paso, pantalla por pantalla, el documento
complementario es `docs/tutorials/manual_completo_uso_pagina_web.md`. Esta guia
explica el modelo mental; el manual detalla la operacion.

## 1. Que Es Esta Herramienta

BESS Workspace es una aplicacion web privada para modelar y optimizar el
despacho economico de sistemas hibridos (BESS, solar, eolica, hidraulica con
regulacion y demanda local) conectados a un unico punto de conexion (PCC).

Puntos clave para ubicarse rapido:

- **El motor matematico es Julia (JuMP + HiGHS)**. La web no reimplementa la
  formulacion: genera un contrato `system_case.json`, lo valida y ejecuta el
  CLI de Julia como proceso externo. Los outputs (`dispatch.csv`,
  `asset_dispatch.csv`, `summary.json`, `model_metadata.json`) son
  reproducibles y auditables.
- **El alcance electrico es intencionalmente acotado**: un solo bus, sin
  flujo de red, sin lineas ni perdidas. Es una herramienta de despacho de
  recursos co-ubicados, no un simulador electrico general.
- **Todo es trazable**. Cada corrida apunta a un snapshot inmutable que
  registra exactamente que topologia, parametros y revisiones de series
  consumio. La aplicacion prefiere fallar antes que correr con datos
  desactualizados (politica *fail-closed*).
- **Los datos de series viven en un modelo canonico unico**. Desde el cutover
  de TS-7 existe un solo escritor de series de tiempo: las rutas antiguas
  siguen respondiendo, pero por debajo publican en el catalogo canonico, y
  toda mutacion queda registrada en libros de auditoria inmutables
  (seccion 6.2).
- **Hay tres superficies distintas sobre el mismo motor**: el workspace del
  analista, la consola de operador (entrada acotada y ejecucion) y el portal
  externo (solo lectura). Cada usuario aterriza en la que le corresponde; no
  son vistas del mismo menu (seccion 3).

## 2. El Modelo Mental

Antes de tocar la UI conviene entender la jerarquia de objetos. Todo el
trabajo se ordena asi:

```text
Proyecto
  -> Escenario (caso de optimizacion, editable)
       -> Draft (documento editable del modelo)
       -> Variante de entrada (bindings a revisiones exactas del catalogo)
            -> Rango de fechas (elegido al correr)
                 -> Version inmutable (snapshot ejecutable)
                      -> Corrida (queued/running/succeeded/failed)
                           -> Resultados, dashboards
                                -> Publicacion read-only
       -> Consola de operador (variante clonada + superficie acotada)

Proyecto
  -> Catalogo de series de tiempo (sets versionados del proyecto)
  -> Objetos vinculables (grid, load, renewable, battery, hydro, nodos,
     tramos, plantas y unidades hidraulicas)
       -> Asociacion a una fuente del catalogo canonico
       -> Series especificas del objeto
  -> Configuracion del portal (que ve el usuario externo)

Catalogo canonico global
  -> Fuentes genericas compartidas entre proyectos (alcance global)
```

Conceptos que no debes confundir:

| Concepto | Que es | Mutable? |
| --- | --- | --- |
| Escenario / caso | El modelo editable (topologia, parametros, solver). | Si |
| Draft | El documento de trabajo del editor estructurado. | Si |
| Set de series | Un conjunto versionado de senales con horizonte comun. | Solo agregando revisiones |
| Objeto vinculable | Un componente del caso al que se le cuelgan series. | Su registro sigue al modelo |
| Asociacion | Que fuente del catalogo puede alimentar a un objeto. | Si, con motivo y auditoria |
| Variante de entrada | Un juego nombrado de referencias caso-a-series. | Si (sus bindings) |
| Binding | El uso de una **revision exacta** en una variante. | Se reemplaza, no se edita |
| Version inmutable | Snapshot congelado listo para ejecutar. | No, nunca |
| Corrida (run) | Una ejecucion del solver sobre una version. | No (solo su estado) |
| Consola de operador | Superficie acotada configurada por el analista. | Su configuracion si |
| Configuracion de portal | Que resultados ve el usuario externo. | Si, por revisiones |

Regla de oro: **las corridas nunca leen datos "en vivo"**. Al correr, la
aplicacion materializa las series de la variante en el rango elegido, congela
todo en una version inmutable y ejecuta eso. Si despues editas una serie, las
corridas viejas siguen apuntando al hash exacto que consumieron.

Segunda regla, la que trajo el modelo canonico: **asociar y usar son dos actos
distintos y sucesivos**. Asociar declara que una fuente es valida para un
objeto; usar una revision declara que *esa* revision entra en una variante.
Nada se propaga solo desde la primera hacia la segunda.

## 3. Puesta En Marcha

Requisitos locales: Python con el venv del repo, PostgreSQL corriendo con las
credenciales de `.env` (variable `DB_PASSWORD`), y Julia disponible si vas a
ejecutar corridas (sin Julia puedes modelar y validar datos, pero las
corridas fallaran).

Desde la raiz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir en el navegador:

```text
http://127.0.0.1:8000/
```

Si el puerto 8000 esta ocupado, agregar `--port 8001` y ajustar la URL.

### Sesion, roles y capacidades

La primera vez que la aplicacion arranca sin usuarios te pedira crear la
cuenta inicial (bootstrap de admin). Despues, el login es correo + password.

Hay tres roles:

- `analyst`: crea y edita proyectos, modelos, series; configura consolas y el
  portal; corre y publica.
- `admin`: todo lo anterior, mas gestion de usuarios, capacidades externas por
  proyecto, cambios de alcance de sets, schedules de corridas automaticas y
  operaciones masivas.
- `external`: no ve nada del workspace. Solo alcanza lo que se le habilito
  explicitamente, proyecto por proyecto, mediante dos capacidades
  independientes:
  - `portal_view`: portal de resultados read-only (seccion 10).
  - `operate`: consola de operador (seccion 11).

El rol `client` de iteraciones anteriores fue retirado. Si vienes de esa
version, el equivalente actual es un usuario `external` con `portal_view` en
los proyectos que le correspondan.

### Las tres raices de la aplicacion

La UI React se sirve bajo `/react` y esta partida en tres raices que no
comparten navegacion:

| Raiz | Quien entra | Que hay |
| --- | --- | --- |
| Analista (`/projects`, `/time-series/...`, `/admin`) | `analyst`, `admin` | Todo el workspace. |
| Consola (`/console`) | `external` con `operate`; tambien internos, para probar | Consolas operables. |
| Portal (`/client`) | `external` con `portal_view` | Publicaciones configuradas. |

**El aterrizaje lo decide el backend, no el navegador.** Al iniciar sesion el
servidor calcula `landing_path` y la UI lo obedece: un interno cae en
`/projects`; un externo con `operate` cae en su consola (directamente en ella
si tiene una sola) y, sin `operate`, en el portal. Entrar a una raiz que no te
corresponde muestra una pantalla que lo dice y ofrece volver, no un error.

La barra superior muestra tu identidad y rol. La navegacion del analista es
**Proyectos**, **Administración** si corresponde, y **Catálogo de series** si
tu cuenta tiene habilitada la lectura canonica (seccion 6.2). **Estado del
sistema** se encuentra dentro de **Utilidades**.

## 4. Crear Proyecto Y Escenario

1. En **Proyectos** (`/projects`), usar el formulario **Nuevo proyecto** y
   presionar **Crear proyecto**.
2. Entrar al proyecto. **Escenarios** contiene la lista y el formulario de
   creación; **Datos**, el catálogo del proyecto; **Informes**, el portal y
   las plantillas; **Consolas**, enlaces a los escenarios. **Accesos** aparece
   solo para admin y permite gestionar capacidades externas.
3. Crear un escenario con **Nuevo escenario** -> **Crear escenario**. Un
   escenario es un caso de optimizacion: conviene uno por configuracion de
   sistema que quieras estudiar (las alternativas de *datos* no requieren
   escenarios nuevos; para eso estan las variantes, seccion 7).

El escenario abre en **Resumen**, con su contexto y una acción para crear o
continuar el modelo según la consulta al servidor. **Modelo** abre el editor;
**Datos** contiene variantes, fuentes y período; **Ejecuciones**, corridas y
comparación; **Avanzado**, JSON experto, versiones, diagrama hidráulico y
**Consolas de operador** (seccion 11). La sección queda en la URL y los campos
pendientes se conservan al alternar secciones de la misma pantalla.

## 5. Modelar El Caso: El Draft

Dentro del escenario, presionar **Modelo** o **Crear modelo** si aún no existe.
El editor es estructurado
(formularios y tablas, no un canvas libre) y trabaja sobre un documento
borrador que solo se convierte en algo ejecutable cuando tu lo decides.

Secciones del editor:

- **Caso**: nombre, descripcion y metadatos generales. El campo **Draft
  schema** (`bess_editor_draft.v1`) es la version del formato del documento:
  no lo edites; si cambia, el backend rechaza el draft.
- **Graph, grid y solver**: definicion del PCC y la red (limites de
  importacion/exportacion, anti-simultaneidad opcional, precios de compra y
  venta separados) y configuracion del solver (HiGHS por defecto).
- **Assets**: lista de activos conectados al bus. Tipos soportados:
  - `battery`: potencia de carga/descarga, energia min/max, energia inicial,
    eficiencias, condicion terminal, degradacion lineal por movimiento de
    SOC, anti-simultaneidad opcional.
  - `renewable` (solar/eolica): generacion con disponibilidad exogena por
    periodo, curtailment permitido con penalizacion opcional.
  - `load`: demanda local.
  - `hydro`: activo despachable con stock intertemporal (tipo bateria con
    afluentes naturales), vertimiento y valor de agua opcionales.
- **Time-series metadata**: metadatos de las series que el caso espera.

Acciones importantes:

- **Guardar draft**: persiste el documento (hay aviso si intentas salir con
  cambios sin guardar).
- **Generar preview**: muestra el `system_case` que se generaria desde el
  draft, para inspeccionarlo antes de comprometerte.
- **Validar con Julia**: corre la validacion del contrato contra el motor
  real sin ejecutar la optimizacion. Usalo temprano y seguido.

Para casos con hidrologia compleja existe ademas el **editor de diagrama
hidraulico** (desde el escenario): nodos, tramos, curvas cota-volumen,
afluentes por nodo y caudales minimos por tramo. Si tu caso es one-bus
simple, puedes ignorarlo.

Cada componente que declaras aqui queda registrado como **objeto vinculable**:
la unidad a la que se le cuelgan series en el modelo canonico. Los tipos
registrados son `component:grid`, `component:load`, `component:renewable`,
`component:battery`, `component:hydro`, los objetos hidraulicos
(`hydraulic_system`, `hydraulic_node`, `hydraulic_reach`, `hydraulic_plant`,
`hydraulic_unit`) y `global:system` para las senales de sistema, como los
precios.

## 6. Cargar Series De Tiempo: El Catalogo

Cada proyecto tiene un **catalogo de series de tiempo**: sets versionados
guardados en base de datos, compartidos por todos los escenarios del
proyecto. Un *set* agrupa una o mas senales sobre un horizonte comun de
periodos con resolucion homogenea y zona horaria explicita.

Caminos de entrada de datos:

1. **CSV desde el draft** (el camino principal): en el editor de draft, la
   seccion *Time-series source* permite subir un CSV, previsualizarlo,
   mapear columnas a senales del catalogo canonico (*Column mapping*),
   corregir filas puntuales (*Editable rows*) e importarlo al catalogo
   (*Import mapped columns to catalog*).
2. **Conector externo** (panel *Ingesta de pronostico* en el catalogo):
   trae datos de una API HTTP JSON configurable. El resultado entra igual
   que un archivo: un set `forecast` o, si lo marcas como **Programa
   oficial**, un set `programmed` con emisor y vigencia por revision.
3. **Derivados por transformacion** (seccion 6.1).
4. **Series especificas de un objeto**, creadas y cargadas desde el recorrido
   protegido (seccion 6.2).
5. **Migracion de series hidraulicas legacy** (solo si vienes de datos
   creados con el editor hidraulico antiguo). El adaptador sigue vigente y su
   migracion bajo demanda ahora publica en el modelo canonico.

Las senales canonicas que un caso puede requerir son, entre otras:
`import_price_usd_per_mwh` / `export_price_usd_per_mwh` (precios de red),
`load_demand_mw` (demanda), `renewable_available_power_mw` (disponibilidad
renovable), `natural_inflow_m3s` (afluentes por nodo hidraulico) y
`minimum_flow_m3s` (caudal minimo por tramo).

Versionado: editar valores a mano o reemplazar el archivo de un set **no
sobreescribe nada**: crea una nueva *revision* con nuevo `content_hash`. El
historial de revisiones es inmutable; las corridas viejas siguen apuntando a
la revision que usaron.

Nota tecnica: estas pantallas conservan su forma, pero desde el cutover
escriben en el modelo canonico. Las respuestas de las rutas antiguas anuncian
su deprecacion y su sucesor, y las escrituras exigen `If-Match` e
`Idempotency-Key`, de modo que un reintento no puede crear una segunda
revision.

### 6.1 Transformaciones y combinacion

En el detalle de un set, el panel **Transformaciones** ofrece un allowlist
cerrado (no hay scripts libres):

- `scale_signal`: escala una senal por un factor.
- `resample`: baja la resolucion (por ejemplo 1h -> 2h) con un metodo
  explicito; el upsampling se rechaza.
- `interpolate_gaps`: rellena huecos pequenos (lineal, con maximo de horas
  configurable); las filas rellenadas quedan marcadas con badge
  "interpolado".
- **Combinar series** (panel del catalogo): une senales de varios sets con
  horizonte comun en un set nuevo.

Toda transformacion produce un **set derivado** (`data_kind = derived`) con
lineage completo (tipo, version de implementacion, parametros, inputs con
set/revision/hash); el set origen no se toca. Si el origen cambia despues,
el derivado se marca **Desactualizado** en el catalogo y el detalle ofrece
**Regenerar set derivado**, que agrega una revision nueva al mismo set.

Regla importante heredada del diseno: **en tiempo de corrida no hay
resampling ni relleno implicito, nunca**. Si tus datos tienen resolucion
mixta o huecos, debes resolverlo antes, explicitamente, con transformaciones.

### 6.2 El Catalogo Canonico Global Y Las Series Por Objeto

El catalogo del proyecto (seccion 6) responde "que archivos cargue". El
**catalogo canonico** responde una pregunta distinta: "que fuentes existen,
para que sirven y quien las usa". Es el modelo que introdujo TS-7, y desde el
cutover es el unico escritor de series de tiempo de la aplicacion.

**Acceso.** El enlace **Catalogo** de la navegacion, y las tres rutas
asociadas, se abren solo a cuentas habilitadas para la lectura canonica.
Antes del cutover C6 esas son las cuentas de verificacion listadas en
`TS_NEXT_CANONICAL_READ_ACCOUNTS` (o, sin esa variable, la unica credencial
de verificacion de `.env`); despues del cutover, toda identidad interna. Si no
tienes el enlace, la ruta simplemente no existe para ti.

**Vista de catalogo** (`/time-series/catalog`). Lista las fuentes por senal,
no por archivo. Cada fila trae identidad, tipo semantico, unidad, clase de
dato, proyecto propietario, alcance, cobertura y cuantas asociaciones tiene.
Se filtra por texto, tipo semantico, clase de dato, unidad, alcance
(**Proyecto** o **Global**) y estado (**Activas** o **Archivadas**), y se
ordena por actualizacion reciente, nombre, proyecto propietario, fin de
cobertura o numero de asociaciones. El detalle agrega el historial de
revisiones y una vista previa de valores contra una revision exacta.

Dos alcances:

- `project`: la fuente pertenece a un proyecto y solo se puede usar ahi.
- `global`: fuente generica compartida entre proyectos.

Promover un set a `global` o devolverlo a `project` es una operacion **de
admin**, en dos pasos: una prevalidacion que enumera el impacto sin escribir
nada, y la confirmacion. Un `analyst` recibe `TS_SCOPE_ADMIN_REQUIRED`. Bajar
de alcance falla cerrado si hay consumidores de otros proyectos, y los
enumera en vez de dar una negativa seca. Repetir un cambio ya vigente devuelve
`TS_SCOPE_ALREADY_EFFECTIVE` y no escribe. La promocion conserva la misma
fila: propietario, revisiones, asociaciones e historial siguen siendo los
mismos.

**Resumen contextual del objeto**
(`/projects/{proyecto}/linkable-objects/{objeto}/time-series`). Es la vista
inversa: parado en un componente, que series tiene, de que tipo son, si estan
asociadas al objeto y en que variantes se estan usando. Cada uso muestra
variante, escenario, rol, numero de revision y hash, y se marca **Obsoleta**
o **Invalida**, con **Ejecucion bloqueada** cuando corresponde.

**Series especificas del objeto.** Cuando un dato pertenece solo a un
componente y no tiene sentido compartirlo, se crea como serie especifica de
ese objeto. No aparece nunca en el catalogo global, bajo ningun filtro. Su
ciclo es explicito: primero se guarda la definicion (clave local, nombre,
tipo semantico, unidad, clase de dato, zona horaria, resolucion) y queda a la
espera de datos, **sin ser seleccionable**; luego se cargan los puntos (por
formulario, CSV o XLSX), que quedan en staging con una vista previa de su
hash; y solo al sellar nace la revision, con el mismo hash que el staging
habia mostrado.

**El recorrido protegido** (`/time-series/journey`). Es el **unico** camino
que muta el modelo canonico. Se entra desde el catalogo o desde el resumen del
objeto, y siempre tiene los mismos cuatro pasos:

1. **Origen y alcance**: necesidad funcional, y si la fuente sera generica
   compartida o solo de este objeto.
2. **Definicion o seleccion**: elegir la fuente compatible o definir la serie
   especifica. Las fuentes incompatibles aparecen bloqueadas con su codigo
   estable, no ocultas.
3. **Datos o revision**: cargar los datos, o elegir la revision exacta.
4. **Impacto y confirmacion**: el impacto completo antes de decidir, y la
   confirmacion con motivo.

Dos intenciones, distintas y sucesivas: **Asociar fuente al objeto** y **Usar
revision en una variante**. El veredicto del servidor es **Aceptada**,
**Rechazada** o **Requiere confirmacion**.

**Actualizar una fuente compartida desde un objeto** es el caso delicado, y
por eso el recorrido muestra el impacto entero antes de cualquier decision:
alcance, propietario, revision vigente, asociaciones, otros proyectos
afectados y que bindings quedarian obsoletos. Recien entonces ofrece dos
salidas con nombre propio:

- **Crear especifica para este objeto**: deriva una copia local, con su
  lineage. No toca a nadie mas.
- **Publicar para todos**: publica una revision nueva de la fuente
  compartida. Exige motivo explicito y reconocimiento de lo que implica, y
  deja visiblemente obsoletos los bindings de los consumidores.

**Auditoria.** Las asociaciones, los bindings y los cambios de alcance tienen
cada uno su libro de eventos, y los tres son inmutables: ninguna ruta publica
los borra, y la base de datos rechaza tanto el `DELETE` como el `UPDATE`. Cada
evento registra identidad del actor, su rol, su id, el codigo de motivo, el
`request_id` y el momento; el libro distingue quien hizo cada cosa en vez de
registrar "alguien".

## 7. Variantes De Entrada: Conectar Datos Al Caso

De vuelta en el escenario, abrir **Datos**. El panel **Variantes de entrada** es donde el caso
se conecta con el catalogo. Una variante es un juego nombrado de *bindings*:
para cada senal requerida por el caso, que fuente la alimenta y **en que
revision exacta**. Son referencias, no copias.

- Todo caso parte con una variante **Default**.
- **Variante activa**: selector de con que variante trabajas. Si aparece
  "(desactualizada)", hay que revalidar antes de correr.
- En **Gestionar variantes**, usa **Clonar variante activa**: escribe un nombre descriptivo (por ejemplo
  "Precios estresados 2027") y clona. La copia hereda todos los bindings y
  puedes cambiarle solo los que te interesan, sin tocar la Default. Asi se
  estudian sensibilidades de datos sobre el mismo modelo.

Debajo del selector, el editor de bindings lista las **senales requeridas**
del caso (derivadas automaticamente de su topologia: si agregas un activo
`load`, aparece `load_demand_mw`; si agregas nodos hidraulicos, aparecen sus
afluentes; etc.). En compatibilidad hay un selector por senal y la accion
**Confirmar fuentes**. Cuando el servidor exige el recorrido protegido, el
panel muestra las revisiones fijadas y enlaces para corregir cada necesidad
desde el objeto. Ese recorrido conserva prevalidacion y confirmacion de impacto.

Como el binding apunta a una revision exacta y no a "la ultima", una revision
nueva de la fuente **no** entra sola: el binding queda marcado obsoleto y hay
que decidir explicitamente si se mueve. Eso es lo que hace que el fail-closed
de la seccion 8 sea detectable en vez de una sorpresa.

## 8. Correr La Optimizacion

En el mismo panel de la variante:

1. Confirma todas las fuentes: **Confirmar fuentes** en compatibilidad, o el
   recorrido protegido enlazado desde cada necesidad. Esto no crea una corrida.
2. Define **Inicio del período**, **Fin del período** y sus offsets. El panel
   muestra la zona de las fuentes, la duracion y el intervalo `[inicio, fin)`.
   **Entrada ISO avanzada** conserva la entrada literal. Cambiar de fuente
   mantiene el rango digitado. **Usar cobertura disponible** adopta expresamente
   la cobertura comun que pudo comprobar el servidor.
3. Presiona **Revisar preparación**. El servidor comprueba cobertura exacta,
   huecos, resolucion y dependencias. Cualquier cambio posterior exige otra revision.
4. Cuando aparezca **Preparado para ejecutar este período**, presiona
   **Ejecutar variante**.

Si la confirmacion de fuentes falla parcialmente, el mensaje cuenta los cambios
aceptados y conserva los pendientes. Si aparece **No pudimos confirmar el envío**,
consulta el historial: la corrida puede haberse aceptado. No se reenvia
automaticamente; despues de consultar, puedes preparar otro intento y revisarlo.

Que pasa por debajo (util para confiar en el resultado): la aplicacion
valida que cada set vinculado cubra el rango exacto sin huecos y con
resolucion consistente; materializa las series desde las revisiones que
fijaron los bindings; congela topologia, parametros, variante, rango y
lineage de cada serie (set, version, revision, hash) en una **version
inmutable**; crea la corrida y la encola para ejecutar Julia. Te redirige al
detalle del run.

### Staleness (la regla fail-closed)

Si despues de la ultima validacion cambio cualquiera de estas cosas, la
variante queda **desactualizada** y la aplicacion se niega a correr:

- alguna serie vinculada tiene nueva revision (nuevo `content_hash`);
- la topologia o los parametros del caso cambiaron;
- un set derivado vinculado quedo stale respecto de su receta.

Veras los motivos y enlaces al modelo o la fuente que debes corregir. Resuelve
esos cambios (y regenera derivados si corresponde) y usa **Revisar preparación**.
Las revisiones canonicas obsoletas requieren resolver su uso en el recorrido
protegido; la revision general no reemplaza una revision fijada silenciosamente.

### Estados y detalle de la corrida

Una corrida pasa por `queued` -> `running` -> `succeeded` | `failed`. El
detalle del run muestra:

- **Run state**: estado, tiempos, quien/que la disparo (manual, schedule o
  consola de operador).
- **Lineage** y **Procedencia**: proyecto/escenario/version, hashes de
  topologia y parametros.
- **Series de entrada**: por cada senal, el set/version/revision/hash exacto
  consumido.
- **Snapshot tecnico**: el `system_case_json` congelado.
- Si fallo: error estructurado, stdout y stderr del solver.
- Si termino bien: **resultados** (tablas y graficos indexados en BBDD),
  seccion de **publicacion** y **artefactos** descargables (`dispatch.csv`,
  `asset_dispatch.csv`, `summary.json`, `model_metadata.json`).

### Camino experto (opcional)

En **Avanzado**, el escenario lista las **Versiones inmutables** y permite crear una
version pegando un `system_case_json` a mano (formulario experto) y lanzarle
un run manual desde su detalle. Es un camino de escape: el flujo normal es
correr desde la variante.

## 9. Analizar Y Comparar Resultados

- Los graficos base cubren precios, importacion/exportacion, renovable usada
  y vertida, carga/descarga y SOC del BESS, generacion y stock hidraulico,
  demanda y profit por periodo, mas KPIs economicos por corrida.
- **Plantillas de dashboard**: en **Informes** del proyecto puedes guardar
  configuraciones de graficos como plantillas reutilizables y aplicarlas a
  corridas nuevas.
- **Comparar corridas**: desde **Ejecuciones** del escenario, **Comparar corridas** abre una
  vista que enfrenta dos runs del mismo caso: contexto de cada una (variante,
  rango, hashes), KPIs lado a lado y series superpuestas. Como cada run
  guarda su lineage completo, la comparacion te dice tambien *por que*
  difieren (datos distintos, parametros distintos, o ambos).

## 10. Entregar Resultados A Usuarios Externos

Un usuario `external` con `portal_view` no ve nada de lo anterior: solo un
portal read-only con lo que se publico y se configuro explicitamente. El
portal no es una vista automatica de los resultados; es una configuracion.

1. **Publicar la corrida.** En el detalle de un run exitoso, seccion de
   publicacion -> **Nueva publicacion**: eliges que artefactos y dashboards
   expone. Puedes previsualizarla exactamente como la vera el externo.
2. **Configurar el portal del proyecto.** En **Informes** del proyecto, la
   seccion **Portal del cliente** define nombre publico, logo (PNG o JPEG,
   hasta 256 KiB) y que se muestra: titulos de secciones, KPIs (con signo y
   enfasis), graficos, tablas y descargas, elegidos desde un catalogo de
   items disponibles. La configuracion se guarda por revisiones y tiene
   estado **Borrador** o **Activa**; solo lo activo llega al portal.
3. **Asignar capacidades.** Un admin decide, proyecto por proyecto, que
   usuario externo tiene **Portal** (`portal_view`) y/o **Operar**
   (`operate`), en **Accesos** de la pagina del proyecto.
   Revocar una capacidad surte efecto en el siguiente request.

El externo entra, aterriza en el portal, ve los proyectos que le asignaron,
las publicaciones y las descargas habilitadas por allowlist. No puede editar,
correr ni ver corridas no publicadas, y el contenido de otro proyecto le
responde 404, no un mensaje de permiso.

## 11. Consolas De Operador

Una consola es una superficie acotada para que alguien opere el modelo sin
tocarlo: cambia unos pocos datos y parametros declarados, ejecuta y mira
resultados. La configura el analista; la usa un `external` con `operate` en
`/console` (o tu mismo, con **Probar**, para verificarla).

**Crearla.** En **Avanzado** del escenario, panel **Consolas de operador**: nombre de la
consola y **variante de origen**, luego **Crear consola**. La consola recibe
**su propia variante clonada**: el operador nunca ve ni toca la variante del
analista.

**Configurarla** (accion `Configurar`). El documento
(`operator_console_config.v1`) define:

- **Identidad publica**: nombre y descripcion que vera el operador.
- **Grupos y columnas**: las tablas que el operador puede editar. Cada
  columna se ata a una senal del **catalogo canonico de senales**; una senal
  que no este en el catalogo se rechaza al guardar, no al ejecutar.
- **Parametros y resultados** (JSON): que parametros quedan expuestos, con
  etiqueta, unidad y minimo/maximo, y que KPIs, graficos y tablas se
  muestran.

Estado **Borrador** o **Activa**; solo lo activo es operable.

**Que puede hacer el operador.** Elegir periodo dentro del rango disponible,
mover los parametros expuestos dentro de sus limites, editar las tablas
declaradas (pegado incluido, con revision de cambios celda a celda antes de
guardar), **Ejecutar**, ver el historial reciente y comparar dos corridas
suyas. Las ediciones se hacen sobre **copias operativas** de las series: el
dato canonico no se toca. Para editar hay que tomar un lease, hay heartbeat y
contencion visible, el guardado de varios sets es atomico, y el historial
registra quien cambio que celda, con deshacer y restaurar append-only.

**Cuando la consola se bloquea.** Si el analista cambia el modelo por debajo,
la consola falla cerrado en vez de correr con supuestos viejos. El panel
muestra el motivo y la accion que lo resuelve:

| Bloqueo | Que paso | Accion del analista |
| --- | --- | --- |
| **Dependencia movida** | La variante de la consola quedo desactualizada respecto del caso o de las series. | **Revalidar variante**, desde el propio panel. |
| **Campo no disponible** | Un parametro o una columna de la consola apunta a algo que ya no existe en el caso. | **Corregir**, que lleva al campo exacto del editor de la consola. |

El operador, por su lado, puede **Solicitar revision**; la solicitud queda con
su timestamp y el panel del analista muestra desde cuando espera. La columna
**Origen de copias** avisa cuando una copia operativa quedo atras de su
origen canonico (**Copia antigua**, con la revision copiada y la vigente); la
regeneracion automatica no existe, es una decision tuya.

## 12. Corridas Programadas (Admin)

Para reruns periodicos (por ejemplo, reoptimizar cada dia con el pronostico
mas reciente) existen los **schedules**, gestionados por un admin en la
seccion Admin:

- Un schedule referencia caso + variante + regla de rango + cadencia. Nunca
  se pega un JSON de caso a mano.
- Regla de rango `fixed` (mismo rango cada vez) o `rolling` (offset y
  duracion en horas resueltos respecto de la hora de disparo — rolling
  horizon).
- El disparo es externo: el boton **Ejecutar vencidos** o el script
  `scripts/run_due_schedules.py` invocado por el Task Scheduler / cron del
  sistema operativo. No hay scheduler interno.
- Cada disparo queda registrado como *tick* con su resultado. Las corridas
  producidas son corridas normales (`trigger_type = scheduled`) con el mismo
  snapshot inmutable, y pasan por los mismos gates: si la variante esta
  stale o el rango no tiene cobertura, el tick falla visiblemente y **no**
  se crea ninguna corrida.

## 13. Eliminar Un Proyecto

Eliminar un proyecto es la unica operacion que termina la retencion de su
historia. Borra escenarios, versiones, corridas, series de tiempo,
publicaciones, consolas y todo el rastro canonico del proyecto —
asociaciones, bindings y libros de auditoria incluidos — dentro de una sola
transaccion: si algo falla, no se borra nada.

Fuera de ese caso nada se puede borrar ni reescribir: una revision sellada,
una identidad de senal, una asociacion, un binding y los tres libros siguen
siendo inmutables. Y aun durante el borrado del proyecto solo se permite
eliminar, nunca actualizar; no hay forma de alterar historia y hacerla pasar
por algo que si ocurrio.

Consecuencia a tener presente: un lineage que cruza dos proyectos se va con el
primero de los dos que se elimine.

## 14. Errores Frecuentes De Usuario Nuevo

| Sintoma | Causa probable | Solucion |
| --- | --- | --- |
| Variante desactualizada | Alguna serie, la topologia o los parametros cambiaron desde la ultima validacion. | Corregir los motivos indicados y presionar **Revisar preparación**. |
| El boton de correr esta deshabilitado | Falta modelo, fuente confirmada, rango valido o una revision vigente. | Seguir los enlaces de correccion, confirmar fuentes y revisar la preparacion. |
| "missing coverage for [...)" | Algun set vinculado no cubre el rango pedido, o tiene huecos. | Acortar el rango, o completar/interpolar la serie (explicitamente) y revalidar. |
| "Horizonte incompatible" / rechazo por resolucion | Sets vinculados con resoluciones distintas. | No hay resampling implicito: usar la transformacion `resample` para unificar resolucion antes de vincular. |
| Set derivado con badge "Desactualizado" | Su origen cambio despues de generarlo. | **Regenerar set derivado** y luego revalidar las variantes que lo usan. |
| El draft no genera el caso | `schema_version` alterado o campos invalidos. | Restaurar `bess_editor_draft.v1` y revisar los errores de validacion. |
| La corrida queda `failed` | Error del solver o caso infactible. | Revisar el error estructurado, stdout y stderr en el detalle del run. |
| Corridas fallan de inmediato en ambiente nuevo | Julia no esta disponible para el worker. | Instalar/configurar el motor Julia; la parte web funciona igual sin el, pero no puede ejecutar. |
| No aparece el enlace **Catalogo** y `/time-series/catalog` responde 404 | La cuenta no esta habilitada para la lectura canonica antes del cutover. | Agregar la cuenta a `TS_NEXT_CANONICAL_READ_ACCOUNTS`, o esperar al cutover, que la abre a toda identidad interna. |
| Una fuente aparece bloqueada al intentar asociarla | Incompatibilidad de tipo semantico, unidad o tipo de objeto. | Leer el codigo estable que acompana al bloqueo; elegir otra fuente o crear una serie especifica del objeto. |
| La serie especifica creada no se puede seleccionar | Se guardo la definicion pero todavia no tiene una revision sellada. | Cargar los puntos y sellar la revision; solo entonces es seleccionable. |
| `TS_SCOPE_ADMIN_REQUIRED` al promover o degradar un set | El cambio de alcance es operacion de admin. | Pedirlo a un admin; la prevalidacion muestra el impacto antes de escribir nada. |
| Un binding quedo **Obsoleta** con **Ejecucion bloqueada** | Alguien publico una revision nueva de la fuente compartida. | Decidir explicitamente, en el recorrido protegido, si el binding se mueve a la revision nueva. |
| El usuario externo entra y no ve nada | No tiene capacidades en ese proyecto, o la configuracion del portal esta en Borrador. | Asignar `portal_view` (admin) y poner la configuracion del portal en **Activa**. |
| Consola bloqueada con **Dependencia movida** | La variante de la consola quedo desactualizada. | **Revalidar variante** desde el panel de consolas. |
| Consola bloqueada con **Campo no disponible** | Un parametro o columna apunta a algo que ya no existe en el caso. | Usar **Corregir**, que lleva al campo exacto del editor de la consola. |

## 15. Donde Profundizar

- Recorrido operativo completo, pantalla por pantalla:
  `docs/tutorials/manual_completo_uso_pagina_web.md`.
- Carga y matcheo de series:
  `docs/tutorials/carga_y_matcheo_series_tiempo.md`.
- Vision de producto y alcance: `docs/final/objetivo_final.md`.
- Formulacion matematica del motor: `docs/iter1/mathematical_model.md`.
- Jerarquia caso/version/corrida (semantica aceptada):
  `docs/series_tiempo/iter1/decision_record_ts1_hierarchy.md`.
- Catalogo de series: `docs/series_tiempo/iter2/`.
- Variantes de entrada y staleness:
  `docs/series_tiempo/iter3/decision_record_ts3_variant_semantics.md`.
- Resultados en BBDD y comparacion de corridas: `docs/series_tiempo/iter4/`.
- Transformaciones, conectores y schedules:
  `docs/series_tiempo/iter6/architecture_ts6_final.md`.
- Catalogo canonico, objetos vinculables y series especificas:
  `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md`,
  con la evidencia de cierre en `docs/series_tiempo/iter7/acceptance_ts7.md` y
  la semantica del borrado en
  `docs/series_tiempo/iter7/decision_record_ts7_project_purge.md`.
- Consolas, portal y capacidades externas:
  `docs/capa_configuracion/architecture_configuration_layer_final.md`, con su
  verificacion en
  `docs/capa_configuracion/verification_configuration_layer_final.md`.
- Decisiones de producto detras de ambas capas: `docs/wayfinder/`.
- Checklists manuales por iteracion (utiles como recorridos guiados de la
  UI): `docs/series_tiempo/iter*/pruebas_manuales_*.md`.
