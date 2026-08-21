---
id: 08
title: "Modelo de datos de la configuracion por proyecto"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
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

## Resolucion

Decision tomada en sesion de grilling el 2026-08-21, con **corte MVP explicito**:
lo basico completo, sin funcionalidad de mas. Cada recorte asumido queda
nombrado abajo, porque todos son aditivos de revertir.

### El hueco que este ticket destapo: los parametros del operador

Los tickets 05, 06 y 07 resolvieron con detalle donde aterriza una edicion de
**series**. Sobre los **parametros** no habia una linea en todo el mapa, y el
cascaron de la consola los pone *antes* que los datos.

No era una laguna inocente. Tres hechos verificados se cruzan en una trampa:

- el caso base se genera desde el draft (`_generate_base_system_case_for_variant`
  -> `scenario_drafts.document_json`, `app/persistence.py:7070`);
- `derive_case_hierarchy_views` mete en la vista `parameters` un
  `node_parameters` con **todo campo de todo nodo que no sea `id` ni `type`**
  (`app/persistence.py:10484-10490`). El `power_max_mw` de `battery_1` esta
  dentro del hash `parameters`;
- el ticket 06 refresca **solo** la dependencia `time_series_set` y descarto
  explicitamente tocar `topology` y `parameters`.

Si la edicion de un parametro del operador llegara al draft, moveria el hash
`parameters`, la variante quedaria stale, y por regla del propio ticket 06 nadie
la refrescaria. El operador se autobloquearia al primer parametro que toca, y
encima le habria mutado el caso al analista. Es la misma trampa que el ticket 06
encontro con los sets derivados.

### Overlay de overrides, propiedad de la consola

La configuracion declara que campos son editables, con etiqueta, unidad, rango y
default. La consola guarda un conjunto `puntero -> valor` que **no toca el
draft**. Se aplica en la materializacion sobre el `system_case` devuelto,
**despues** de derivar la provenance: el hash `parameters` sigue describiendo el
caso del analista, no el override del operador.

El punto de insercion es quirurgico: en `_resolve_variant_series_for_range` la
provenance se deriva de `base_system_case` mientras el `system_case` devuelto ya
es un dict aparte (`app/persistence.py:7285`).

Es la asimetria del ticket 06 extendida a parametros: **el cambio propio del
operador no bloquea; el ajeno si.** La trazabilidad no se pierde — el valor que
realmente corrio queda en la `scenario_version` inmutable y en su
`generation_metadata`, que es donde el lineage vive.

Se descarta que el operador escriba en el draft (deadlock y mutacion del caso
compartido) y se descarta limitarlo a presets nombrados, que contradiria el
rango y default por parametro que fijo **Forma del cascaron de la consola de
operador**.

### La consola posee su propia variante

Refinamiento que emergio al bajar el modelo a la mesa, y sin el cual el ticket
05 no es implementable.

El ticket 05 manda redirigir *el binding de la consola* hacia la copia
operativa, pero los bindings viven en `case_time_series_bindings` colgando de la
variante. Si la consola compartiera la variante del analista, la primera edicion
del operador **le redirigiria el binding al analista** y le cambiaria lo que
corre.

Por eso la consola **posee una variante propia**, clonada de una variante del
analista al crearse. Esa es la que se redirige, la que queda stale por un cambio
ajeno, y la que se refresca quirurgicamente. Es lo que el ticket 06 ya
presuponia al hablar de "la variante de la consola".

No agrega motor: reutiliza variantes, bindings y `validation_dependencies` tal
como existen. El listado de variantes del analista marca las que pertenecen a
una consola mediante join, sin columna nueva en `case_input_variants`.

### Entidades

**`portal_configurations` — una por proyecto** (`UNIQUE (project_id)`).
Reemplaza a `dashboard_templates`.

**`operator_consoles` — N por proyecto, colgando del caso.** Identidad estable
separada de su configuracion, como exigio el ticket 05. Es dueña de su variante
propia, de sus copias operativas y de su overlay de overrides. Sin limite
artificial por caso; se distinguen por nombre.

**`operator_console_series_copies` — el linaje inerte.** `console_id`,
`time_series_set_id` (la copia, set plano no derivado), `origin_set_id`,
`origin_revision_number`, `created_at/by`, `archived_at`. El lease del ticket 05
vive **como columnas de esta misma fila** —`lease_holder_user_id`,
`lease_heartbeat_at`, `lease_expires_at`— no en tabla aparte. La revision
vigente no se modela: ya es el `MAX(revision_number)` de
`time_series_set_revisions`.

### Documento JSON, no columnas tipadas

Ambas configuraciones son un **documento JSON con `schema_version`**, validado
contra un esquema en codigo y con rechazo duro, siguiendo el precedente exacto
de `bess_editor_draft.v1` (`app/draft_editor.py:285`). Nueve booleanos no
aguantan campos expuestos con etiqueta, rango y default.

Versiones `portal_config.v1` y `operator_console_config.v1`. Sin migracion
silenciosa. En columnas queda solo lo consultable: `project_id`/`case_id`,
`status`, `revision`, `updated_at`, `updated_by`.

El documento de la consola declara ademas, por exigencia del ticket 07: los
**grupos** (nombre, orden, señales con etiqueta y condicion de editable) y las
**granularidades de tramo** permitidas. Un grupo puede mezclar señales de copias
operativas distintas; la relacion grupo -> copias se resuelve por las señales
declaradas sin recorrer valores.

### Puntero al campo expuesto

`{"asset_id": "battery_1", "field": "power_max_mw"}`, que resuelve contra el
`node_parameters` que `derive_case_hierarchy_views` ya construye
(`app/persistence.py:10487`).

**Puntero colgando:** se detecta **al cargar la consola**, no al guardar la
configuracion. Si el campo ya no existe en el caso, la consola bloquea ejecutar
y escala por el mismo camino que el ticket 06 definio para el stale ajeno.
Fail-closed, sin validador nuevo. Un override cuyo campo dejo de estar expuesto
queda **inerte, no se borra**.

### Versionado: no lo hay

La configuracion **no tiene historial**. Un contador `revision INTEGER` que sube
en cada guardado, mas `updated_at` y `updated_by`. La auditoria que exigen los
tickets 04 y 05 estampa ese contador.

La configuracion **no entra en el snapshot inmutable de la corrida**: no afecta
el resultado matematico, solo la interfaz. Queda dicho explicitamente para que
nadie lo mezcle con el lineage de TS-1/TS-3.

### Publicado/borrador

Dos estados en la misma fila: `draft` | `active`. En `draft` no es visible ni
operable por `external`. Sin flujo de aprobacion y sin copia paralela.

### Migracion de `dashboard_templates`

La tabla vieja **no se borra ni se migra destructivamente**: queda muerta, lo
que es coherente con que hoy no exista `DELETE` de plantillas ni de
publicaciones. La migracion crea una configuracion de portal por proyecto a
partir de la plantilla que usa su publicacion publicada mas reciente.

Esto resuelve la niebla que el mapa tenia abierta sobre este punto.

### Lo que el modelo NO necesita

- **Refresco quirurgico del ticket 06**: `validation_dependencies` ya es
  direccionable por `(owner_type, owner_id, dependency_type, dependency_id)` con
  `UNIQUE` (`app/persistence.py:740`). Es un `UPDATE` puntual, cero cambios de
  modelo.
- **Campo de formato numerico**: el ticket 07 lo elimino.
- **Rango del selector de periodo**: se deriva de `time_series_periods` de la
  copia.
- **Marcador de no-stale para la copia**: los sets no derivados no tienen
  dependencias grabadas y nunca estan stale (`app/persistence.py:3360-3365`).

### Cortes MVP asumidos

Todos aditivos de revertir. Se listan para que nadie los confunda con
descuidos:

- **La publicacion deja de elegir plantilla.** Conserva corrida, titulo, notas,
  fecha y artefactos. Es un cambio de comportamiento visible sobre lo que hoy
  funciona, y es lo que el ticket 03 cerro.
- **La configuracion no es reconstruible hacia atras.** El contador dice que
  revision corrio, no que contenia. Revertirlo es una tabla de historial
  aditiva.
- **Editar una consola `active` la cambia en vivo** bajo el operador. El daño es
  de presentacion, no de calculo; la alternativa es maquinaria real.
- **Solo escalares de nodo** como campo expuesto. Nada anidado, ni curvas, ni
  listas.
- **Granularidades de tramo de un enum cerrado** —dia, semana, mes, horizonte
  completo— en vez de tramos arbitrarios.

### Consecuencias para el resto del mapa

- Desbloquea **Alcance de marca del portal cliente**, que esperaba este modelo.
- **Superficie del ingeniero para consolas bloqueadas** hereda un caso nuevo: el
  override colgando por un campo que el ingeniero borro o renombro. Y gana una
  facilidad: listar las consolas de un proyecto pasa a ser una consulta, no una
  derivacion.
- **Contrato del payload de las superficies configuradas** hereda que el
  `revision` de la configuracion y los identificadores de copia operativa son
  internos y no cruzan la frontera.
- **Extensibilidad del registro de senales canonicas** gana un lugar mas en su
  mapa de costos: la etiqueta por señal vive en el documento de configuracion.

## Adenda: paneles de resultado en el documento de la consola

Agregada el 2026-08-21 al cerrar **Contrato del payload de las superficies
configuradas**, que destapo el hueco.

`operator_console_config.v1`, tal como quedo especificado arriba, declara
parametros expuestos, grupos, señales y granularidades de tramo, pero **no
declara paneles de resultado**. El cascaron de la consola exige que la consola
muestre resultados e historial, con apertura de resultados desde el historial y
comparacion de dos corridas.

El documento gana por tanto una seccion de paneles de resultado con **la misma
gramatica que `portal_config.v1`**: KPIs por path de hasta tres segmentos,
graficos del catalogo fijo, tablas con columnas etiquetadas. Es la contrapartida
natural de que el payload tenga un unico bloque de resultados compartido entre
ambas superficies.

Adicion aditiva: no cambia entidades, columnas ni ninguna otra decision de este
ticket.
