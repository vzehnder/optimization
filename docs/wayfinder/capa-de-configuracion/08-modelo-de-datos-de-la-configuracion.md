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

**Restriccion confirmada por el portal cliente**: existe una configuracion de
portal por proyecto, compartida por todos los usuarios cliente asignados. Esa
configuracion guarda forma y vocabulario reutilizables; cada publicacion sigue
eligiendo corrida, titulo, notas, fecha y artefactos permitidos.

**Restriccion confirmada por Donde aterriza la edicion de series del
operador**: la consola necesita identidad estable, separada de sus versiones
de configuracion. Esa identidad posee copias operativas de los sets elegidos;
cada copia registra set y revision canonicos de origen, sobrevive cambios de
configuracion y se archiva al cambiar de base o reiniciar. El modelo debe
representar tambien su lease de edicion y revision vigente sin exponer estos
conceptos al usuario operador.

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
- **Cardinalidad de la consola de operador**: la del portal ya quedo fijada en
  una por proyecto. Un proyecto con tres escenarios puede necesitar varias
  consolas; falta decidir si son subconfiguraciones nombradas dentro del mismo
  documento o entidades separadas.
- **Estado publicado/borrador**: si el ingeniero puede trabajar una
  configuracion sin que el operador la vea todavia.

## Restricciones confirmadas por la regla fail-closed

**Edicion del operador frente a la regla fail-closed** agrega dos exigencias al
modelo de datos:

- la copia operativa se representa como **set no derivado**: sin receta de
  transformacion ni dependencias grabadas, con el linaje al set y revision de
  origen como metadata inerte visible para `analyst` y `admin`. Si conservara
  la receta, la primera edicion la marcaria stale-derivada y el unico camino de
  salida borraria las ediciones;
- la dependencia de la variante de la consola sobre esa copia tiene que ser
  **direccionable de forma puntual**, para refrescar su `recorded_hash` en la
  transaccion del guardado sin tocar las dependencias `topology` ni
  `parameters` de la misma variante.

## Restricciones confirmadas por el contrato de la tabla editable

**Contrato de la tabla editable y del pegado desde Excel** deja tres exigencias
sobre el modelo y le quita una cuarta:

- la configuracion declara los **grupos** del analista: nombre, orden, y las
  señales que contiene cada uno, con su etiqueta y su condicion de editable o
  solo lectura. Un grupo puede mezclar señales de copias operativas distintas,
  asi que el modelo debe poder resolver, desde un grupo, el conjunto de copias
  que un guardado va a tocar;
- la configuracion declara los **tramos seleccionables** por el operador y su
  granularidad. El tramo acota la edicion, no solo la vista, asi que es parte
  del contrato y no una preferencia de UI;
- el guardado es transaccional entre copias, de modo que la relacion
  grupo → copias operativas tiene que ser consultable sin recorrer los valores;
- **no hace falta campo de formato numerico.** El parser deduce el separador
  decimal de la estructura del texto y rechaza el unico caso ambiguo, asi que el
  locale deja de ser configuracion.
