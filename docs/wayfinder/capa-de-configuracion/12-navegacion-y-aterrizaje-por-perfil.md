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
