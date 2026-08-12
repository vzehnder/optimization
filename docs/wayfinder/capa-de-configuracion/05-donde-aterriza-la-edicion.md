---
id: 05
title: "Donde aterriza la edicion de series del operador"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
blocked_by: []
---

## Question

Cuando el operador pega una columna nueva de caudales, ¿sobre que objeto cae
esa escritura?

El encuadre inicial fue "que quede guardado en la version de la ts que fue
editada", lo que apunta a una revision nueva del mismo `time_series_set`. Eso
es exactamente lo que hace `edit_time_series_set_values`
(`app/persistence.py:4399`) y encaja con el versionado de TS-2: revision nueva,
`content_hash` nuevo, historial inmutable.

Pero eso significa que un operador muta un dato **compartido por todo el
proyecto**: los sets del catalogo son del proyecto, y otras variantes y otros
escenarios pueden estar vinculados al mismo set. El radio de impacto de un
pegado accidental es todo el proyecto, no la corrida del operador.

Opciones a contrastar:

- **Revision sobre el set compartido** (lo mas directo): coherente con TS-2,
  cero conceptos nuevos, historial completo, pero un operador puede ensuciar
  datos de los que no es dueño. ¿Se acepta y se mitiga con auditoria y
  reversion, o no se acepta?
- **Copia privada al editar** (copy-on-write): el primer pegado deriva un set
  propio del operador o de la configuracion, y la variante se rebinda a el. No
  contamina a nadie, pero multiplica sets y hay que decidir su nombre, su
  ciclo de vida y quien los limpia.
- **Set designado como "editable por operador"**: el ingeniero marca en la
  configuracion que sets son escribibles desde la consola. Los demas son de
  solo lectura para el operador. Acota el daño sin inventar copias.

Preguntas que cualquier opcion debe responder:

- ¿Puede el operador deshacer? ¿Volver a la revision anterior es una operacion
  suya o de admin?
- ¿Que `change_summary` se registra, y lo escribe el operador o el sistema?
- ¿Que ve el operador de la historia de revisiones? Probablemente no la tabla
  cruda de TS-2.
- ¿Que pasa si dos operadores editan el mismo set a la vez?

Este ticket bloquea **Edicion del operador frente a la regla fail-closed**:
si la edicion cae en una copia privada, la staleness casi no existe; si cae en
el set compartido, la staleness es el problema central.

**Restriccion confirmada por el cascaron**: los datos se leen desde la base de
datos SQL y toda edicion aceptada debe persistirse alli como una revision
auditable. Este ticket no decide si hay persistencia; decide **sobre que set**
se crea esa revision cuando el operador ha elegido una version nombrada de la
serie.
