---
id: 11
title: "Contrato del payload de las superficies configuradas"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
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
