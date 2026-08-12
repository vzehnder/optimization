# Wayfinder: tracker markdown local

Este repositorio no tiene un issue tracker configurado, asi que los mapas de
wayfinder viven aqui como markdown.

## Estructura

```text
docs/wayfinder/
  README.md                      <- este archivo (convenciones)
  <slug-del-mapa>.md             <- el mapa (label: wayfinder:map)
  <slug-del-mapa>/               <- tickets hijos de ese mapa
    NN-<slug-del-ticket>.md
```

## Operaciones de wayfinding

Cada ticket es un archivo markdown con frontmatter. La identidad del ticket es
su `id`; en toda narracion se le llama por su **titulo**, nunca por su id.

```markdown
---
id: NN
title: <titulo legible del ticket>
map: <slug-del-mapa>
label: wayfinder:research | wayfinder:prototype | wayfinder:grilling | wayfinder:task
status: open | closed
assignee: <persona que reclamo el ticket, o vacio>
blocked_by: [NN, NN]
---

## Question

<la decision o investigacion que este ticket resuelve>
```

- **Reclamar**: escribir `assignee` antes de empezar cualquier trabajo. Un
  ticket `open` con `assignee` vacio esta libre.
- **Bloqueo**: `blocked_by` lista los ids que deben estar `closed` primero.
  Markdown no tiene bloqueo nativo; esta lista es la convencion.
- **Frontera**: tickets con `status: open`, `assignee` vacio y todos sus
  `blocked_by` cerrados. Se obtiene listando el directorio del mapa.
- **Resolver**: agregar una seccion `## Resolucion` al final del ticket,
  cambiar `status: closed`, y agregar una linea en `## Decisiones tomadas`
  del mapa apuntando al ticket.
- Los activos producidos (prototipos, borradores) se enlazan desde el ticket,
  no se pegan dentro.

## Consulta rapida de la frontera

```powershell
Select-String -Path docs/wayfinder/*/*.md -Pattern '^(id|title|status|assignee|blocked_by):'
```
