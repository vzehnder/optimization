---
id: 11
title: "Contrato del payload de las superficies configuradas"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
blocked_by: [02, 03]
---

## Question

¿Que campos exactamente cruzan la frontera hacia un usuario no-analista, y
quien recorta el payload?

El inventario mostro que hoy **no hay contrato**: `client_publication_payload`
(`app/main.py:751-795`) aplica la plantilla solo a `results` y devuelve crudos
`project`, `scenario`, `scenario_version`, `run`, `publication` y `template`.
Eso pone al alcance de un `client` autenticado las rutas de workspace, el
`stdout` y el `stderr` de la corrida, el `case_name`, el `schema_version` y los
`created_by` internos. Ademas, si `show_summary` esta encendido, el bloque de
KPIs imprime toda clave desconocida sin traducir, incluido
`source_identifiers.system_case`, que es la ruta absoluta del caso en el disco
del servidor.

Hoy nadie ve eso porque el React elige que pintar. Es decir: la promesa del
destino —"nunca ve draft, catalogo, variantes ni versiones inmutables"— se
sostiene por convencion de UI, no por construccion. Una consola de operador y
un portal cliente configurables multiplican las superficies que hacen este
mismo pase, asi que conviene fijar la regla antes de escribirlas.

A decidir:

- **Allowlist o denylist**: ¿el payload se arma enumerando lo que sale, o
  filtrando lo que no debe salir? La primera opcion falla cerrado cuando
  alguien agrega una columna a `runs`; la segunda falla abierto.
- **Donde vive el recorte**: ¿en la capa de ruta, en un serializador por perfil,
  o en la propia configuracion (el ingeniero elige que metadatos mostrar)? Ojo
  con confundir "que puede salir" (seguridad, fija) con "que se muestra"
  (configuracion, del ingeniero). Probablemente son dos filtros en serie y el
  spec debe decirlo.
- **Estado y errores de la corrida**: el operador **necesita** saber que su
  corrida fallo, y hoy el detalle util esta en `stderr` y en `error_message`,
  que son texto de Julia. ¿Que parte de eso es mostrable y como se traduce?
  Ligado a la pregunta de fallos del cascaron de la consola.
- **KPIs desconocidos**: ¿la superficie imprime toda clave del `summary.json`
  que no reconoce, o solo las que la configuracion declara? Lo segundo cierra
  la filtracion de `source_identifiers` por construccion.
- **Vocabulario**: `scenario_version.version_number` y `run.status` son
  conceptos internos que hoy se muestran con su nombre tecnico. ¿Se renombran,
  se derivan a un estado de negocio, o se ocultan?
- **Un contrato o dos**: ¿el portal cliente read-only y la consola de operador
  comparten el sobre, o cada perfil tiene el suyo?

La respuesta es una seccion del spec: el esquema del payload de cada
superficie, con su regla de recorte y su punto de aplicacion.

## Restriccion confirmada por el portal cliente

El portal adopta un informe ejecutivo lineal. Su payload debe permitir solo el
contexto publico de la publicacion, KPIs declarados, graficos y tablas
habilitados, etiquetas cliente y descargas aprobadas. Nunca entrega claves no
declaradas del `summary`, rutas del servidor, versiones internas, `stdout`,
`stderr` ni estados tecnicos crudos. La configuracion decide presentacion
dentro de esa allowlist; no amplia lo que puede cruzar la frontera.

## Restriccion confirmada por la regla fail-closed

La consola puede quedar bloqueada por un stale ajeno (topologia o parametros
que movio el ingeniero). Ese estado viaja al frontend **ya traducido**: un
estado de negocio y una frase accionable, mas a quien escalar. Nunca cruzan las
`reasons` crudas de `VariantStaleError`, ni `dependency_type`,
`dependency_id`, hashes ni nombres de tablas. El payload de la consola tampoco
expone marcador de staleness como campo tecnico: la superficie solo necesita
saber si puede ejecutar y, si no, por que en lenguaje de operador.

## Restriccion confirmada por el contrato de la tabla editable

El error de validacion de una edicion debe cruzar la frontera **direccionado por
celda** —indice de periodo y `signal_key`— y ya traducido a lenguaje de
operador. Hoy `validate_catalog_value_edits` responde
`edit 37: load_demand_mw at period 5305 must be nonnegative`: en ingles, por
numero de edicion dentro de la lista, y nombrando la clave canonica. Ninguna de
esas tres cosas sirve en la superficie, y la ultima ademas filtra vocabulario
interno.

El payload de guardado tampoco expone identificadores de copia operativa, set,
revision ni hash: la consola necesita saber a que celda apunta el error y si
puede ejecutar, nada mas.

## Restriccion confirmada por el modelo de datos

**Modelo de datos de la configuracion por proyecto** fija que nunca cruzan la
frontera: el `revision` de la configuracion, su `schema_version`, y los ids de
consola, de variante propia, de copia operativa y de set y revision de origen.
Del lease solo puede salir quien esta editando, nombrado como persona, nunca su
estado tecnico ni sus timestamps.

Ademas responde la pregunta de este ticket sobre si son dos filtros en serie:
si lo son, y el segundo **es** la configuracion. La allowlist de seguridad
decide que *puede* salir; el documento de configuracion decide que *se muestra*
dentro de eso, y nunca amplia el primero. Como ambos documentos declaran sus
propias etiquetas, el vocabulario del cliente y el del operador salen de ahi y
no de las ~40 cadenas fijas que el inventario encontro repartidas entre backend
y frontend.

## Resolucion

Decision tomada en sesion de grilling el 2026-08-21, con **corte MVP explicito**:
lo basico completo, sin funcionalidad de mas. Cada recorte asumido queda
nombrado abajo.

La pregunta de fondo tenia una respuesta ya implicita en cuatro tickets
cerrados; lo que faltaba era el mecanismo. Hoy la promesa del destino se
sostiene porque el React elige que pintar. Despues de este ticket se sostiene
porque el backend no manda otra cosa.

### Dos sobres y un bloque de resultados compartido

`portal_payload` y `console_payload` son documentos independientes de nivel
superior. No hay sobre generico con secciones nulas: obligaria a cada
superficie a ignorar campos ajenos, que es exactamente el modo de falla que se
esta cerrando.

Lo unico que ambas superficies muestran de verdad es el **bloque de
resultados** —el cascaron de la consola fija historial con apertura de
resultados y comparacion de dos corridas—, y es justo donde vive la fuga de
hoy. Ese bloque es **un solo constructor**, compartido. Duplicarlo duplicaria
la fuga: ya paso una vez, entre `client_publication_payload`
(`app/main.py:751`) y el preview del analista (`app/main.py:2520`), que son dos
copias del mismo pase armadas a mano.

### La regla: allowlist construida a mano

El payload se arma **enumerando lo que sale**, nunca filtrando lo que no debe
salir. Agregar una columna a `runs` o una clave al `summary.json` no la hace
cruzar. Es la propiedad central del contrato.

Los dos filtros en serie que anticipo el modelo de datos:

1. **Filtro de seguridad, fijo.** Funciones puras en un modulo unico
   (`app/surface_payloads.py`) que **nombran campo por campo**. Ninguna fila de
   la base se pasa entera a un sobre. El ingeniero no puede ensanchar este
   filtro.
2. **Filtro de presentacion.** El documento de configuracion decide que se
   muestra *dentro* de lo que el primero permite.

No se delega la garantia al `response_model` de FastAPI: un campo
`dict[str, Any]` pasa sin filtrar, y `results` necesariamente lo es. El
`response_model` puede existir como segunda correa, pero no es lo que sostiene
la frontera.

### Sobre del portal

```text
portal_payload
  project        { name }
  publication    { title, comment, published_at }
  period         { start, end }
  results_state  "available" | "unavailable"
  results        results_block | null
  downloads      [ { label, media_type, byte_size, download_url } ]
```

- `title` es `publications.public_title` y `comment` es `analyst_notes`, que
  pese al nombre es el comentario publico que fijo el cascaron del portal.
- **`period` se deriva de los timestamps del bloque de resultados**, no de
  `scenario_version.period_count`. Asi la version inmutable no aparece en el
  sobre ni siquiera como fuente.
- `scenario`, `scenario_version` y `run` **no tienen representacion**. Ni un
  campo. Es lo que hoy manda los seis bloques crudos.
- `results_state` reemplaza a `results_error`, que hoy cruza mensajes como
  `summary.json artifact is not registered`. El cliente no tiene nada que hacer
  con el nombre de un artefacto.

### Bloque de resultados compartido

```text
results_block
  kpis    [ { id, label, value, unit, decimals, sign, emphasis } ]
  charts  [ { id, label, x_labels, series: [ { label, unit, values } ] } ]
  tables  [ { id, label, columns: [ { id, label, unit } ],
              rows: [ { <column_id>: value } ], row_limit } ]
```

- **Los KPIs se declaran por path de hasta tres segmentos** en la
  configuracion: `objective_value_usd`, `hydro_totals.total_generation_mwh`,
  `hydro_kpis_by_asset.hydro_1.final_storage_hm3`. El payload emite `label` y
  `value`; **la clave canonica no viaja**. Eso cierra por construccion la fuga
  de `source_identifiers.system_case`, que es la ruta absoluta del caso en el
  disco del servidor y hoy se imprime porque `SummarySection`
  (`frontend/src/RunResults.tsx:157`) recorre `Object.entries(summary)` entero.
- **Un KPI declarado que falta en el `summary` se omite.** No rompe la pagina.
  El ingeniero lo nota al previsualizar, porque no aparece.
- **Toda clave del `summary` que la configuracion no declare, no sale.** Se
  acabo el imprimir lo desconocido.
- Las series de grafico llevan `label` de la configuracion, nunca `key`.
- Tres segmentos de path es el corte: cubre lo plano, los `*_totals` y un nivel
  por activo. No hay comodines ni "todos los activos". Coherente con el corte
  "solo escalares de nodo" del modelo de datos.

### Sobre de la consola

```text
console_payload
  console      { id, name, description, prepared_by, updated_at }
  period       { available_start, available_end, selected_start, selected_end }
  parameters   [ { id, label, unit, min, max, default, value } ]
  groups       [ { id, label, granularities: [...],
                   columns: [ { id, label, unit, nonnegative, editable } ] } ]
  run_gate     { can_run, reason, message, contact, editing_locked_by }
  history      [ { id, started_at, state, duration_seconds, triggered_by } ]
```

Los valores de una tabla no viajan dentro de este sobre: se piden por grupo y
tramo, que es como el operador navega las pestañas.

```text
group_values  { group_id, granularity,
                rows: [ { index, timestamp,
                          values: { <column_id>: number|null } } ] }
```

- **Ningun identificador interno cruza**: ni `case_id`, ni el id de la variante
  propia, ni el de la copia operativa, ni el set o la revision de origen, ni el
  `revision` ni el `schema_version` de la configuracion. `console.id` si cruza
  porque la ruta lo necesita, y es una clave subrogada de un objeto de
  configuracion, no del linaje.
- `editing_locked_by` nombra a **una persona**, nunca el estado tecnico del
  lease ni sus timestamps.
- `triggered_by` y `prepared_by` son nombres para mostrar, no correos ni ids.

### Identificadores opacos, no vocabulario interno

Parametros, grupos y columnas se nombran con **el `id` que la configuracion
declara**, no con su origen:

- un parametro expuesto viaja como `id`, nunca como `{asset_id, field}`;
- una columna viaja como `id`, nunca como `signal_key`.

El backend resuelve el id contra el documento de configuracion al recibir un
guardado o una ejecucion. Esto sale **mas simple**, no mas complejo: el
frontend direcciona con el mismo id que recibio, y no necesita conocer ni la
topologia del caso ni el registro canonico de señales.

Resuelve ademas la tension que este ticket tenia con el contrato de la tabla
editable, que pedia direccionar el error "por indice de periodo y `signal_key`"
mientras este mismo ticket objetaba que eso filtra vocabulario interno. El
error de validacion apunta a la celda por coordenadas de la tabla que el
operador ve:

```text
save_error  { message,
              cells: [ { group_id, column_id, row_index, message } ],
              total_cells, shown_cells }
```

Con tope de **100 celdas mostradas** mas el total. Un pegado de 8760 filas
invalidas no puede reventar el payload. El guardado sigue siendo todo-o-nada:
el tope es de presentacion, no de validacion.

### Estado y fallo de la corrida

`run.status` se traduce a un enum de negocio fijo del producto, no
configurable:

```text
en_espera | ejecutando | lista | fallida
```

**El operador no ve `stdout`, `stderr` ni `exit_code`. Nunca.** Un fallo viaja
asi:

```text
failure  { cause, message, reference }
```

y `cause` distingue dos mundos:

- **lo que el backend sabe antes de invocar al motor** —`rango_sin_cobertura`,
  `serie_incompleta`, `parametro_fuera_de_rango`— que es accionable, se traduce
  a lenguaje de operador y apunta al grupo o parametro que hay que corregir;
- **`ejecucion_fallida`**, el generico para todo lo que venga de Julia, con
  `reference` = el id de la corrida, para que el ingeniero lo encuentre en su
  propia superficie.

**No hay parser de `stderr`.** Adivinar la causa desde el texto del solver es
funcionalidad de mas y envejece con cada version del motor.

`run_gate.reason` cubre los cinco motivos que los tickets previos ya fijaron:

```text
null | dependencia_movida | campo_no_disponible
     | edicion_sin_guardar | guardado_en_curso | edicion_de_otro_usuario
```

Los dos primeros son los bloqueos fail-closed —variante stale por causa ajena y
puntero colgando— y viajan con `message` accionable y `contact`, que es a quien
escalar. Nunca cruzan las `reasons` crudas de `VariantStaleError`, ni
`dependency_type`, `dependency_id`, hashes ni nombres de tabla.

### Vocabulario e idioma

Las frases fijas del producto viajan **en español desde el backend**, junto al
enum. El enum gobierna el comportamiento de la interfaz; la frase es el texto.
Es lo que exigio la regla fail-closed al decir que el estado viaja "ya
traducido". Sin capa de i18n: la aplicacion ya es de interfaz en español y
agregar negociacion de idioma es funcionalidad de mas.

`version_number`, `schema_version`, `revision`, `case_name` y los `created_by`
internos no cruzan a ninguna de las dos superficies, en ninguna forma.

### Lo que nunca cruza, y el test que lo sostiene

La allowlist es el mecanismo. La denylist es el **test de frontera**: serializa
el sobre completo de cada superficie sobre un caso con datos y falla si aparece
cualquiera de estas claves.

```text
workspace_path      input_snapshot_path   output_dir          summary_path
stdout_log_path     stderr_log_path       stdout              stderr
exit_code           error_message         source_identifiers  system_case
case_name           schema_version        version_number      validation_payload
generation_metadata asset_counts          signal_key          asset_id
dependency_type     dependency_id         content_hash        revision
set_id              variant_id            case_id             scenario_id
scenario_version_id dashboard_template_id created_by          updated_by
all_series          plot_series
```

El test revisa **claves**, y ademas que ninguna cadena del sobre contenga la
raiz de artefactos del servidor. No revisa todos los valores: los ids de activo
aparecen como *valores* en la columna de activo de la tabla de despacho por
activo, igual que hoy.

`all_series` y `plot_series` estan en la lista por una razon que el ticket no
habia nombrado: `build_all_series_chart` y `build_plot_series_catalog`
(`app/results.py`) emiten **una serie por cada columna numerica** del CSV, con
el nombre crudo de la columna como etiqueta. Es el mismo imprimir todo lo
desconocido, en forma de grafico. Quedan como superficie exclusiva del analista.

### El preview del analista usa el mismo constructor

`/api/publications/{id}/preview` deja de armar su propio dict y pasa a llamar al
constructor del sobre del portal, con su propio armador de URL de descarga. Sin
eso el preview no es un preview: el ingeniero configuraria a ciegas y las dos
copias volverian a divergir. Es la unica parte de este ticket que **borra**
codigo en vez de agregarlo.

### El contrato no se negocia entre versiones

Frontend y backend se despliegan juntos —FastAPI sirve `frontend/dist`— asi que
no hay compatibilidad hacia atras que sostener ni `schema_version` del payload
que emitir. Los nombres `portal_payload` y `console_payload` viven en el codigo
y en este spec, no en el cable.

### Cortes MVP asumidos

Todos aditivos de revertir. Se listan para que nadie los confunda con
descuidos:

- **El operador no accede al detalle tecnico de un fallo.** El cascaron de la
  consola dijo que el detalle tecnico queda como accion secundaria; aqui esa
  accion secundaria es la causa traducida, no el `stderr`. Revertirlo es
  agregar un campo, pero antes hay que decidir que parte del texto del solver es
  mostrable, y eso no es MVP.
- **Un KPI declarado que falta se omite en silencio.** No hay aviso al ingeniero
  mas alla de verlo faltar en el preview.
- **Los ids de activo se muestran tal como el analista los nombro** en la tabla
  de despacho por activo. No hay relabeling por activo en la configuracion.
- **Sin i18n.** Frases fijas en español, en el codigo del backend.
- **Sin paginacion de resultados ni de historial.** El limite de filas de tabla
  que ya existe (`table_preview_limit`) es todo el control que hay.

### Fuera de alcance declarado

- **`403` frente a `404`.** Hoy `require_client_publication_access`
  (`app/main.py:543`) responde `403` cuando el permiso falta y `404` cuando el
  objeto no existe, lo que confirma existencia a un usuario autenticado sin
  acceso. Unificarlo en `404` es una linea, pero es contrato de autorizacion, no
  de payload; meterlo aqui ensancha el ticket sin cerrarlo mejor.

### Consecuencias para el resto del mapa

- **Modelo de datos de la configuracion por proyecto** queda con un hueco que
  este ticket destapo: `operator_console_config.v1` **no declara paneles de
  resultado**, pero el cascaron de la consola exige que la consola muestre
  resultados e historial. Se resuelve haciendo que declare sus paneles con la
  **misma gramatica** que el documento de portal —KPIs por path, graficos del
  catalogo, tablas con columnas etiquetadas—, que es justamente lo que paga
  tener un bloque de resultados compartido. Adicion chica y aditiva; queda
  anotada como adenda en ese ticket.
- **Extensibilidad del registro de señales canonicas** gana una restriccion y
  pierde un lugar del mapa de costos: como el payload nombra columnas por id de
  configuracion y no por `signal_key`, una señal nueva no toca el contrato de
  payload de ninguna de las dos superficies.
- **Navegacion y aterrizaje por perfil** hereda que el listado de consolas de un
  proyecto es un sobre mas, sujeto a la misma allowlist, y que las consolas en
  `draft` no aparecen en el.
- **Alcance de marca del portal cliente** hereda que todo elemento de marca
  tiene que entrar como campo declarado del sobre del portal; no hay hueco
  generico por donde pasen metadatos de proyecto.
- **Superficie del ingeniero para consolas bloqueadas** hereda su contraparte:
  es superficie de analista, **no** esta sujeta a esta allowlist, y es el unico
  lugar donde vive el detalle tecnico que el operador no ve. El `reference` del
  fallo generico es lo que conecta ambas.
