---
id: 03
title: "Forma del cascaron del portal cliente configurado"
map: capa-de-configuracion
label: wayfinder:prototype
status: open
assignee:
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
