---
id: 06
title: "Edicion del operador frente a la regla fail-closed"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
blocked_by: [05]
---

## Question

El operador edita una serie y aprieta correr. La regla fail-closed dice que esa
edicion dejo la variante desactualizada y que no se puede correr hasta
revalidar. ¿Como se resuelve eso sin romper ninguna de las dos cosas?

Este es el choque central del mapa. La cadena interna no se toca (decision de
encuadre), asi que las garantias siguen vigentes: una serie vinculada con
`content_hash` nuevo marca la variante como stale, y
`materialize_system_case_for_variant` falla cerrado hasta que
`POST .../variants/{id}/validate` vuelve a pasar. Para un analista eso es una
proteccion. Para un operador que acaba de pegar una columna y espera un
resultado, es una pared sin sentido.

Lo que hay que decidir:

- **¿La consola revalida automaticamente despues de editar?** Si lo hace,
  ¿queda la proteccion como algo real o se vuelve un tramite invisible que
  siempre pasa? La proteccion existe para que nadie corra con datos que no
  reviso; si el operador acaba de escribirlos a mano, ¿los reviso?
- **¿Editar y correr son una sola operacion atomica** desde la perspectiva del
  operador, con revalidacion incluida en el medio, o son dos pasos con un
  estado intermedio visible?
- **Cobertura del rango**: pegar una columna mas corta o mas larga que el
  horizonte cambia la cobertura. TS-3 exige cobertura exacta sin huecos ni
  resampling implicito. ¿El pegado puede cambiar el largo del horizonte, o solo
  reemplaza valores de periodos existentes?
- **Fallos que el operador no puede arreglar**: si la revalidacion falla por
  algo ajeno a su edicion (la topologia del caso cambio, un set derivado quedo
  stale), ¿que se le muestra y a quien se escala?
- **Sets derivados**: si el operador edita un set que es origen de un derivado,
  el derivado queda stale y hay que regenerarlo. ¿Lo hace la consola sola, o el
  operador queda bloqueado esperando al ingeniero?
- **Efecto sobre terceros**: si la edicion cae en el set compartido, otras
  variantes del proyecto quedan stale sin que sus dueños lo pidieron. ¿Se les
  avisa?

**Insumo de** [Inventario de la superficie configurable existente](01-inventario-superficie-configurable.md):
la pregunta de cobertura de mas arriba ya tiene media respuesta en el codigo.
La edicion manual **solo reemplaza valores existentes**: rechaza todo periodo y
toda senal que no esten ya en el set. Extender el horizonte no es una edicion,
es un import. Ver la seccion C de ese ticket.

La respuesta debe preservar la propiedad que hace confiable a la herramienta:
toda corrida sigue apuntando al hash exacto que consumio.
