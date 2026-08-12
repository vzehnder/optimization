---
id: 07
title: "Contrato de la tabla editable y del pegado desde Excel"
map: capa-de-configuracion
label: wayfinder:prototype
status: open
assignee:
blocked_by: [02, 05]
---

## Question

¿Que es exactamente "pegar una columna desde Excel" y que hace el sistema con
lo pegado?

Es el gesto que define la consola de operador, y esta lleno de detalle que solo
se ve prototipando con datos reales. La primitiva de backend ya existe
(`edit_time_series_set_values` toma una lista de `CatalogValueEdit`); lo que
falta es el contrato de la superficie.

A resolver con el prototipo:

- **Forma de la tabla**: filas = periodos con su timestamp; columnas = señales
  que el ingeniero habilito. ¿Una tabla por set, o una tabla unificada por
  caso que mezcla señales de sets distintos? Lo segundo es mas comodo para el
  operador y mas dificil de mapear de vuelta.
- **Alineacion del pegado**: al pegar N valores desde la celda seleccionada,
  ¿que pasa si N no coincide con el numero de periodos visibles? ¿Se trunca, se
  rechaza, se extiende el horizonte? Ligado a la decision de cobertura del
  ticket de fail-closed.
- **Formato numerico**: Excel en es-CL usa coma decimal y punto de miles. Pegar
  `1.234,5` debe interpretarse bien o rechazarse claramente, nunca leerse como
  `1.234`. Decidir el parser y si es configurable.
- **Pegado de bloques**: ¿solo columnas, o tambien rangos rectangulares que
  cubren varias señales a la vez? ¿Y encabezados pegados por accidente?
- **Validacion en vivo**: las reglas del registro canonico (no negativos donde
  corresponde, numerico, unidad) deben aplicarse antes de guardar, marcando la
  celda ofensora. ¿Se puede guardar parcialmente o es todo o nada? TS-2 ya
  garantiza que un import fallido no deja revision parcial; conviene mantener
  esa propiedad.
- **Escala de datos**: un año horario son 8760 filas. ¿La tabla virtualiza?
  ¿Se puede editar solo un tramo? ¿Cuanto pesa el request de guardado?
- **Deshacer y comparar**: ¿el operador ve que cambio respecto de la revision
  anterior antes de confirmar? Un diff previo al guardado es probablemente lo
  que separa esto de ser peligroso.
- **Solo lectura vs. editable**: como se distingue visualmente una columna que
  el ingeniero no habilito.

**Insumo de** [Inventario de la superficie configurable existente](01-inventario-superficie-configurable.md),
seccion C y E:

- El parser de valores es `float()` pelado, sin locale. Hoy `"1.234,5"` falla y
  `"1.234"` se lee como 1,234. El formato es-CL no esta contemplado en ninguna
  capa.
- La edicion no puede crear periodos ni senales: solo reemplaza celdas que ya
  existen. Eso responde por si solo la pregunta de "que pasa si pego mas filas".
- El contrato de guardado no tiene cota de tamano; un ano horario entra en un
  solo `PUT`.
- Las columnas de la tabla son derivables sin listas fijas: `required_signals`
  de la variante da el eje de senales.

Enlazar el prototipo desde este ticket como activo.

**Restriccion confirmada por el cascaron**: la tabla no mantiene un borrador
solo en memoria. Lee los valores desde SQL y el gesto de guardar debe persistir
el bloque validado de forma atomica, creando una revision auditable. El
prototipo de este ticket debe resolver el estado sucio/guardando/guardado y el
contrato de error sin fingir que la persistencia es instantanea.
