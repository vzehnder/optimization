---
id: 12
title: "Navegacion y aterrizaje por perfil"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
blocked_by: [02, 03, 04]
---

## Question

¿Como conviven la aplicacion de analista, la consola de operador y el portal
cliente dentro de la navegacion global, y a que ruta aterriza cada perfil al
iniciar sesion?

Los dos cascarones ya fijan sus superficies. Esta decision debe precisar:

- si cada perfil tiene una ruta raiz y navegacion propias;
- si `admin`/`analyst` pueden entrar a las tres superficies y como cambian entre
  ellas sin confundir la vista operativa con la configuracion;
- que ocurre con usuarios que tienen mas de un perfil utilizable;
- como se reemplazan las comprobaciones React repetidas de `isClient` por una
  politica de rutas coherente con **Rol y permisos del operador**;
- que breadcrumbs y selector de proyecto conserva cada superficie.

## Restriccion confirmada por el modelo de datos

Las consolas son **N por proyecto**, colgando del caso; el portal es **uno por
proyecto**. La navegacion no puede tratarlos igual:

- un usuario `external` con `operate` en un proyecto con varias consolas
  necesita elegir cual abrir, mientras que con `portal_view` no hay nada que
  elegir. Si tiene exactamente una consola, el aterrizaje deberia saltarse la
  eleccion en vez de mostrar una lista de un elemento;
- las consolas en estado `draft` no existen para un usuario `external`: no
  aparecen en su navegacion y no son direccionables por URL;
- `admin` y `analyst` entran a las consolas con su identidad real para probarlas
  —lo fijo **Rol y permisos del operador**—, asi que la misma ruta sirve a dos
  perfiles con navegacion de origen distinta.

## Restriccion confirmada por el contrato del payload

**Contrato del payload de las superficies configuradas** fija que la navegacion
tambien es superficie configurada, no una excepcion:

- **el listado de consolas de un proyecto es un sobre mas**, sujeto a la misma
  allowlist escrita a mano. Por consola sale nombre, descripcion, quien la
  preparo y cuando se actualizo; no salen `case_id`, la variante propia, la
  copia operativa ni el `revision` de la configuracion;
- las consolas en `draft` **no existen en ese sobre**. La navegacion no las
  omite en el frontend: el backend no las incluye;
- `console.id` si cruza, porque la ruta lo necesita. Es una clave subrogada de
  un objeto de configuracion, no del linaje, y es el unico identificador
  direccionable que este mapa deja del lado del operador;
- el aterrizaje que se decida aqui no puede apoyarse en campos que el sobre no
  lleva. Si el salto directo cuando hay exactamente una consola necesita algun
  dato mas, hay que declararlo como campo del sobre, no leerlo de otra ruta.

## Restriccion confirmada por la superficie del ingeniero

**Superficie del ingeniero para consolas bloqueadas** agrega una superficie mas
al inventario que este ticket tiene que rutear, y decide de antemano que no es
una raiz:

- **la lista de consolas del ingeniero vive dentro del workspace de escenario**,
  junto a las variantes, porque ahi ya viven el caso y la variante de la que la
  consola clona la suya. No es una ruta de nivel superior y no compite con las
  tres superficies que este ticket ordena. Si la navegacion que se decida aqui
  la mueve a nivel de proyecto, hay que decirlo explicitamente y asumir que
  agregar consolas pasa a ser una agregacion sobre escenarios;
- **son dos vistas distintas del mismo objeto.** El ingeniero abre una consola
  desde su lista para configurarla o desbloquearla; `admin`/`analyst` tambien
  entran a la consola **con su identidad real para probarla**, que es lo que
  fijo **Rol y permisos del operador**. La navegacion tiene que distinguir esos
  dos destinos sin confundirlos: configurar no es operar;
- **la ruta de detalle de corrida `runs/:runId` queda como destino compartido.**
  El `reference` que el operador recibe cuando una corrida falla apunta ahi, y
  es superficie exclusiva de analista. Un `external` no puede alcanzarla por
  URL, aunque tenga el numero;
- el flag `esperando_desde` y el estado de bloqueo son **columnas de la lista**,
  no un destino navegable propio. No hay bandeja de avisos que rutear.
