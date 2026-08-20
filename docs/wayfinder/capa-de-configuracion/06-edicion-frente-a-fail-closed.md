---
id: 06
title: "Edicion del operador frente a la regla fail-closed"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
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

**Restriccion confirmada por Donde aterriza la edicion de series del
operador**: la edicion nunca toca el set canonico ni afecta variantes ajenas.
La consola trabaja sobre una copia operativa propia y compartida; cada
guardado avanza su revision y su hash. Por tanto, este ticket debe resolver la
revalidacion de la variante operativa despues de ese cambio, no la propagacion
de staleness por todo el proyecto. Cada corrida debe seguir registrando la
revision exacta de la copia que materializo.

## Resolucion

Decision tomada en sesion de grilling el 2026-08-20.

### El hallazgo que reencuadra el ticket

`validate_case_input_variant` y `materialize_system_case_for_variant`
(`app/persistence.py:7299-7340`) llaman ambos a
`_resolve_variant_series_for_range`. Revalidar y correr revisan exactamente lo
mismo. La unica diferencia es que materializar se niega si el marcador stale
esta puesto, y validar lo limpia sobrescribiendo los hashes grabados.

Eso parte el fail-closed en dos cosas que este ticket trataba como una:

- **Chequeos duros**, que corren siempre en ambos caminos: señales requeridas
  bindeadas, sets derivados no stale, cobertura exacta del horizonte sin huecos
  ni solapes, ningun valor faltante (`app/input_variants.py:62`,
  `app/persistence.py:7203-7245`).
- **El marcador stale**, que no revisa nada. `validation_dependencies` guarda
  solo `recorded_hash` y timestamps, **sin actor** (`app/persistence.py:7166`).
  Es una atestacion anonima, no una validacion.

A esto se suma que una edicion del operador **no puede romper ningun chequeo
duro**: `validate_catalog_value_edits` (`app/time_series_catalog.py:491`)
rechaza todo periodo que no este ya en el set, toda señal que no este ya en el
set, y todo valor no numerico, infinito o negativo cuando la señal lo prohibe.
No existe forma de borrar un valor ni de sacar un periodo. Un pegado solo
cambia numeros en su lugar.

### El guardado del operador es la atestacion

El backend, al aceptar un guardado del operador sobre la copia operativa,
refresca los hashes grabados de la variante de la consola **en la misma
transaccion** que crea la revision. La variante nunca llega a estar stale por
causa propia. La revalidacion deja de existir como paso para esta superficie:
ni automatica ni manual.

La asimetria que lo justifica: cuando un analista queda stale es porque algo se
movio debajo de el sin que lo pidiera, y la pared tiene sentido. Cuando el
operador queda stale, la causa es el mismo, hace dos segundos, escribiendo a
mano en una tabla que la consola le puso adelante, con el diff obligatorio de
**Donde aterriza la edicion de series del operador** ya confirmado. Pedirle que
atestigue lo que acaba de escribir es un tramite invisible.

La garantia no se debilita porque no vivia ahi: la dan los chequeos duros, que
siguen corriendo en cada corrida y siguen fallando cerrado. La trazabilidad
mejora: el historial de revisiones de la copia tiene actor, diff y nota, contra
una atestacion anonima que no tenia ninguno de los tres.

### Refresco quirurgico: una sola dependencia

La variante graba varias dependencias, no una: `topology`, `parameters`, y un
`time_series_set` por cada set bindeado (`app/persistence.py:7278-7295`). El
guardado refresca **unicamente** el `recorded_hash` de la dependencia
`time_series_set` que corresponde a la copia operativa. Nada mas se toca.

Se descarta el refresco total: reconciliar la variante entera dejaria que el
guardado del operador borre por la puerta de atras un stale de topologia o de
parametros que nadie miro, y expondria al operador a que su pegado sea
rechazado por un error que no causo ni puede arreglar.

La regla queda enunciable en una linea: **el cambio propio del operador no deja
stale la variante; el cambio de cualquier otro, si.**

### Editar y correr siguen siendo dos pasos

Despues de un guardado aceptado la variante no esta stale por causa propia, asi
que correr procede directo: `materialize_system_case_for_variant` encuentra el
marcador limpio y `_resolve_variant_series_for_range` corre igual todos los
chequeos duros. La consola **nunca llama al endpoint de validar variante**; ese
endpoint queda como superficie de `analyst` y `admin`.

Se descarta la operacion atomica editar-y-correr: fusionarlas esconde el
guardado, y el guardado es justamente la atestacion que reemplaza a la
revalidacion. El unico estado intermedio visible es el que ya fijo **Forma del
cascaron de la consola de operador** —cambios sin guardar / guardando, con
ejecutar deshabilitado— y desaparece solo al confirmar.

### La copia operativa es un set plano

La copia se materializa como set **no derivado**: conserva los valores, no la
receta de transformacion. El linaje al set y revision de origen queda como
metadata visible para `analyst` y `admin`, no como dependencia viva.

Sin esto el diseño se traba. Si la copia heredara las dependencias del set
origen, la primera edicion moveria su `content_hash`,
`evaluate_time_series_set_staleness` la marcaria stale-derivada, y
`_resolve_variant_series_for_range` levantaria `VariantStaleError` antes que
cualquier otro chequeo (`app/persistence.py:7216-7239`), con un unico camino de
salida —regenerar— que borraria las ediciones del operador. Un set no derivado
no tiene dependencias grabadas y nunca esta stale
(`app/persistence.py:3360-3365`).

Consecuencia asumida: la copia no se regenera nunca. Si el ingeniero cambia la
transformacion de origen, eso no se propaga; hay que crear una copia nueva, que
es el camino que **Donde aterriza la edicion de series del operador** ya
contempla como elegir otra version base.

Esto tambien disuelve la pregunta original sobre sets derivados: el operador no
puede editar un set que sea origen de un derivado, porque edita una copia de la
que no deriva nada.

### Stale ajeno: bloquear, traducir, escalar

Es el caso que sobrevive y donde el fail-closed sigue haciendo trabajo real:
topologia o parametros que movio el ingeniero. La consola traduce las `reasons`
de `VariantStaleError` a una frase sin vocabulario interno —la configuracion de
este plan cambio y necesita revision del equipo que la preparo—, bloquea
ejecutar, y ofrece avisar, apuntando a quien preparo la configuracion, dato que
la consola ya muestra en pantalla.

**El operador no tiene boton de revalidar.** Darselo repondria exactamente el
sello de goma anonimo que esta resolucion elimina, y en el unico caso donde el
sello no significaria nada: el operador no puede juzgar un cambio de topologia.
Solo `analyst` y `admin` limpian ese stale, por el endpoint que ya existe. Las
ediciones del operador no se pierden: siguen guardadas en la copia.

### El pegado no extiende el horizonte

Extender es un import, no una edicion. La consola lo sostiene por diseño: el
selector de periodo se limita al rango que la copia cubre, asi que el operador
no llega a pedir algo fuera de rango. Necesitar un horizonte mas largo es tarea
del ingeniero.

### La regla es del endpoint, no del rol

Cualquier escritura aceptada sobre la copia operativa a traves de los endpoints
de la consola —guardar, deshacer, y restaurar por `analyst` o `admin`— refresca
ese unico hash en la misma transaccion. El argumento no es que fue el operador,
es que la escritura paso por una superficie con diff, actor y auditoria. Una
escritura sobre la copia por cualquier otra via si deja stale la variante y cae
en el caso anterior.

### Lo que ya se cumple por construccion

`series_bindings` —con `revision_number` y `content_hash` por set— se persiste
dentro del `generation_metadata` de la version inmutable de la corrida
(`app/main.py:2274-2283`). El requisito de que cada corrida registre la revision
exacta de la copia que materializo ya esta satisfecho. No hay que diseñarlo,
solo no romperlo al hacer pasar la copia operativa por ese mismo camino.

### Efecto sobre terceros

Ninguno. **Donde aterriza la edicion de series del operador** ya aislo la copia:
no hay variantes ajenas que puedan quedar stale por una edicion operativa.

### Consecuencias para el resto del mapa

- **Contrato de la tabla editable y del pegado desde Excel**: el contrato de
  guardar incluye el refresco del hash de la variante en la misma transaccion,
  y el selector de periodo se limita al rango cubierto por la copia.
- **Modelo de datos de la configuracion por proyecto**: la copia operativa se
  representa como set no derivado con linaje inerte, y la variante de la consola
  necesita que su dependencia sobre la copia sea direccionable para el refresco
  puntual.
- **Contrato del payload de las superficies configuradas**: el bloqueo por stale
  ajeno viaja al frontend ya traducido, sin `dependency_type` ni hashes.
- Abre **Superficie del ingeniero para consolas bloqueadas**: esta resolucion
  deja al operador escalando hacia una superficie que todavia no existe.
