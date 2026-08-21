---
id: 09
title: "Extensibilidad del registro de senales canonicas"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
blocked_by: [07]
---

## Question

¿Que hace falta para que agregar una senal canonica nueva sea barato — y donde
esta hoy el costo?

El encuadre fue explicito: se disena la extensibilidad, no se implementa la
senal. El caso de prueba es el que motivo la pregunta: un limite de potencia
minima o maxima por unidad, variable en el tiempo. Hoy no existe. El registro
canonico (`app/time_series_catalog.py`) tiene 8 claves y `power_max_mw` es un
escalar del draft, no una serie.

A resolver:

- **Mapa de costos**: enumerar cada lugar que hay que tocar hoy para agregar
  una senal — registro canonico, validacion de import CSV/XLSX, validacion de
  edicion manual, derivacion de "senales requeridas" de un caso, bindings de
  variante, materializacion del `system_case`, contrato Julia, indexado de
  resultados TS-4, tabla editable del operador, configuracion. La lista misma
  es el resultado principal.
- **Cual de esos pasos es evitable por diseño** y cual es irreducible. La
  validacion por senal probablemente puede ser declarativa; el contrato Julia
  probablemente no puede evitarse.
- **Senales escalares vs. vectoriales**: la extension real que pide el caso de
  prueba no es "una senal mas", es convertir un parametro escalar en una serie.
  ¿El diseño distingue esos dos tipos de extension? Son costos muy distintos y
  conviene no confundirlos en el spec.
- **Que parte del contrato Julia queda como dependencia declarada**: el spec
  debe decir con precision que cambiaria en el motor (v3) sin especificarlo,
  para que el esfuerzo futuro arranque desde ahi y no desde cero.
- **La tabla editable no debe conocer senales por nombre**: si la consola tiene
  una lista fija de columnas soportadas, cada senal nueva la toca. Decidir como
  se deriva del registro.

**Insumo de** [Inventario de la superficie configurable existente](01-inventario-superficie-configurable.md),
seccion E: el registro de entrada (8 claves) y el de salida
(`DISPATCH_SIGNAL_KEY_CATALOG`, 24 claves) son vocabularios **distintos e
independientes**; el mapa de costos tiene que recorrer los dos. Ademas la tabla
sufijo-a-unidad esta duplicada entre backend y frontend, que es un lugar mas
donde una senal nueva puede quedar a medias.

El entregable es la parte del spec que dice: "para agregar la senal X, se toca
esto, en este orden, y esto ya no hay que tocarlo".

## Restricciones confirmadas por el contrato de la tabla editable

**Contrato de la tabla editable y del pegado desde Excel** ya resolvio el punto
de la tabla editable que este ticket dejaba pendiente:

- la tabla **no conoce señales por nombre**. Las columnas se derivan del grupo
  configurado, y de cada señal solo consume su `unit` y su `nonnegative` del
  registro canonico. Una señal nueva entra sin tocar la superficie de edicion,
  siempre que el registro la declare;
- el parser numerico es unico para todas las señales y no depende de la señal ni
  del locale, asi que tampoco es un lugar a tocar;
- lo que si es por señal, y por tanto entra en el mapa de costos: `unit`,
  `nonnegative`, `entity_type`, y la traduccion de su etiqueta en la
  configuracion.

## Restricciones confirmadas por el modelo de datos

**Modelo de datos de la configuracion por proyecto** agrega un lugar al mapa de
costos y aclara la distincion que este ticket pedia no confundir:

- la **etiqueta por señal** vive en el documento de configuracion de la consola
  (`operator_console_config.v1`), dentro del grupo que la declara. Una señal
  nueva que deba aparecer en una consola existente obliga a editar ese
  documento; no se hereda del registro canonico;
- los grupos declaran señales por `signal_key` mas `entity_type`/`entity_id`, no
  por posicion, asi que agregar una clave al registro **no invalida** las
  configuraciones existentes;
- el parametro escalar expuesto y la señal vectorial son mecanismos **distintos**
  en el modelo: el primero es un puntero `{asset_id, field}` con overlay de
  override sobre el `system_case`; la segunda es una columna de la copia
  operativa. Convertir un escalar en serie —el caso de prueba de este ticket, el
  limite de potencia por unidad— es por tanto **mover un campo de un mecanismo
  al otro**, no agregar una clave mas. El mapa de costos debe contarlo asi, o
  subestimara el trabajo.

## Restricciones confirmadas por el contrato del payload

**Contrato del payload de las superficies configuradas** le quita dos lugares al
mapa de costos de este ticket y le confirma uno:

- **el contrato de payload no es un lugar a tocar.** Ninguna de las dos
  superficies configuradas nombra columnas ni parametros por `signal_key` ni por
  `{asset_id, field}`: viajan con el `id` que declara el documento de
  configuracion, y el backend lo resuelve al recibir un guardado o una
  ejecucion. Una señal canonica nueva no toca `portal_payload` ni
  `console_payload`;
- **la tabla sufijo-a-unidad duplicada entre backend y frontend deja de ser un
  lugar a medias para estas superficies.** El payload lleva `unit` por columna y
  por serie de grafico, derivada del registro canonico en el backend. La copia
  del frontend sigue viva para la aplicacion del analista, pero la consola y el
  portal ya no la consultan, asi que una señal nueva no puede quedar sin unidad
  ahi;
- **se confirma lo que si es por señal**: `unit`, `nonnegative`, `entity_type` y
  la etiqueta en el documento de configuracion. El mapa de costos debe contar
  ademas que una señal nueva que deba aparecer en una consola o portal ya
  existentes obliga a editar ese documento a mano.

## Resolucion

Decision tomada en sesion de grilling el 2026-08-21, con **lente MVP explicito**:
lo basico completo, sin funcionalidad de mas. Cada recorte queda nombrado abajo.

### El reencuadre: el caso de prueba no es caro, es inexpresable

El ticket pedia un mapa de costos. El mapa existe y esta abajo, pero el hallazgo
que lo reordena es otro: agregar un limite de potencia por unidad **no tiene
costo alto, tiene costo infinito**, porque hoy no se puede ni declarar.

`_ONE_BUS_ENTITY_SIGNALS` (`app/required_signals.py:12`) es un
`dict[str, tuple[str, str]]`: el valor es **una** tupla, asi que un tipo de nodo
requiere **exactamente una** señal. La estructura no puede expresar "un `load`
necesita demanda *y* limite de potencia". No es una linea mas en el mapa de
costos; es un muro.

El camino hidraulico parecia ser la salida —usa una lista declarativa
`hydraulic_network.required_time_series`— pero no lo es: `src/system_dispatch.jl:419`
rechaza toda clave distinta de `natural_inflow_m3s`, y `minimum_flow_m3s` ni
siquiera pasa por ahi (es un caso especial aparte, `src/system_dispatch.jl:446`
y `app/required_signals.py:110`). **La declaratividad existente es forma de
transporte, no mecanismo.**

### Decision 1: la derivacion one-bus pasa a lista, como forma sin comportamiento

El spec declara que `_ONE_BUS_ENTITY_SIGNALS` pasa de `dict[str, tuple]` a
`dict[str, list[tuple]]`, con las cuatro entradas actuales quedando como listas
de un elemento. Es el unico cambio que convierte "rediseñar la derivacion" en
"agregar una entrada", y no agrega ninguna señal ni toca el motor.

**Este mapa lo especifica; no lo implementa.** La suite existente es el testigo
de que las cuatro señales actuales siguen derivandose igual.

### Decision 2: los dos mecanismos NO se unifican (recorte MVP)

Sin la lente MVP habria correspondido un unico mecanismo declarativo para one-bus
e hidraulico. Con ella, no: unificarlos obliga a tocar dos esquemas Julia con
validadores y runners separados, y eso es refactor de la cadena interna, que el
mapa ya declaro fuera de alcance.

Lo que si se fija es que **ambos produzcan la misma forma de salida**: una lista
de `{entity_type, entity_id, signal_key}`. One-bus la deriva de la topologia,
hidraulico la trae del draft. Mismo tipo, productores distintos. La unificacion
real queda como deuda nombrada, no como trabajo de este mapa.

### Decision 3: el registro se expone por API y muere la copia del frontend

`TIME_SERIES_SIGNAL_CATALOG` no se expone nunca por API, y
`frontend/src/timeSeriesCatalogMapping.ts` es una copia a mano de las 8 claves:
lista de opciones, mapa de unidades, arreglo `scalarKeys` y ramas por señal. Hoy
una señal nueva puede quedar a medias ahi sin que nada lo detecte.

El spec declara un endpoint de lectura del registro que devuelve exactamente los
campos que ya tiene —`signal_key`, `unit`, `entity_type`, `nonnegative`— y de ahi
el frontend deriva las opciones y las unidades. Pasa por
`require_authenticated_app_boundary` como cualquier superficie nueva.

Se verifico que la rama anidada-vs-plana del frontend tambien es derivable: las
tres señales que hoy trata como anidadas (`load_demand_mw`,
`renewable_available_power_mw`, `hydro_inflow_m3s`) son exactamente las tres cuyo
`entity_type` empieza con `component:`. La condicion por nombre se reemplaza por
esa, y deja de ser un lugar por señal.

Es un endpoint de lectura sin estado: cabe en el MVP y elimina una clase entera
de duplicacion permanentemente.

### Decision 4: escalar y vectorial son dos extensiones distintas, y el spec las separa

Confirmado en el codigo del motor, no solo en el modelo de datos:

- **vectorial** en Julia es **campo tipado de struct**, no entrada de registro:
  `SystemPeriodData` (`src/system_dispatch.jl:31`) tiene un campo por señal, y
  `SystemOptimizationData` (`:99`) una `Matrix{Float64}` por señal;
- **escalar** es campo del struct del activo:
  `HydroAssetParameters.power_max_mw` (`:87`), consumido como **cota de variable
  JuMP** en `src/model/base_model.jl:50`.

Convertir el escalar en serie —el caso de prueba— es mover el campo de struct de
activo a matriz por periodo, reindexar, y **cambiar la cota de la variable de
escalar a por-periodo**. Eso es cambio de modelo de optimizacion, no de parseo.
El spec cuenta los dos costos por separado; confundirlos subestima el trabajo por
un orden de magnitud.

### Decision 5: el registro de salida no se toca (recorte MVP)

`DISPATCH_SIGNAL_KEY_CATALOG` (`app/result_indexing.py:37`, 26 claves) ya es un
dict plano: agregar una clave es una linea. Es lo mas barato del mapa entero y no
necesita diseño.

Lo unico que el spec debe decir explicitamente es que **los dos vocabularios son
independientes**: una señal de entrada nueva **no** produce automaticamente una
señal de salida. Si el resultado tiene que mostrarla, es una segunda entrada, en
el otro registro, decidida aparte.

### Decision 6: la dependencia del motor, con la correccion de version

**El mapa asumia mal que "contrato Julia v3" era futuro. v3 ya existe.**
`src/system_dispatch.jl:9-12` define v1, v2 y v3; el conjunto de versiones
soportadas por el validador one-bus solo contiene v1 y v2 porque **v3 es el
esquema hidraulico actual**, con validador y runner propios
(`validate_hydraulic_v3_system_case_document`, `run_hydraulic_v3_system_case`),
despachado por `schema_version` en `:1396`.

La dependencia que el spec declara —sin especificarla— es por tanto de tres
tamaños distintos, y ninguno se llama v3:

1. **señal vectorial en el camino hidraulico**: levantar la allowlist de `:419`
   y agregar el parseo del campo por periodo. Es el barato;
2. **señal vectorial en el camino one-bus (v1/v2)**: campo nuevo en
   `SystemPeriodData` mas `Matrix{Float64}` nueva en `SystemOptimizationData`.
   Structs tipados, no registro: no hay forma de hacerlo declarativo sin
   reescribir el cargador;
3. **escalar a serie**: lo anterior mas el cambio de cota JuMP. Es el que
   justifica una version de contrato nueva, y esa version es **v4 o una
   ampliacion de v3**, nunca "v3".

### La receta: para agregar una señal canonica nueva se toca esto, en este orden

Asumiendo aplicadas las decisiones 1 y 3:

1. `app/time_series_catalog.py` — una entrada con `unit`, `entity_type`,
   `nonnegative`. **Declarativo.**
2. `app/required_signals.py` — un elemento mas en la lista del tipo de nodo que
   la requiere. **Declarativo, y solo posible por la decision 1.**
3. Motor Julia — segun cual de los tres tamaños de la decision 6 aplique.
   **Irreducible.**
4. `app/draft_editor.py` — materializacion del `system_case`: el periodo gana el
   campo. **Irreducible mientras el system_case sea un documento de campos
   nombrados.**
5. `app/time_series_ingestion.py` — mapeo de columna de importacion.
   **Reducible, no reducido**: hoy son ramas por señal; la lente MVP dejo este
   refactor afuera porque no bloquea nada.
6. `operator_console_config.v1` — la etiqueta, a mano, en **cada consola
   existente** que deba mostrarla. Costo por consola, no por señal. Se respeta lo
   que cerro **Modelo de datos de la configuracion por proyecto**: la etiqueta no
   se hereda del registro.
7. `app/result_indexing.py` — **solo si** la señal debe volver en resultados, y
   como entrada del otro vocabulario.

### Lo que ya no hay que tocar

Confirmado por los tickets cerrados, y verificado contra el codigo:

- **tabla editable del operador**: deriva columnas del grupo configurado y de la
  señal solo consume `unit` y `nonnegative`;
- **parser numerico**: unico, independiente de señal y de locale;
- **contrato de payload**: viaja por `id` de configuracion, nunca por
  `signal_key`;
- **tabla sufijo-a-unidad del frontend**: el payload lleva `unit` derivada del
  registro en backend; consola y portal ya no la consultan. Con la decision 3, la
  copia del analista tambien deja de existir.

### Mapa de costos verificado (evidencia)

Conteo de literales de las 8 claves canonicas por archivo, que es lo que hoy hay
que revisar a mano ante una señal nueva:

| Lugar | Archivo | Naturaleza |
|---|---|---|
| Registro de entrada | `app/time_series_catalog.py` | declarativo |
| Ingesta CSV/XLSX | `app/time_series_ingestion.py` | ramas por señal |
| Materializacion del caso | `app/draft_editor.py` | campos nombrados |
| Extraccion legacy | `app/legacy_series_extraction.py` | specs por señal |
| Señales requeridas | `app/required_signals.py` | el muro de la decision 1 |
| Registro de salida | `app/result_indexing.py` | declarativo, independiente |
| Paneles de resultado | `app/results.py` | etiquetas fijas |
| Persistencia | `app/persistence.py` | columnas SQL de precio + validacion |
| Mapeo de catalogo | `frontend/src/timeSeriesCatalogMapping.ts` | copia a mano |
| Editor de draft | `frontend/src/DraftEditor.tsx` | |
| Workspace | `frontend/src/Workspace.tsx` | familia de precio fija |

### Recortes MVP asumidos

- no se unifican los dos mecanismos de derivacion (decision 2);
- no se hace declarativa la ingesta CSV/XLSX (paso 5 de la receta);
- no se toca el registro de salida ni se conectan los dos vocabularios
  (decision 5);
- no hay migracion ni herramienta para agregar etiquetas a consolas existentes:
  es edicion a mano (paso 6);
- no se implementa ninguna señal nueva, ni se especifica v4.
