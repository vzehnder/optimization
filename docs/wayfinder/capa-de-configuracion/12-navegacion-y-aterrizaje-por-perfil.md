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
