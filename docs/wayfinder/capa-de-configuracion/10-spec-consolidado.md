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
- **Nota de extensibilidad** de senales: que se toca para agregar una nueva.
- **Compatibilidad**: que pasa con `dashboard_templates`, publicaciones y
  configuraciones ya existentes.
- **Criterios de aceptacion** verificables, en el estilo de los acceptance
  suites por iteracion que ya usa el repositorio.
- **Fuera de alcance explicito**, heredado de la seccion correspondiente del
  mapa.

Al cerrar este ticket el mapa esta completo. El paso siguiente ya no es
wayfinding: es `/to-tickets` sobre el spec.
