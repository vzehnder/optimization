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
