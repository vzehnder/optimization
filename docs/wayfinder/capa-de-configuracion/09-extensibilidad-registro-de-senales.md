---
id: 09
title: "Extensibilidad del registro de senales canonicas"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
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
