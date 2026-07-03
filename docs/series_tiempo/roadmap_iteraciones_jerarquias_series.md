# Roadmap De Iteraciones Para Topologia, Parametros Y Series Versionadas

Fecha: 2026-07-03

## Objetivo

Separar correctamente tres jerarquias que hoy estan parcialmente mezcladas:

1. **Topologia**: que componentes existen y como se conectan.
2. **Parametros del caso**: como se parametriza esa topologia para optimizar.
3. **Series de tiempo de entrada**: que datos temporales se usan, con versiones,
   rango de fechas y edicion desde BBDD.

El resultado esperado es que un analista pueda abrir un caso, elegir desde un
dropdown la version de series de entrada, elegir un rango de fechas y correr. El
Excel o CSV debe servir para cargar o reemplazar datos, pero la fuente operativa
de series debe ser la BBDD. Los resultados tambien deben quedar guardados en
BBDD, asociados a la combinacion exacta de topologia, parametros, series y rango
usados.

Este documento no define issues todavia. Primero fija una vision por
iteraciones. Despues se creara un PRD por iteracion y, recien con cada PRD
cerrado, se partiran issues concretas.

## Pasada Grill-Me: Decisiones Recomendadas

### 1. `ScenarioVersion` debe seguir siendo la version visible del usuario?

Respuesta recomendada: no como concepto principal de UI. Debe seguir existiendo
como snapshot auditable ejecutable, porque hoy el flujo de corridas depende de
`scenario_versions.system_case_json` inmutable. Pero el usuario deberia pensar
en:

```text
OptimizationCase
-> ParameterVersion
-> InputSeriesVariant
-> DateRange
-> Run
```

`ScenarioVersion` puede quedar como snapshot tecnico creado automaticamente al
correr o promover.

### 2. `Scenario` y `OptimizationCase` deben seguir siendo casi lo mismo?

Respuesta recomendada: no. `Scenario` debe ser una carpeta o linea de trabajo
dentro de un proyecto. `OptimizationCase` debe ser la unidad editable que el
analista abre y corre. En el estado actual, `optimization_cases.scenario_id` es
`UNIQUE` y esta muy orientado al editor hidraulico. En el modelo objetivo, un
scenario podria contener uno o mas casos si eso se vuelve util.

### 3. La topologia debe cambiar cuando cambia una serie?

Respuesta recomendada: no. La topologia debe ser independiente. Cambiar de
hidrologia, demanda o precios no debe duplicar nodos, componentes, tramos,
centrales ni unidades.

### 4. Los parametros deben vivir dentro de la topologia?

Respuesta recomendada: solo los atributos fisicos estables. Los parametros que
pueden cambiar entre alternativas deben vivir en versiones de parametros del
caso. Ejemplos: limites activos, estados iniciales, costos, penalizaciones,
solver settings, restricciones activas y curvas elegidas para correr.

### 5. Las series deben ser archivos o datos en BBDD?

Respuesta recomendada: datos en BBDD. El archivo debe quedar como fuente
auditable (`time_series_sources`), pero los valores usados por el sistema deben
vivir en tablas de periodos, senales y valores.

### 6. Una version de series puede editarse?

Respuesta recomendada: si, pero con revisiones. Si el usuario edita manualmente
o sube otro Excel/CSV sobre una version visible, se crea una nueva revision con
`content_hash`. Las corridas guardan la revision/hash exacto que usaron. Asi se
permite la ergonomia de "editar version" sin romper reproducibilidad.

### 7. Debe existir una version default de series por caso?

Respuesta recomendada: si. Cada `OptimizationCase` debe tener un
`default_input_variant_id`. La UI abre el caso con esa variante seleccionada,
pero permite cambiarla desde un dropdown antes de correr.

### 8. El rango de fechas pertenece a la version de series o a la corrida?

Respuesta recomendada: pertenece a la corrida o al snapshot ejecutable. Una
version de series puede contener un horizonte grande; al correr se selecciona un
rango. El sistema materializa solo ese slice dentro del snapshot de ejecucion.

### 9. Los resultados deben reemplazar los artifacts?

Respuesta recomendada: no. Los artifacts siguen siendo auditoria reproducible.
Pero los resultados principales deben indexarse tambien en BBDD para consulta,
comparacion, dashboards y futuras publicaciones. Esto incluye al menos series
de `dispatch.csv` y `asset_dispatch.csv` que sean utiles para UI.

### 10. La primera implementacion debe resolver resampling?

Respuesta recomendada: no. La primera version debe exigir que las series usadas
por una corrida calcen exactamente en el rango elegido. Resampling,
interpolacion y escalamiento deben ser una iteracion posterior con
transformaciones versionadas.

## Diferencia Con El Estado Actual

Hoy el flujo principal es:

```text
Scenario
-> ScenarioDraft u OptimizationCase
-> ScenarioVersion(system_case_json completo)
-> Run
-> artifacts
```

La `ScenarioVersion` congela todo junto: topologia, parametros y series ya
materializadas. Eso es correcto para auditoria, pero es incomodo como modelo
mental del analista cuando solo quiere cambiar de hidrologia, demanda o precios.

El objetivo nuevo separa capas:

```text
Project
-> Scenario
  -> OptimizationCase
    -> TopologyVersion
    -> ParameterVersion
    -> InputSeriesVariant(default o seleccionada)
      -> TimeSeriesSet + TimeSeriesRevision
    -> Run(date_range)
      -> ExecutionSnapshot/ScenarioVersion
      -> ResultSeries
      -> Artifacts
```

En este modelo:

- Topologia no cambia al cambiar series.
- Parametros no cambian al cambiar series.
- Series viven en BBDD y se seleccionan por variante.
- La corrida congela la combinacion exacta usada.
- Los resultados quedan en artifacts y tambien en BBDD.

## Modelo Objetivo De Trabajo

Nombres tentativos:

```text
projects
  -> scenarios
    -> optimization_cases
      -> topology_versions
      -> case_parameter_versions
      -> case_input_variants
        -> case_time_series_bindings
          -> time_series_sets
            -> time_series_set_revisions
            -> time_series_periods
            -> time_series_signals
            -> time_series_values
      -> scenario_versions / execution_snapshots
        -> runs
          -> result_series_sets
          -> run_artifacts
```

`ScenarioVersion` puede mantenerse como tabla tecnica por compatibilidad, pero
la UI deberia presentarlo como "input snapshot" o "run input version", no como
la version principal que el usuario manipula todos los dias.

## Dimensionamiento

Las iteraciones existentes del repo suelen tener entre 9 y 12 issues cuando ya
existe un PRD:

- Iteracion 4: editor estructurado, CSV/XLSX y promocion.
- Iteracion 5: hidro simple end-to-end.
- Iteracion 6: auth, publicaciones y portal cliente.
- Hydro Diagram Iteration 1: red hidraulica, layout, v3, validacion y corrida.

Este objetivo es comparable a varias de esas iteraciones juntas porque cruza
BBDD, dominio, UI, validacion, ejecucion, resultados y migracion. La division
recomendada es de 5 iteraciones core, mas una sexta futura para capacidades
avanzadas. Cada iteracion deberia tener su propio PRD antes de crear issues.

## Iteracion TS-1: Jerarquias De Topologia Y Parametros

La primera iteracion debe resolver el problema conceptual de base: un caso no
debe seguir siendo una mezcla implicita de estructura, parametros, series y
snapshot ejecutable. El objetivo es que el sistema empiece a distinguir, aunque
sea con una implementacion inicial conservadora, entre la topologia y la
parametrizacion que se quiere usar sobre esa topologia.

La topologia responde preguntas como: que componentes existen, como se llaman,
que identificadores tecnicos tienen, que nodos o activos se conectan entre si,
que embalses, centrales, unidades o tramos forman parte del sistema, y que
elementos pertenecen al proyecto versus al caso activo. Esa capa debe cambiar
poco y debe poder reutilizarse entre alternativas.

La parametrizacion responde otras preguntas: que limites activos se usan, que
curvas se eligen, cuales son los estados iniciales, que costos o penalizaciones
se aplican, que restricciones estan activas y que solver settings corresponden
a esta alternativa. Dos casos pueden compartir topologia y diferir en parametros.
Tambien un mismo caso puede necesitar una parametrizacion base y luego una
parametrizacion ajustada para una sensibilidad.

Esta iteracion no deberia intentar redisenar las series de tiempo ni los
resultados. Su foco es preparar la base para que despues las series puedan
cambiar sin duplicar topologia ni parametros. Tampoco deberia romper el flujo
actual de `ScenarioVersion -> Run`: al final de esta iteracion, se debe seguir
pudiendo generar un `system_case_json` inmutable y correrlo igual que hoy.

El resultado esperado es que un `OptimizationCase` tenga una topologia
identificable y una version de parametros default. La UI puede seguir mostrando
un flujo similar al actual, pero debe empezar a exponer o al menos registrar la
procedencia: esta version ejecutable salio de esta topologia y de esta
parametrizacion. Eso es importante para que luego los runs puedan decir "use
topologia A, parametros B y series C en el rango D".

El PRD de TS-1 deberia cerrar decisiones como si habra multiples
`OptimizationCase` por `Scenario`, como se versiona la topologia, si las curvas
son parte de parametros o de topologia, y como convivira esta separacion con el
editor hidraulico ya implementado.

### Detalle Adicional

TS-1 debe partir por ordenar el lenguaje del producto. Hoy `Scenario`,
`ScenarioDraft`, `OptimizationCase` y `ScenarioVersion` se solapan parcialmente.
La iteracion debe dejar claro que el analista trabaja sobre un caso editable y
que las versiones ejecutables son snapshots derivados, no el objeto principal de
edicion. Esta distincion deberia reflejarse en la UI, aunque al principio sea
solo con etiquetas, metadata y rutas de navegacion mas claras.

La topologia versionada deberia contener solamente lo que describe la forma del
sistema. En one-bus simple, eso puede ser el PCC y la lista de componentes
electricos. En hidro de diagrama, incluye nodos hidraulicos, tramos, centrales,
unidades y relaciones de intake/discharge. Si un cambio mueve un nodo visual en
el canvas, eso no deberia ser una nueva topologia fisica; si agrega un tramo o
cambia la conexion de una unidad, si deberia afectar la version de topologia o
al menos invalidar su validacion.

La version de parametros deberia contener los valores que hacen ejecutable una
topologia bajo una hipotesis operacional: limites de potencia, limites de
almacenamiento, estados iniciales, eficiencias, costos, penalizaciones, curvas
seleccionadas, restricciones activas y solver settings. Esta separacion ayuda a
responder preguntas como "que pasa si uso la misma central y embalse, pero otra
curva o distintos limites operacionales?" sin copiar toda la red.

En esta primera iteracion no es obligatorio crear una UX completa para comparar
topologias o parametros. El minimo util es que el backend y los snapshots sepan
de donde salieron: `topology_version_id`, `parameter_version_id` o metadata
equivalente. El usuario deberia poder ver en una version o corrida algo como:

```text
Caso: Sistema Maule base
Topologia: v1 - red base validada
Parametros: v2 - limites operacionales invierno
Snapshot ejecutable: creado al validar/correr
```

Tambien hay que decidir el ciclo de vida. Una opcion conservadora para TS-1 es
permitir edicion en estado draft y crear una nueva version cuando se valida o
promueve. Otra opcion es permitir versiones editables con revisions internas.
Para mantener consistencia con lo que luego se quiere hacer con series, la
recomendacion es diferenciar version visible y revision tecnica: la corrida
siempre congela el hash/revision exacto usado.

La validacion de TS-1 debe detectar stale por cambios de topologia o parametros.
Si el usuario valida una topologia y luego cambia un tramo, un limite o una
curva, el snapshot anterior no puede promoverse sin revalidar. Este patron ya
existe parcialmente en el editor hidraulico y deberia generalizarse.

TS-1 termina bien si, aunque no haya nuevas funcionalidades visibles grandes, el
modelo mental queda corregido: un caso ya no es "un JSON que se edita hasta
correr", sino una combinacion controlada de topologia y parametros que luego
podra recibir distintas versiones de series.

## Iteracion TS-2: Catalogo Generico De Series En BBDD

La segunda iteracion debe mover las series de tiempo al lugar correcto: la
BBDD. El archivo Excel o CSV debe dejar de ser el objeto operativo principal.
Debe quedar como fuente auditable de importacion, mientras que los periodos,
senales y valores usados por la aplicacion viven en tablas consultables,
versionables y editables.

Esta iteracion debe construir el catalogo generico de series. Un set de series
debe poder representar un paquete de datos alineados en el tiempo: precios,
demanda, disponibilidad renovable, afluentes, caudales minimos u otras senales.
Cada set debe tener metadata de proyecto, nombre, version visible, revision,
timezone, estado, hash de contenido y origen. Tambien debe poder distinguir si
los datos son reales, programados, forecast, sinteticos, simulados o mixtos.

El usuario debe poder crear una version de series subiendo un CSV/XLSX,
revisando columnas, mapeando columnas a senales canonicas y validando los
valores. Despues, esos valores deben existir en BBDD. Si el usuario corrige una
celda manualmente o sube otro archivo para reemplazar datos, el sistema debe
registrar una nueva revision con hash, fecha y autor. Esto permite una
experiencia flexible sin sacrificar auditoria.

Esta iteracion todavia no necesita conectar las series a un caso por dropdown.
El foco es que las series existan como objetos independientes y reutilizables.
La UI deberia permitir listar sets, ver sus senales, revisar periodos, editar
valores de forma acotada, subir una nueva revision y entender de donde viene
cada dato. La validacion debe cubrir timestamps, duraciones, duplicados,
ordenamiento, unidades esperadas, valores negativos donde no correspondan y
errores de mapeo.

El resultado esperado es que se pueda decir: "ya tengo en BBDD la version
`hidrologia_seca_v2`, la version `precios_enero_2026_v1` y la version
`demanda_cliente_corregida_v3`". Todavia no es necesario que un caso las use
automaticamente, pero ya deben estar preparadas para ser vinculadas en TS-3.

El PRD de TS-2 debe cerrar el modelo de revision versus version visible, el
catalogo inicial de `signal_key`, la politica de edicion manual, la trazabilidad
del archivo fuente y la convencion de timezone.

### Detalle Adicional

TS-2 es la iteracion que convierte Excel/CSV en un mecanismo de carga, no en el
lugar donde viven los datos. Despues de importar, el usuario deberia poder
cerrar el archivo y seguir trabajando desde la aplicacion. Si vuelve a subir un
archivo corregido, eso debe ser una nueva fuente o revision, no una dependencia
opaca contra un path local.

El set de series debe sentirse como un objeto de negocio. No basta con guardar
filas. Debe tener nombre, descripcion, version visible, estado, tipo de dato,
timezone y fuente. Ejemplos de objetos que el usuario podria reconocer:

```text
Precios compra venta - Ene 2026 - v1
Demanda planta cliente - medicion corregida - v3
Hidrologia seca sintetica - escenario planificacion - v2
Afluentes observados DGA - invierno 2025 - v1
```

Cada set puede contener una o varias senales. Un archivo simple podria crear un
set con `timestamp`, `duration_hours` y `import_price_usd_per_mwh`. Un archivo
mas completo podria crear precios, demanda y disponibilidad solar en el mismo
set si comparten el mismo horizonte. El PRD debe decidir si la UI recomienda
sets "paquete" o sets mas pequenos por dominio, pero la BBDD deberia soportar
ambos.

La tabla de senales es critica porque evita que el sistema dependa de nombres
de columnas del Excel. La columna puede llamarse `Precio Compra`, pero la senal
canonica debe ser `import_price_usd_per_mwh`. Lo mismo aplica a
`load_demand_mw`, `renewable_available_power_mw`, `natural_inflow_m3s`,
`minimum_flow_m3s` y futuras senales.

La edicion manual debe estar acotada y auditada. TS-2 no necesita un Excel
completo dentro del navegador, pero si debe permitir correcciones puntuales o
edicion tabular razonable. Cada cambio debe recalcular hash y registrar quien
lo hizo. Si la serie ya fue usada por corridas, esas corridas no cambian porque
guardaron el hash/revision original.

La importacion debe guardar suficiente metadata para explicar errores despues.
Si una fila falla por timestamp duplicado o valor negativo, la UI debe poder
decir que fuente, hoja, columna y fila causaron el problema. Si una columna fue
mapeada a una unidad canonica, tambien deberia quedar registro de unidad origen
y unidad destino, aunque al inicio no se implementen conversiones.

La validacion temporal debe ser estricta: timestamps ordenados, duraciones
positivas, inicio/fin coherentes, sin duplicados y timezone explicito. Esto es
especialmente importante para Chile por cambios de hora. La recomendacion es
guardar timestamps como instantes y conservar `America/Santiago` como timezone
de interpretacion/visualizacion cuando corresponda.

TS-2 termina bien si el usuario ya puede construir una biblioteca de series en
BBDD, revisarla, corregirla y versionarla, aunque todavia no exista el dropdown
dentro del caso.

## Iteracion TS-3: Variantes De Series Por Caso, Default Y Rango De Fechas

La tercera iteracion es donde aparece la experiencia que motivacion este
roadmap: abrir un caso, elegir una version de series desde un dropdown, elegir
un rango de fechas y correr. En esta etapa, las series ya viven en BBDD y el
caso ya distingue topologia y parametros. Ahora hay que unir esas piezas.

La pieza central es la variante de input. Una variante de input es una
seleccion nombrada de series para un caso. Por ejemplo, para el mismo caso se
podrian tener variantes como:

```text
Default
Hidrologia seca
Precios altos
Forecast actualizado
Demanda corregida cliente
```

Cada variante resuelve las senales necesarias para correr: precio de compra,
precio de venta, demanda, disponibilidad renovable, afluentes hidraulicos,
caudales minimos u otras que el contrato requiera. El caso debe tener una
variante default. La UI abre con esa default, pero permite cambiarla antes de
correr.

Tambien se debe introducir formalmente el rango de fechas de la corrida. Una
version de series puede contener meses o anos de datos; la corrida deberia usar
un slice continuo de ese horizonte. El sistema debe validar que todas las
senales requeridas cubren ese rango, que sus periodos calzan y que no hay gaps
inesperados. En esta etapa no se recomienda resampling automatico: si las
series no calzan, la corrida debe fallar con un mensaje claro.

Al ejecutar, el backend debe construir un snapshot tecnico inmutable combinando:

```text
TopologyVersion + ParameterVersion + InputSeriesVariant + DateRange
```

Ese snapshot puede seguir guardandose como `ScenarioVersion` por compatibilidad,
pero la UI no deberia obligar al usuario a pensar en ello. Para el analista, el
flujo deberia sentirse como "corri este caso con esta variante y este rango".

El resultado esperado es que el mismo caso pueda correrse dos o mas veces con
distintas variantes de series sin duplicar la topologia ni los parametros. Cada
run debe registrar exactamente que sets, revisiones, hashes y rango uso.

El PRD de TS-3 debe cerrar que senales son obligatorias por tipo de caso, como
se elige la variante default, como se crean variantes nuevas, como se muestran
errores de cobertura temporal y como se crea o reutiliza el snapshot ejecutable.

### Detalle Adicional

TS-3 es la iteracion mas importante desde la perspectiva de flujo de usuario. Es
donde el analista deja de pensar "creare otro scenario version" y empieza a
pensar "correre este caso con otra version de datos". El foco no es crear mas
tablas por crear tablas; es lograr que el caso tenga variantes de entrada claras
y usables.

Una variante de input debe ser una configuracion nombrada de bindings. No
contiene necesariamente valores; apunta a sets/senales versionadas. Por ejemplo:

```text
Variante: Default
  precio compra -> Precios Ene 2026 v1 / import_price_usd_per_mwh
  precio venta  -> Precios Ene 2026 v1 / export_price_usd_per_mwh
  demanda       -> Demanda base v2 / load_demand_mw
  afluente R1   -> Hidrologia normal v1 / natural_inflow_m3s

Variante: Hidrologia seca
  precio compra -> Precios Ene 2026 v1 / import_price_usd_per_mwh
  precio venta  -> Precios Ene 2026 v1 / export_price_usd_per_mwh
  demanda       -> Demanda base v2 / load_demand_mw
  afluente R1   -> Hidrologia seca v3 / natural_inflow_m3s
```

La variante default debe existir para que el caso sea rapido de correr. La UI
puede crearla automaticamente cuando el usuario vincula las primeras series
requeridas. Despues, crear una variante nueva deberia poder hacerse clonando la
default y cambiando solo algunos bindings. Esto evita que el usuario tenga que
remapear todas las senales cada vez.

El dropdown del caso deberia mostrar variantes, no sets sueltos. El set es una
pieza tecnica de datos; la variante es la combinacion coherente que corre el
caso. El usuario puede abrir la variante para editar sus bindings, pero al
correr solo deberia necesitar elegir la variante y el rango.

El rango de fechas debe validarse contra todos los bindings requeridos. Si el
usuario selecciona enero completo y una serie de afluentes termina el 20 de
enero, la corrida no deberia generarse. El error debe decir que senal falta,
para que entidad, en que fechas y que variante esta incompleta.

Al correr, el sistema debe crear o reutilizar un snapshot tecnico. Ese snapshot
debe incluir:

- version de topologia usada;
- version de parametros usada;
- variante de input usada;
- revision/hash de cada set de series;
- rango de fechas;
- `system_case_json` materializado para Julia.

Esto mantiene la compatibilidad con el motor actual: Julia sigue recibiendo un
caso completo. La diferencia es que la construccion del caso ahora viene de
capas seleccionables y no de un JSON monolitico editado a mano.

La UI de TS-3 deberia mostrar claramente el estado de la variante: completa,
incompleta, stale o lista para correr. Si un set de series cambia despues de
validar la variante, debe aparecer stale hasta revalidar. Si el caso cambia de
topologia o parametros y requiere nuevas senales, la variante debe mostrar que
faltan bindings.

TS-3 termina bien si se puede demostrar el flujo completo con el mismo caso:
correr default, cambiar a otra variante desde dropdown, elegir el mismo rango o
uno distinto, correr de nuevo y ver dos runs con snapshots distintos pero sin
duplicar la topologia ni los parametros.

## Iteracion TS-4: Resultados En BBDD Y ResultSeries

La cuarta iteracion debe llevar los resultados al mismo nivel operativo que los
inputs. Hoy los artifacts son muy valiosos para auditoria, pero para UI,
comparacion, dashboards y publicaciones conviene que las series principales de
resultados tambien esten indexadas en BBDD.

Esta iteracion no debe eliminar artifacts. `dispatch.csv`,
`asset_dispatch.csv`, `summary.json`, logs y snapshots deben seguir existiendo
como prueba reproducible de la corrida. Lo que cambia es que, al terminar un run
exitoso, el sistema ademas registra las salidas relevantes como series de
resultado en BBDD. Esas series deben quedar vinculadas al `run_id`, al snapshot
ejecutable, a la variante de input, al rango de fechas, a la version de
topologia, a la version de parametros y a los hashes de series de entrada.

El beneficio inmediato es que la UI puede consultar resultados sin depender
siempre de leer CSV desde disco. Tambien permite comparar runs del mismo caso,
por ejemplo "default vs hidrologia seca" o "precios v1 vs precios v2". A futuro
permite publicar resultados con mayor control, filtrar series visibles para
clientes y reutilizar ciertos outputs como inputs simulados de otro caso.

El resultado esperado es que una corrida exitosa deje dos rastros: artifacts
auditables y resultados consultables en BBDD. Las tablas y graficos principales
pueden leerse desde BBDD, manteniendo fallback a artifacts para compatibilidad o
reconstruccion.

El PRD de TS-4 debe cerrar si se reutiliza el mismo modelo de
`time_series_sets` para outputs simulados o si se crea una capa
`result_series_sets`, que columnas de artifacts se indexan al inicio, que
lineage exacto se guarda y como funcionara la comparacion entre runs.

### Detalle Adicional

TS-4 debe tratar los resultados como datos consultables, no solo como archivos.
Hoy los artifacts son suficientes para auditoria y descarga, pero son incomodos
para preguntas de producto como: comparar dos corridas, construir dashboards
rapidos, filtrar por activo, publicar solo algunas series o buscar resultados
historicos.

El primer alcance no tiene que guardar absolutamente todo. Debe priorizar las
series que ya alimentan tablas y graficos:

- precios;
- importacion/exportacion de red;
- demanda;
- generacion renovable usada y vertida;
- carga/descarga y energia de BESS;
- generacion hidraulica;
- afluente, caudal turbinado, vertimiento y almacenamiento;
- profit, costos e ingresos principales;
- filas por activo desde `asset_dispatch.csv`.

Cada resultado guardado debe tener lineage fuerte. No basta con `run_id`; el
sistema debe poder reconstruir la historia:

```text
Run 58
  caso: Sistema Maule base
  topologia: v1 hash abc
  parametros: v2 hash def
  variante input: Hidrologia seca
  rango: 2026-01-01 a 2026-01-31
  series input: precios v1 rev 3, hidrologia seca v2 rev 1
  snapshot ejecutable: scenario_version 41
```

La lectura de resultados deberia moverse gradualmente. Al principio, la UI puede
leer desde BBDD cuando hay resultados indexados y caer a artifacts cuando no.
Eso permite mantener compatibilidad con runs antiguos. Tambien conviene agregar
una herramienta de reconstruccion: dado un run exitoso con artifacts, cargar sus
resultados a BBDD si todavia no existen.

La comparacion de runs debe empezar simple. No hace falta una herramienta BI
completa. Basta con permitir comparar dos corridas del mismo caso y mostrar
diferencias por series clave, por ejemplo importacion total, generacion total,
storage final, profit acumulado o diferencias periodo a periodo para una senal
seleccionada.

Los resultados en BBDD abren una decision importante: si usar el mismo modelo
generico de `time_series_sets` con `data_kind = simulated`, o crear una capa
`result_series_sets` especializada. La opcion generica reduce duplicacion y
permite reutilizar outputs como inputs futuros. La opcion especializada puede
ser mas clara para lineage y permisos. El PRD debe decidirlo con cuidado.

TS-4 termina bien si una corrida nueva deja artifacts y resultados indexados,
si los endpoints principales pueden leer desde BBDD, y si hay una comparacion
basica entre dos runs del mismo caso.

## Iteracion TS-5: Migracion, Unificacion Y Hardening

La quinta iteracion debe evitar que el sistema termine con dos o tres modelos
distintos compitiendo para representar series. Para llegar rapido al valor, TS-1
a TS-4 pueden convivir con estructuras actuales como `scenario_drafts` y
`hydraulic_time_series_sets`. Pero despues hay que unificar la semantica y
cuidar migracion, compatibilidad, permisos, performance y auditoria.

Esta iteracion debe revisar los caminos existentes:

- series guardadas dentro de `ScenarioDraft`;
- series hidraulicas versionadas en tablas especificas;
- fuentes CSV/XLSX del editor estructurado;
- scenario versions historicas que ya tienen `system_case_json` materializado;
- resultados antiguos que solo existen como artifacts.

El objetivo no necesariamente es migrar todo de golpe. Puede haber adaptadores
de lectura, herramientas de reconstruccion o migraciones parciales. Lo
importante es que hacia adelante exista una sola manera conceptual de crear,
editar, seleccionar, correr y auditar series.

Tambien debe cerrarse la parte operacional: indices para volumen realista,
politicas de retencion, reglas de borrado, permisos para series visibles a
clientes, auditoria de revisiones, manejo de stale validations y herramientas
para reconstruir resultados en BBDD desde artifacts si algo falla.

El resultado esperado es que el modelo nuevo no sea solo una capa encima, sino
la base estable del producto. Lo legacy puede seguir leyendose, pero las nuevas
features deben escribir al modelo comun.

El PRD de TS-5 debe cerrar que se migra, que se adapta, que queda deprecado,
como se protege compatibilidad con corridas previas y que garantias de auditoria
son necesarias antes de considerar cerrado el cambio de arquitectura.

### Detalle Adicional

TS-5 es una iteracion de consolidacion. No deberia iniciarse hasta que TS-2,
TS-3 y TS-4 hayan probado el modelo nuevo con flujos reales. Su objetivo es
evitar que el sistema quede con una capa moderna para unas pantallas y otra
capa legacy para otras, porque eso haria mas dificil mantener validaciones,
permisos y auditoria.

Un primer trabajo de TS-5 es inventariar todos los lugares donde hoy existen
series o datos temporales:

- CSV/XLSX guardados en `ScenarioDraft`;
- `validated_rows` dentro del documento del draft;
- `hydraulic_time_series_sets` y puntos especificos de hidraulica;
- `system_case_json` historicos con series materializadas;
- artifacts de runs;
- resultados leidos dinamicamente desde CSV.

Para cada uno hay que decidir una estrategia: migrar, adaptar, congelar como
legacy o reconstruir bajo demanda. No todo necesita migracion fisica inmediata.
Por ejemplo, una `scenario_version` historica puede seguir siendo un snapshot
valido sin desarmarse en tablas nuevas. Pero si el usuario quiere reutilizar sus
datos como variante editable, deberia existir un camino explicito para extraer
series hacia el catalogo comun.

La compatibilidad con hidraulica es un punto delicado. El editor hidraulico ya
tiene tablas especificas de series que funcionan. TS-5 debe decidir si esas
tablas pasan a ser solo un adapter de lectura, si se migran a las tablas
genericas o si se mantienen temporalmente con escritura dual. La recomendacion
de largo plazo es que nuevas escrituras usen el modelo generico.

Tambien hay que revisar cardinalidad de `Scenario` y `OptimizationCase`. Si se
decide que un scenario puede contener varios casos, TS-5 es el momento adecuado
para migrar constraints, rutas y UI. Si se decide mantener uno por scenario, el
producto debe nombrarlo asi y no dejar ambiguedad.

La auditoria debe endurecerse: quien edito una serie, desde que fuente, que
revision reemplazo a cual, que corridas usaron cada revision, que validaciones
quedaron stale y que snapshots siguen inmutables. Esto tambien afecta permisos:
un cliente podria ver resultados publicados, pero no necesariamente series de
input o fuentes originales.

En performance, TS-5 debe agregar indices y revisar volumen real. No conviene
optimizar antes de medir, pero si conviene asegurar patrones basicos: leer un
set por rango, leer senales de una variante, cargar resultados de un run,
comparar dos runs y borrar/reconstruir datos derivados sin tocar snapshots
auditables.

TS-5 termina bien si el equipo puede decir: "el modelo comun es la fuente de
verdad para nuevas series y resultados; lo viejo tiene adaptadores o migracion;
las corridas historicas siguen reproducibles; y la UI ya no mezcla conceptos".

## Iteracion TS-6 Futura: Transformaciones Y Automatizacion

La sexta iteracion no deberia planificarse en detalle todavia. Es trabajo
futuro para cuando existan datos reales y se conozcan los patrones de uso.

Esta iteracion cubriria operaciones avanzadas sobre series:

- resampling;
- interpolacion;
- escalamiento;
- combinacion de escenarios;
- forecast ingestion;
- programas externos con vigencia formal;
- rolling horizon;
- reruns programados usando variantes;
- comparacion avanzada de muchos runs;
- particionamiento fisico o TimescaleDB si el volumen lo exige.

La razon para dejar esto fuera del core es practica. Implementar
transformaciones antes de tener el modelo basico usado con datos reales aumenta
el riesgo de sobredisenar. Primero hay que probar que las series se pueden
cargar, versionar, seleccionar, cortar por rango, correr y guardar resultados.
Despues se vera que transformaciones tienen valor.

El resultado esperado de TS-6, si se ejecuta, seria que el sistema pueda crear
nuevas versiones de series derivadas de otras de forma declarativa y auditable,
sin scripts libres ni transformaciones implicitas al momento de correr.

### Detalle Adicional

TS-6 debe verse como una capa de transformaciones declarativas. No deberia
permitir scripts arbitrarios guardados en BBDD, porque eso complica seguridad,
reproducibilidad y mantenimiento. En cambio, deberia haber transformaciones
allowlisted con version de implementacion y parametros validados.

Ejemplos de transformaciones:

```text
resample_hourly_to_daily
fill_missing_linear
scale_signal
combine_price_scenarios
derive_availability_from_outage_events
clip_negative_values
shift_timezone_display
```

Cada transformacion deberia producir un nuevo set de series o una nueva
revision derivada, con lineage claro hacia los sets de entrada. Si cambia el
set origen o cambia la version de implementacion, el output queda stale o debe
regenerarse.

La automatizacion tambien debe apoyarse en variantes. Un rerun programado no
deberia decir "corre este JSON"; deberia decir "corre este caso, con esta
parametrizacion, esta variante o regla de seleccion de series, y este rango".
Eso permite rolling horizon, ejecuciones diarias o forecasts sin romper el
modelo conceptual.

Esta iteracion puede incluir integraciones externas, pero solo despues de que
el modelo local este probado. Una API externa de precios o forecasts deberia
entrar como `time_series_source` y terminar generando `time_series_set`, igual
que un Excel. La diferencia es el origen, no la semantica.

TS-6 termina bien si las transformaciones son auditables y repetibles, y si el
usuario puede entender que una serie no fue cargada directamente, sino derivada
desde otras con una receta versionada.

## Orden Recomendado

1. TS-1: separar topologia y parametros.
2. TS-2: crear catalogo generico de series en BBDD.
3. TS-3: variantes/default/rango/dropdown/run.
4. TS-4: resultados en BBDD.
5. TS-5: migracion, unificacion y hardening.
6. TS-6: transformaciones avanzadas, solo si el uso real lo justifica.

## Preguntas Que Aun Requieren Confirmacion

Estas son las preguntas que no conviene cerrar solo desde el repo:

1. El usuario necesita multiples `OptimizationCase` dentro de un mismo
   `Scenario`, o basta con uno por scenario pero mejor nombrado?
2. Cuando se edita una version de series ya usada por corridas, la UI debe
   crear automaticamente una nueva version visible o solo una nueva revision?
3. El rango de fechas debe permitir gaps o siempre debe ser continuo?
4. Los resultados en BBDD deben guardar todas las columnas de artifacts o solo
   un subconjunto canonico para UI y comparacion?
5. Los clientes deben poder ver series de entrada, o solo resultados derivados?

## Recomendacion Final

No intentaria implementar todo en una sola iteracion. El primer corte correcto
es TS-1 + TS-2 + TS-3. Ese bloque ya entrega la experiencia central:

```text
Caso
-> parametros estables
-> dropdown de version de series
-> rango de fechas
-> run reproducible
```

TS-4 agrega el segundo bloque de valor: resultados consultables y comparables
desde BBDD. TS-5 evita que queden dos sistemas paralelos de series y cierra la
migracion.
