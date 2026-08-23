---
id: 10
title: "Especificacion consolidada de la capa de configuracion"
map: capa-de-configuracion
label: wayfinder:task
status: open
assignee:
blocked_by: [01, 02, 03, 04, 05, 06, 07, 08, 09, 11, 12, 13, 14]
---

## Question

Nada que decidir: escribir el documento que es el destino del mapa.

Consolidar todas las resoluciones en una especificacion lista para implementar,
en `docs/` junto al resto de la documentacion de arquitectura del repositorio,
siguiendo el estilo de `docs/series_tiempo/iter6/architecture_ts6_final.md`.

Debe contener:

- **Modelo de datos** de la configuracion, con esquema y politica de version.
- **Contratos de API**: endpoints de lectura y escritura de la configuracion,
  de la consola de operador (leer tabla, guardar edicion, correr, ver estado) y
  del portal cliente configurado, con el esquema de payload y la regla de
  recorte que fija **Contrato del payload de las superficies configuradas**.
- **Comportamiento de ambas superficies**: que ve cada perfil, en que orden,
  con que estados de carga y error.
- **Marca del portal cliente**: los dos unicos campos configurables
  —`display_name` y logo—, con el logo acotado a un slot **PNG/JPEG** de hasta
  **256 KB**, guardado en columnas de `portal_configurations` y servido por un
  endpoint propio bajo `/api/` con el control de acceso del portal, **nunca** bajo
  `/react/*`, que esta exento del gate de rol. Debe registrar la regla de fallback
  que **nunca** cae en la marca del producto —sin `display_name` muestra
  `project.name`, sin logo no muestra ninguno, y en particular no el brand mark
  `Z` del header del analista—, el titulo del documento por proyecto, el `ETag`
  por revision, y las dos **enmiendas declaradas** por **Alcance de marca del
  portal cliente**: que el documento JSON lleva solo `display_name` porque un
  binario no cabe en el, y que el sobre del portal reemplaza `project { name }`
  por `branding { display_name, logo_url }` con el fallback ya resuelto en
  backend, igual que `landing_path`. Debe dejar escrito que
  `project.description` deja de mostrarse en el portal, como **regresion
  consciente** respecto de hoy y no como omision.
- **Navegacion global y aterrizaje por perfil**: las tres raices que no comparten
  header, la ruta plana `/console/:consoleId`, la ruta separada de configuracion
  dentro del workspace de escenario, la regla unica de `landing_path` como campo
  del sobre de identidad, las tres guardas de raiz que reemplazan los 19
  `isClient` y la politica 403/404, segun **Navegacion y aterrizaje por perfil**.
  Debe registrar explicitamente que hoy la regla de aterrizaje esta **triplicada**
  en el codigo (`app/main.py:585`, `app/main.py:589`, `frontend/src/App.tsx:66`)
  y que el spec la unifica en una sola implementacion de backend. Debe fijar
  tambien que para un `external` la respuesta a lo que no le pertenece es **404**,
  incluido `runs/:runId` con el numero de referencia en la mano.
- **Matriz de permisos** actualizada, y como pasa por
  `require_authenticated_app_boundary`.
- **Semantica de la edicion de series**: donde aterriza, como interactua con
  staleness y cobertura, que se audita.
- **Superficie del ingeniero sobre las consolas de su proyecto**: la lista con
  sus estados, los dos motivos de bloqueo con su gesto de desbloqueo distinto,
  la advertencia sincrona al guardar un cambio de caso y el badge de copia vieja,
  segun **Superficie del ingeniero para consolas bloqueadas**.
- **Estrategia de validacion de la configuracion**: rechazo duro de esquema al
  guardar mas fail-closed al cargar la consola, sin linter semantico. Va como
  seccion propia porque es una decision de recorte, no una omision.
- **Nota de extensibilidad** de senales: la receta ordenada de siete pasos que
  fija **Extensibilidad del registro de senales canonicas**, marcando cual es
  declarativo y cual irreducible. Debe separar explicitamente el costo de
  **agregar una señal vectorial** del de **convertir un escalar en serie**, y
  declarar la dependencia del motor como v4 o ampliacion de v3 —nunca "v3", que
  ya existe—. Incluye el endpoint de lectura del registro canonico que reemplaza
  la copia a mano del frontend, y que entra en la matriz de permisos como
  cualquier superficie nueva.
- **Compatibilidad**: que pasa con `dashboard_templates`, publicaciones y
  configuraciones ya existentes.
- **Criterios de aceptacion** verificables, en el estilo de los acceptance
  suites por iteracion que ya usa el repositorio.
- **Fuera de alcance explicito**, heredado de la seccion correspondiente del
  mapa.

Al cerrar este ticket el mapa esta completo. El paso siguiente ya no es
wayfinding: es `/to-tickets` sobre el spec.
