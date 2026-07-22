# Guia Del Analista: Primeros Pasos Con BESS Workspace

Audiencia: analistas con experiencia en herramientas de optimizacion
(formulacion LP/MIP, solvers, analisis de escenarios, series de tiempo) pero
sin experiencia previa con esta aplicacion en particular.

Objetivo: al terminar esta guia deberias poder crear un proyecto, modelar un
caso one-bus, cargar series de tiempo, correr la optimizacion, revisar
resultados, comparar corridas y publicar resultados para un cliente.

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

## 2. El Modelo Mental

Antes de tocar la UI conviene entender la jerarquia de objetos. Todo el
trabajo se ordena asi:

```text
Proyecto
  -> Escenario (caso de optimizacion, editable)
       -> Draft (documento editable del modelo)
       -> Variante de entrada (bindings a series del catalogo)
            -> Rango de fechas (elegido al correr)
                 -> Version inmutable (snapshot ejecutable)
                      -> Corrida (queued/running/succeeded/failed)
                           -> Resultados, dashboards
                                -> Publicacion read-only para cliente

Proyecto
  -> Catalogo de series de tiempo (sets versionados, compartidos por
     todos los escenarios del proyecto)
```

Conceptos que no debes confundir:

| Concepto | Que es | Mutable? |
| --- | --- | --- |
| Escenario / caso | El modelo editable (topologia, parametros, solver). | Si |
| Draft | El documento de trabajo del editor estructurado. | Si |
| Set de series | Un conjunto versionado de senales con horizonte comun. | Solo agregando revisiones |
| Variante de entrada | Un juego nombrado de referencias caso-a-series. | Si (sus bindings) |
| Version inmutable | Snapshot congelado listo para ejecutar. | No, nunca |
| Corrida (run) | Una ejecucion del solver sobre una version. | No (solo su estado) |

Regla de oro: **las corridas nunca leen datos "en vivo"**. Al correr, la
aplicacion materializa las series de la variante en el rango elegido, congela
todo en una version inmutable y ejecuta eso. Si despues editas una serie, las
corridas viejas siguen apuntando al hash exacto que consumieron.

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

### Sesion y roles

La primera vez que la aplicacion arranca sin usuarios te pedira crear la
cuenta inicial (bootstrap de admin). Despues, el login es correo + password.

Hay tres roles:

- `analyst`: crea y edita proyectos, modelos, series; corre y publica.
- `admin`: todo lo anterior, mas gestion de usuarios, acceso de clientes a
  proyectos, schedules de corridas automaticas y operaciones masivas.
- `client`: solo lectura, ve unicamente lo publicado (seccion 10).

La barra superior muestra tu identidad y rol; la navegacion principal para un
analista es **Analista** (proyectos), y para un admin ademas **Admin**.

## 4. Crear Proyecto Y Escenario

1. En **Analista** (`/projects`), usar el formulario **Nuevo proyecto** y
   presionar **Crear proyecto**.
2. Entrar al proyecto. Veras: la lista de **Escenarios**, el acceso al
   **catalogo de series de tiempo**, las plantillas de dashboards y (si eres
   admin) la gestion de acceso de clientes.
3. Crear un escenario con **Nuevo escenario** -> **Crear escenario**. Un
   escenario es un caso de optimizacion: conviene uno por configuracion de
   sistema que quieras estudiar (las alternativas de *datos* no requieren
   escenarios nuevos; para eso estan las variantes, seccion 7).

## 5. Modelar El Caso: El Draft

Dentro del escenario, presionar **Abrir draft**. El editor es estructurado
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
4. **Migracion de series hidraulicas legacy** (solo si vienes de datos
   creados con el editor hidraulico antiguo; es una operacion de admin).

Las senales canonicas que un caso puede requerir son, entre otras:
`import_price_usd_per_mwh` / `export_price_usd_per_mwh` (precios de red),
`load_demand_mw` (demanda), `renewable_available_power_mw` (disponibilidad
renovable), `natural_inflow_m3s` (afluentes por nodo hidraulico) y
`minimum_flow_m3s` (caudal minimo por tramo).

Versionado: editar valores a mano o reemplazar el archivo de un set **no
sobreescribe nada**: crea una nueva *revision* con nuevo `content_hash`. El
historial de revisiones es inmutable; las corridas viejas siguen apuntando a
la revision que usaron.

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

## 7. Variantes De Entrada: Conectar Datos Al Caso

De vuelta en el escenario, el panel **Variante de entrada** es donde el caso
se conecta con el catalogo. Una variante es un juego nombrado de *bindings*:
para cada senal requerida por el caso, que set del catalogo la alimenta. Son
referencias, no copias.

- Todo caso parte con una variante **Default**.
- **Variante activa**: selector de con que variante trabajas. Si aparece
  "(desactualizada)", hay que revalidar antes de correr.
- **Clonar variante activa**: escribe un nombre descriptivo (por ejemplo
  "Precios estresados 2027") y clona. La copia hereda todos los bindings y
  puedes cambiarle solo los que te interesan, sin tocar la Default. Asi se
  estudian sensibilidades de datos sobre el mismo modelo.

Debajo del selector, el editor de bindings lista las **senales requeridas**
del caso (derivadas automaticamente de su topologia: si agregas un activo
`load`, aparece `load_demand_mw`; si agregas nodos hidraulicos, aparecen sus
afluentes; etc.) con un select por senal para elegir el set que la cubre.

## 8. Correr La Optimizacion

En el mismo panel de la variante:

1. Vincula todas las senales requeridas.
2. Define **Inicio de rango** y **Fin de rango**: el intervalo `[inicio,
   fin)` de las series que quieres optimizar, en ISO-8601 con offset de zona
   horaria (por ejemplo `2026-01-01T00:00:00-03:00`). Por defecto se
   propone el horizonte del primer set vinculado. La UI valida cobertura y
   compatibilidad de resolucion en linea ("Rango valido para correr").
3. Presiona **Vincular y correr variante**.

Que pasa por debajo (util para confiar en el resultado): la aplicacion
valida que cada set vinculado cubra el rango exacto sin huecos y con
resolucion consistente; materializa las series; congela topologia,
parametros, variante, rango y lineage de cada serie (set, version, revision,
hash) en una **version inmutable**; crea la corrida y la encola para
ejecutar Julia. Te redirige al detalle del run.

### Staleness (la regla fail-closed)

Si despues de la ultima validacion cambio cualquiera de estas cosas, la
variante queda **desactualizada** y la aplicacion se niega a correr:

- alguna serie vinculada tiene nueva revision (nuevo `content_hash`);
- la topologia o los parametros del caso cambiaron;
- un set derivado vinculado quedo stale respecto de su receta.

Veras un banner con los motivos y el boton **Revalidar variante**. Esto es
deliberado: nunca hay re-runs silenciosos con datos distintos a los que
crees estar usando. Revalida (y regenera derivados si corresponde) y vuelve
a correr.

### Estados y detalle de la corrida

Una corrida pasa por `queued` -> `running` -> `succeeded` | `failed`. El
detalle del run muestra:

- **Run state**: estado, tiempos, quien/que la disparo (manual o schedule).
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

El escenario tambien lista las **Versiones inmutables** y permite crear una
version pegando un `system_case_json` a mano (formulario experto) y lanzarle
un run manual desde su detalle. Es un camino de escape: el flujo normal es
correr desde la variante.

## 9. Analizar Y Comparar Resultados

- Los graficos base cubren precios, importacion/exportacion, renovable usada
  y vertida, carga/descarga y SOC del BESS, generacion y stock hidraulico,
  demanda y profit por periodo, mas KPIs economicos por corrida.
- **Plantillas de dashboard**: en la pagina del proyecto puedes guardar
  configuraciones de graficos como plantillas reutilizables y aplicarlas a
  corridas nuevas.
- **Comparar corridas**: desde el escenario, **Comparar corridas** abre una
  vista que enfrenta dos runs del mismo caso: contexto de cada una (variante,
  rango, hashes), KPIs lado a lado y series superpuestas. Como cada run
  guarda su lineage completo, la comparacion te dice tambien *por que*
  difieren (datos distintos, parametros distintos, o ambos).

## 10. Publicar Para Clientes

El rol `client` no ve nada de lo anterior: solo un portal read-only con lo
que el analista publico explicitamente.

1. En el detalle de un run exitoso, seccion de publicacion -> **Nueva
   publicacion**: eliges que artefactos y dashboards expone.
2. Puedes previsualizar la publicacion exactamente como la vera el cliente.
3. Un admin asigna que usuarios cliente tienen acceso a que proyecto (en la
   pagina del proyecto, gestion de acceso de clientes).

El cliente entra, ve sus proyectos asignados, las publicaciones y descarga
los archivos habilitados. No puede editar, correr ni ver corridas no
publicadas.

## 11. Corridas Programadas (Admin)

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

## 12. Errores Frecuentes De Usuario Nuevo

| Sintoma | Causa probable | Solucion |
| --- | --- | --- |
| "Variante desactualizada: revalida antes de correr" | Alguna serie, la topologia o los parametros cambiaron desde la ultima validacion. | Revisar los motivos del banner y presionar **Revalidar variante**. |
| El boton de correr esta deshabilitado | Falta vincular alguna senal requerida, o el rango esta vacio/invalido. | Completar todos los selects de senales y revisar el mensaje de validacion del rango. |
| "missing coverage for [...)" | Algun set vinculado no cubre el rango pedido, o tiene huecos. | Acortar el rango, o completar/interpolar la serie (explicitamente) y revalidar. |
| "Horizonte incompatible" / rechazo por resolucion | Sets vinculados con resoluciones distintas. | No hay resampling implicito: usar la transformacion `resample` para unificar resolucion antes de vincular. |
| Set derivado con badge "Desactualizado" | Su origen cambio despues de generarlo. | **Regenerar set derivado** y luego revalidar las variantes que lo usan. |
| El draft no genera el caso | `schema_version` alterado o campos invalidos. | Restaurar `bess_editor_draft.v1` y revisar los errores de validacion. |
| La corrida queda `failed` | Error del solver o caso infactible. | Revisar el error estructurado, stdout y stderr en el detalle del run. |
| Corridas fallan de inmediato en ambiente nuevo | Julia no esta disponible para el worker. | Instalar/configurar el motor Julia; la parte web funciona igual sin el, pero no puede ejecutar. |

## 13. Donde Profundizar

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
- Checklists manuales por iteracion (utiles como recorridos guiados de la
  UI): `docs/series_tiempo/iter*/pruebas_manuales_*.md`.
