---
id: 08
title: "Modelo de datos de la configuracion por proyecto"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
blocked_by: [01, 02, 03]
---

## Question

¿Que entidad guarda la configuracion, que forma tiene y como se versiona?

Es la columna vertebral del spec. Solo se puede responder despues de conocer la
forma de ambos cascarones (que hay que parametrizar) y el inventario de lo que
hoy esta hardcodeado (cuanta superficie hay que cubrir).

La superficie a cubrir ya esta medida: ver la seccion F de
[Inventario de la superficie configurable existente](01-inventario-superficie-configurable.md).
Son cuatro capas —visibilidad de seccion, etiquetas, contrato de payload y
punteros al caso— y solo la primera existe hoy.

A decidir:

- **Tabla nueva o extension de `dashboard_templates`**: la tabla actual ya es
  por proyecto y ya parametriza el portal cliente. ¿La configuracion nueva la
  absorbe, la reemplaza, o son dos objetos distintos? De aqui sale la respuesta
  a la migracion que hoy esta en la niebla del mapa.
- **Columnas tipadas vs. documento JSON**: los 9 booleanos de hoy son columnas.
  Una configuracion que expone campos arbitrarios con etiqueta, rango y default
  no cabe en columnas. Un documento JSON con esquema versionado sigue el
  precedente de `bess_editor_draft.v1` y de `TRANSFORMATION_REGISTRY`: esquema
  en codigo, datos validados contra el. Decidir y justificar.
- **Version de esquema**: si es documento, necesita `schema_version` y politica
  de rechazo, como hace el draft hoy.
- **¿Se versiona la configuracion en si?** Cambiar que campos ve el operador
  cambia lo que puede correr. ¿Hace falta historial, o basta con auditoria de
  quien la modifico y cuando? Notar que la configuracion **no** entra en el
  snapshot inmutable de la corrida: no afecta el resultado matematico, solo la
  interfaz. Conviene decirlo explicitamente en el spec para que nadie lo mezcle
  con el lineage de TS-1/TS-3.
- **Como se referencia un campo expuesto**: la configuracion tiene que apuntar
  a algo dentro del caso ("el `power_max_mw` del activo `bess_1`"). ¿Que forma
  tiene ese puntero y que pasa cuando el caso cambia y el puntero queda
  colgando? Un caso editado puede invalidar una configuracion publicada.
- **Relacion con las variantes**: la consola del operador corre sobre una
  variante. ¿La configuracion fija cual, ofrece varias con nombre legible, o la
  deriva? Ligado a como se presentan las alternativas de datos preparadas.
- **Una configuracion por proyecto o varias**: un proyecto con tres escenarios
  puede necesitar tres consolas distintas. El encuadre dice "ambito por
  proyecto" para *quien la edita*; falta decidir la cardinalidad.
- **Estado publicado/borrador**: si el ingeniero puede trabajar una
  configuracion sin que el operador la vea todavia.
