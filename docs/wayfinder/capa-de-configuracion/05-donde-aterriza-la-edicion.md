---
id: 05
title: "Donde aterriza la edicion de series del operador"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
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

## Resolucion

### Objeto de escritura y aislamiento

- El operador nunca crea una revision sobre el set canonico compartido. En la
  primera edicion aceptada, el backend crea de forma atomica una **copia
  operativa** del set seleccionado y redirige exclusivamente el binding de la
  consola hacia ella.
- La copia pertenece a la identidad estable de la consola, no a un usuario ni
  a una version concreta de su configuracion. Todos los usuarios con
  capacidad `operate` sobre esa consola comparten la misma copia y el mismo
  historial operativo.
- Se copia el set completo. Si varias senales expuestas provienen del mismo
  set, comparten una unica copia operativa; versiones nombradas distintas
  originan copias distintas.
- Cambios de presentacion o de configuracion conservan la copia. Elegir otra
  version base o reiniciar los datos de forma explicita crea una copia nueva y
  archiva la anterior. Las copias no se eliminan automaticamente.
- El operador conserva el nombre funcional de la version elegida. La identidad
  interna de la copia es generada y no editable; `analyst` y `admin` ven que es
  una copia operativa, junto con su set y revision canonicos de origen, consola,
  fecha y actor de creacion.

`operate` sigue sin conceder acceso al catalogo: los endpoints de la consola
resuelven internamente el binding y la copia permitidos por la configuracion
activa.

### Revisiones, auditoria e historial visible

- Cada guardado aceptado crea una revision nueva de la copia operativa; nunca
  reescribe el historial.
- El sistema genera un resumen estructurado obligatorio con actor estable y
  snapshot legible, origen `operator_console`, consola, version de
  configuracion, revision base, senal, rango temporal, cantidad de celdas y
  valores anteriores y nuevos. El operador puede agregar una nota breve
  opcional.
- Antes de confirmar un pegado grande, la consola presenta el resumen y el
  diff. El detalle completo queda en la metadata de la revision, no comprimido
  dentro de `change_summary`.
- El operador ve fecha, autor, senal, rango, cantidad de celdas, nota, revision
  vigente y comparacion antes/despues. No ve ids, hashes, fuentes fisicas,
  bindings ni metadata de TS-2. `analyst` y `admin` conservan el historial
  tecnico completo.

### Deshacer y restaurar

- Un operador solo puede deshacer su ultimo guardado y solo mientras esa
  revision siga siendo la vigente. Deshacer crea otra revision; no borra la
  anterior.
- Si otra persona guardo despues, la consola ya no ofrece ese deshacer.
- `analyst` y `admin` pueden restaurar cualquier revision anterior, tambien
  como una revision nueva.
- Toda restauracion registra actor, revision de origen y motivo.

### Concurrencia

- Entrar en modo edicion adquiere en el servidor un **lease exclusivo por
  copia operativa**. Los demas usuarios pueden verla en modo solo lectura y
  ven quien mantiene el lease.
- El lease se renueva por heartbeat, expira al abandonar la sesion y puede ser
  liberado forzosamente por `admin`. Solo su titular puede guardar o deshacer.
- El lease mejora la coordinacion, pero no es la garantia de integridad: cada
  guardado, deshacer o restauracion envia la revision base esperada. El backend
  rechaza sin escribir si ya no es la vigente; no aplica `last-write-wins` ni
  mezcla cambios automaticamente.

### Consecuencias para el resto del mapa

- Una edicion operativa ya no cambia sets compartidos ni deja stale variantes
  ajenas. Solo avanza el hash de la copia y puede dejar stale el binding de la
  propia consola.
- **Edicion del operador frente a la regla fail-closed** debe decidir como se
  revalida esa variante operativa antes de correr.
- **Contrato de la tabla editable y del pegado desde Excel** debe incorporar
  el lease, la revision base, el diff previo, el rechazo atomico de conflictos
  y el historial simplificado.
- **Modelo de datos de la configuracion por proyecto** debe representar la
  identidad estable de la consola y el ownership, lineage y ciclo de vida de
  sus copias operativas, separados de las versiones de configuracion.
