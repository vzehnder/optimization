---
label: wayfinder:map
slug: capa-de-configuracion
title: "Capa de configuracion: consola de operador y portal cliente"
created: 2026-08-01
---

# Capa de configuracion: consola de operador y portal cliente

## Destination

Una **especificacion lista para implementar** de una capa de configuracion por
proyecto, editada por `analyst`/`admin`, que parametriza dos superficies de
forma fija:

1. **Consola de operador**: un usuario final entra, ajusta parametros expuestos
   y edita en tablas preconfiguradas (pegando columnas desde Excel) las series
   que el ingeniero habilito, ejecuta la corrida y ve resultados. Nunca ve
   draft, catalogo, variantes, bindings ni versiones inmutables.
2. **Portal cliente read-only**: lo que hoy hacen las `dashboard_templates`,
   pero configurable de verdad.

La forma de ambas superficies es **fija**. El ingeniero no mueve layout: decide
que se expone, con que etiqueta, con que rango valido, con que valor por
defecto y que paneles de resultado aparecen. Flexibilidad para quien configura,
estabilidad para quien usa.

El mapa cierra cuando existe ese spec (modelo de datos, contratos de API,
comportamiento de ambas superficies, criterios de aceptacion), listo para
convertirse en tickets de implementacion via `/to-tickets`.

## Notes

**Dominio**: aplicacion web privada de optimizacion de despacho one-bus
(FastAPI + React + motor Julia). Ver `docs/final/objetivo_final.md`,
`docs/tutorials/guia_analista.md` y el `README.md` (secciones TS-1 a TS-6).

**Tracker**: markdown local. Convenciones en `docs/wayfinder/README.md`.

**Este mapa planifica; no implementa.** Cada ticket resuelve una decision. El
entregable es un spec, no codigo.

**Skills a consultar en cada sesion**: `/grill-me` para los tickets de
grilling; el prototipado de UI se hace con codigo desechable en el scratchpad,
no en `frontend/src`.

### Decisiones de encuadre (sesion de charting, 2026-08-01)

Fijan el destino; no son tickets cerrados.

- **Usuario final = dos perfiles**: cliente read-only *y* operador que ejecuta.
- **La fachada ES la simplificacion**: la cadena interna (Draft -> Catalogo ->
  Variante -> Rango -> Version inmutable -> Corrida) no se toca en este mapa.
  Sus garantias (staleness fail-closed, snapshots inmutables, lineage) se
  respetan; el trabajo consiste en esconderlas, no en debilitarlas.
- **Mecanismo = cascaron fijo + parametrizacion**, no constructor de pantallas
  ni documento declarativo suelto.
- **Ambito = por proyecto**, editada por `analyst`/`admin`. Sin rol nuevo para
  configurar (el rol de *quien usa* la consola de operador si esta abierto:
  ver el ticket correspondiente).
- **Extensibilidad de senales si, senal nueva no**: se disena como se agregan
  senales canonicas nuevas al registro y a la tabla editable; no se implementa
  `power_max_mw` variable en el tiempo ni se toca el contrato Julia.

### Hallazgos de codigo verificados en el charting

- `dashboard_templates` ya es un cascaron fijo pobre: 9 booleanos
  (`show_summary`, `show_price_chart`, ... ) mas `table_preview_limit`, por
  proyecto. Ver `app/main.py:141-152` y `app/persistence.py:66-74`. El portal
  cliente no parte de cero.
- La edicion manual con revision ya existe:
  `AnalystStore.edit_time_series_set_values(edits=[CatalogValueEdit])` en
  `app/persistence.py:4399`. Crea una revision nueva sin sobreescribir. El
  pegado desde Excel es UI + batching sobre una primitiva existente.
- El registro canonico de senales tiene exactamente 8 claves
  (`app/time_series_catalog.py`): `price_usd_per_mwh`,
  `import_price_usd_per_mwh`, `export_price_usd_per_mwh`, `load_demand_mw`,
  `renewable_available_power_mw`, `hydro_inflow_m3s`, `natural_inflow_m3s`,
  `minimum_flow_m3s`. **No existe** limite de potencia por unidad como serie.
- El gate de permisos compartido es `require_authenticated_app_boundary` en
  `app/main.py`; cualquier superficie nueva debe pasar por ahi por construccion
  (contrato heredado de TS-5).

## Decisiones tomadas

<!-- una linea por ticket cerrado: gist + link -->

- [Inventario de la superficie configurable existente](capa-de-configuracion/01-inventario-superficie-configurable.md)
  — la superficie que ve un no-analista la gobiernan **tres** mecanismos, no
  uno: los 9 booleanos (unico que el ingeniero controla), el sobre de la
  publicacion (que no filtra nada) y el catalogo de graficos y etiquetas (~40
  cadenas fijas repartidas entre backend y frontend). Cuatro capas a
  parametrizar; solo una existe hoy.

- [Forma del cascaron de la consola de operador](capa-de-configuracion/02-cascaron-consola-operador.md)
  — una mesa de trabajo unica: identidad y parametros primero, series SQL
  agrupadas con Tabla/Grafico y version nombrada por señal, guardado auditable,
  ejecucion lateral persistente e historial comparable.

- [Forma del cascaron del portal cliente configurado](capa-de-configuracion/03-cascaron-portal-cliente.md)
  — un informe ejecutivo read-only y lineal por publicacion, con orden fijo,
  contenido y vocabulario configurables por proyecto, y descargas aprobadas.

- [Rol y permisos del operador](capa-de-configuracion/04-rol-y-permisos-del-operador.md)
  — usuarios `external` reciben capacidades independientes `portal_view` y
  `operate` por proyecto; operar queda limitado a la configuracion activa,
  con asignacion administrativa y auditoria individual completa.

- [Donde aterriza la edicion de series del operador](capa-de-configuracion/05-donde-aterriza-la-edicion.md)
  — la primera edicion crea una copia operativa del set, aislada del catalogo,
  compartida por la consola y persistente entre versiones de configuracion;
  usa lease exclusivo, revisiones optimistas e historial auditable sin
  reescribir datos canonicos.

- [Edicion del operador frente a la regla fail-closed](capa-de-configuracion/06-edicion-frente-a-fail-closed.md)
  — el guardado del operador **es** la atestacion: al aceptarlo, el backend
  refresca en la misma transaccion solo el hash de la copia operativa, asi que
  el cambio propio nunca deja stale la variante y el ajeno si. La consola no
  revalida nunca; ante un stale externo bloquea, traduce y escala al ingeniero.
  La copia se materializa como set plano no derivado, sin lo cual la primera
  edicion se autobloquearia sin salida.

- [Contrato de la tabla editable y del pegado desde Excel](capa-de-configuracion/07-contrato-tabla-editable-y-pegado.md)
  — una tabla por grupo del analista, con guardado transaccional unico entre
  todas las copias operativas que el grupo toca. Se rechaza todo numero de
  lectura ambigua (`1.234`, `12,345`), lo que elimina la necesidad de un locale
  configurable. Validacion todo-o-nada, con el error direccionado por celda en
  vez de por posicion. El tramo acota la edicion y el desborde del pegado
  trunca con aviso; la revision previa queda siempre disponible pero nunca
  obligatoria.

- [Modelo de datos de la configuracion por proyecto](capa-de-configuracion/08-modelo-de-datos-de-la-configuracion.md)
  — dos documentos JSON con `schema_version`: configuracion de portal una por
  proyecto, que reemplaza a `dashboard_templates`, y consola de operador N por
  proyecto colgando del caso, con identidad estable dueña de su **variante
  propia**, sus copias operativas y un **overlay de overrides** de parametros
  que nunca toca el draft. Sin historial: solo contador de revision. El ticket
  destapo que los parametros del operador no estaban resueltos y que compartir
  la variante del analista habria hecho inimplementable al ticket 05.

- [Extensibilidad del registro de senales canonicas](capa-de-configuracion/09-extensibilidad-registro-de-senales.md)
  — el caso de prueba no es caro sino **inexpresable**: la derivacion one-bus
  admite una sola señal por tipo de nodo, y la lista "declarativa" del camino
  hidraulico es forma de transporte con allowlist de una clave detras. Se
  especifica volverla lista, exponer el registro por API para matar la copia a
  mano del frontend, y separar el costo de **agregar una señal vectorial** del de
  **convertir un escalar en serie**, que es cambio de cota JuMP y no de parseo.
  El ticket destapo que **el contrato Julia v3 ya existe** —es el esquema
  hidraulico actual, no una version futura—, asi que la dependencia declarada es
  v4 o una ampliacion de v3. Recorte MVP: no se unifican los dos mecanismos de
  derivacion ni se hace declarativa la ingesta.

- [Contrato del payload de las superficies configuradas](capa-de-configuracion/11-contrato-del-payload.md)
  — dos sobres de nivel superior con **un** bloque de resultados compartido,
  armados por allowlist escrita a mano: ninguna fila de la base cruza entera y
  una columna nueva no se filtra sola. Los KPIs se declaran por path y salen
  solo con etiqueta y valor, lo que cierra la fuga de la ruta absoluta del caso;
  parametros y columnas viajan con id de configuracion, nunca con
  `{asset_id, field}` ni `signal_key`. El operador no ve `stdout`/`stderr`:
  recibe causa traducida cuando el backend la sabe antes de invocar al motor, y
  un generico con id de referencia cuando viene de Julia. El preview del
  analista pasa a usar el mismo constructor. El ticket destapo que el documento
  de la consola no declara paneles de resultado.

- [Superficie del ingeniero para consolas bloqueadas](capa-de-configuracion/14-superficie-ingeniero-consolas-bloqueadas.md)
  — no se crea superficie: el bloqueo es una **columna de estado** en la lista de
  consolas que ya habia que construir. El ingeniero se entera por advertencia
  sincrona al guardar un cambio de caso y por un flag `esperando_desde` en la
  fila; ningun inbox. Los dos motivos de bloqueo **no se desbloquean igual**:
  `dependencia_movida` es un boton sobre el endpoint de validar que ya existe,
  `campo_no_disponible` se arregla editando la configuracion. El ticket destapo
  que "quien movio la dependencia" no es contestable —`validation_dependencies`
  no tiene actor—, lo que forzo que el `contact` apunte a quien preparo la
  configuracion. La copia vieja respecto de su receta de origen se avisa con
  badge y no bloquea. Sin caducidad y sin linter semantico.

- [Navegacion y aterrizaje por perfil](capa-de-configuracion/12-navegacion-y-aterrizaje-por-perfil.md)
  — tres raices hermanas que no comparten header (analista, `/console`, portal),
  con la consola en ruta plana `/console/:consoleId` y una ruta distinta para
  configurarla dentro del workspace de escenario: configurar no es operar. El
  aterrizaje deja de ser logica de cliente y pasa a ser el campo `landing_path`
  del sobre de identidad, con `operate` ganandole a `portal_view` y el salto
  directo a la consola unica viviendo solo ahi. Los 19 `isClient` se reemplazan
  por **tres** guardas de raiz, y para un `external` lo que no le pertenece
  devuelve 404, no 403. El ticket destapo que la regla de aterrizaje esta hoy
  **triplicada** en el codigo y que el listado que la navegacion necesita es
  cruzado por proyecto, no por proyecto.

- [Alcance de marca del portal cliente](capa-de-configuracion/13-marca-del-portal-cliente.md)
  — marca por proyecto de **dos campos**, nombre visible y logo, sin colores. El
  logo es el **primer binario del sistema**, y por eso queda acotado con llave:
  un slot, PNG/JPEG —excluir SVG mata la rama de XSS—, tope de 256 KB, bytes en
  columnas de `portal_configurations` y endpoint propio bajo `/api/`, porque
  `/react/*` esta exento del gate de rol. El fallback nunca cae en la marca del
  producto. Enmienda declarada al sobre: `project { name }` pasa a
  `branding { display_name, logo_url }` con el fallback ya resuelto en backend,
  como `landing_path`. El ticket destapo que la marca del producto **no es un
  activo sino el header del analista** (`Z` + "BESS Workspace"), asi que "usar la
  del producto" nunca fue la opcion conservadora, y que `project.description` se
  cae del portal como regresion consciente. Sin versionado y con edicion en vivo.

- [Especificacion consolidada de la capa de configuracion](capa-de-configuracion/10-spec-consolidado.md)
  — el spec aceptado consolida modelo, documentos JSON, APIs, payloads,
  permisos, edicion, fail-closed, navegacion, marca, migracion, extensibilidad y
  criterios de aceptacion; el mapa queda listo para `/to-tickets`.

## Not yet specified

Ninguno. La ruta al destino esta especificada y no queda niebla dentro del
alcance.

## Out of scope

Trabajo conscientemente fuera del destino de este mapa. No graduan.

- **Exponer o editar el diagrama hidraulico desde la consola de operador**.
  El destino de este mapa es la fachada del editor estructurado one-bus; la
  topologia hidraulica exige otro cascaron y un esfuerzo separado.
- **Documentacion/onboarding del ingeniero configurador**. Es un entregable de
  producto posterior a implementar y estabilizar el spec, no una decision que
  impida convertirlo en tickets.
- **Simplificar la cadena interna** (fusionar Draft con Caso, revisar la
  cardinalidad Escenario -> OptimizationCase 1-a-1, unificar editor
  estructurado con diagrama hidraulico). Decidido en el charting: fachada
  ahora, deuda interna despues, como esfuerzo separado con su propio mapa.
- **Implementar limites de potencia por unidad variables en el tiempo**: senal
  canonica nueva + version de contrato Julia nueva. Aqui solo se disena la
  extensibilidad que lo haria barato despues. Corregido por
  [Extensibilidad del registro de senales canonicas](capa-de-configuracion/09-extensibilidad-registro-de-senales.md):
  **v3 ya existe** —es el esquema hidraulico actual—, asi que la version futura
  es v4 o una ampliacion de v3; y el trabajo no es agregar una clave sino mover
  un campo escalar de struct de activo a matriz por periodo, cambiando la cota de
  la variable JuMP.
- **Unificar los dos mecanismos de derivacion de senales requeridas** (one-bus
  hardcodeado por tipo de nodo, hidraulico por lista declarativa) en uno solo.
  Recorte MVP de
  [Extensibilidad del registro de senales canonicas](capa-de-configuracion/09-extensibilidad-registro-de-senales.md):
  obliga a tocar dos esquemas Julia con validadores y runners separados, que es
  refactor de la cadena interna. Ambos quedan produciendo la misma forma de
  salida; fundirlos es deuda nombrada del esfuerzo separado.
- **Que el operador suba sus propios archivos CSV/XLSX**. Asuncion tomada del
  charting: el mecanismo elegido fue edicion en tabla con pegado, no upload. Si
  resulta que el operador si necesita subir archivos, esto redibuja el destino.
- **Edicion de modelos por el cliente read-only**: sigue fuera de alcance como
  en `docs/final/objetivo_final.md`.
- **Colores, tipografia y tema configurables por proyecto**, y **favicon por
  proyecto**. Recorte MVP de
  [Alcance de marca del portal cliente](capa-de-configuracion/13-marca-del-portal-cliente.md):
  una paleta no es un campo sino una superficie —toca cada color de grafico, de
  estado y todo el contraste— y como ya se decidio que no hay linter semantico,
  nada atajaria una paleta ilegible antes de que la vea el cliente. La marca del
  portal se resuelve con nombre visible y logo.
- **Dominio propio y white-label del portal**. Decidido en
  [Alcance de marca del portal cliente](capa-de-configuracion/13-marca-del-portal-cliente.md):
  el portal es "el informe de este proyecto", no "un producto del cliente".
