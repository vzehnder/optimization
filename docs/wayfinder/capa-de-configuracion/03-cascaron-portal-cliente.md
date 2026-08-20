---
id: 03
title: "Forma del cascaron del portal cliente configurado"
map: capa-de-configuracion
label: wayfinder:prototype
status: closed
assignee: vzehnder
blocked_by: []
---

## Question

¿Que gana el portal cliente sobre los 9 booleanos de hoy, y cual es su forma
fija?

Hoy una `dashboard_template` enciende o apaga: resumen, grafico de precios,
grafico de red, renovables, BESS, hidro, profit, tabla de despacho de sistema,
tabla de despacho por activo; mas un limite de filas. Eso ya es "cascaron fijo
+ parametrizacion", solo que pobre. La pregunta es que le falta para ser
suficiente, sin convertirse en un constructor de pantallas.

Candidatos a resolver con el prototipo:

- **Etiquetas**: ¿el ingeniero renombra secciones y series al vocabulario del
  cliente ("Ingresos por venta" en vez de `export_revenue_usd`)? ¿Hasta que
  nivel de granularidad: seccion, grafico, serie, columna?
- **Orden y enfasis**: ¿puede el ingeniero decidir que va arriba, o el orden
  tambien es fijo? El destino dice forma fija; conviene decidir explicitamente
  si el orden es parte de la forma o parte de la parametrizacion.
- **KPIs**: ¿el ingeniero elige que KPIs del `summary.json` se muestran y como
  se formatean (unidad, decimales, signo)?
- **Alcance por cliente**: ¿la configuracion es una por proyecto para todos los
  clientes asignados, o distinta por cliente? Esto tiene consecuencias directas
  sobre el modelo de datos.
- **Descargas**: hoy la allowlist de artefactos vive en la publicacion. ¿Se
  mueve a la configuracion, se queda, o se hereda con override?
- **Relacion con la publicacion**: una publicacion ya elige run + plantilla +
  titulo + notas. ¿Que parte de esa decision pasa a la configuracion y que
  parte sigue siendo por publicacion?

Enlazar el prototipo desde este ticket como activo.

## Activo de prototipo

- [Tres variantes del portal cliente configurado](../prototypes/portal-cliente/README.md)
  — `A` informe ejecutivo, `B` tablero explorable y `C` dossier tecnico;
  intercambiables con `?variant=` y construidas sobre la misma publicacion.

El prototipo es deliberadamente read-only y usa datos simulados. Se mantuvo
abierto hasta recibir la eleccion humana registrada en la resolucion.

## Resolucion

El usuario eligio la variante **A — Informe ejecutivo** el 2026-08-12.

La forma fija del portal cliente sera una lectura lineal de una publicacion:

1. identidad del proyecto y contexto de la publicacion;
2. titulo, periodo, comentario y fecha de actualizacion;
3. resumen de KPIs;
4. bloques narrativos de resultados con graficos;
5. tablas de detalle;
6. descargas aprobadas para esa publicacion.

El cliente puede leer, desplazarse y descargar; no cambia el orden, no arma un
dashboard y no edita datos. La configuracion es una por proyecto y se comparte
entre todos los usuarios cliente asignados a ese proyecto.

El ingeniero configura, dentro de los lugares fijos del informe:

- que KPIs, graficos, tablas y secciones aparecen;
- las etiquetas visibles de seccion, grafico, serie, KPI y columna;
- unidad, decimales, signo y enfasis de los KPIs;
- el vocabulario cliente que reemplaza claves y metadatos internos.

El orden macro no es configurable. La publicacion conserva la seleccion de la
corrida, titulo publico, notas, fecha y allowlist de artefactos descargables;
la configuracion gobierna la forma y el vocabulario reutilizables. El portal
solo muestra el subconjunto aprobado en la publicacion y nunca expone claves,
rutas, versiones internas o estados tecnicos crudos.

Las variantes **Tablero explorable** y **Dossier tecnico** quedan descartadas
como cascaron principal. Sus tabs por tema, indice documental y exportacion
integral no forman parte de esta primera especificacion.
