---
id: 07
title: "Contrato de la tabla editable y del pegado desde Excel"
map: capa-de-configuracion
label: wayfinder:prototype
status: closed
assignee: vzehnder
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

**Restricciones confirmadas por Donde aterriza la edicion de series del
operador**:

- la tabla edita una copia operativa, nunca el set canonico;
- entrar en modo edicion requiere un lease exclusivo sobre esa copia y deja a
  los demas usuarios en solo lectura;
- todo guardado envia la revision base y se rechaza completo si dejo de ser la
  vigente, sin mezcla automatica;
- antes de confirmar se muestra el diff y el resumen estructurado del bloque;
- el historial operativo es simplificado y solo permite al operador deshacer
  su propio ultimo guardado mientras siga vigente.

El prototipo debe hacer visibles el propietario/expiracion del lease y la
recuperacion ante conflicto de revision.

**Restricciones confirmadas por Edicion del operador frente a la regla
fail-closed**:

- el guardado es la atestacion: la misma transaccion que crea la revision
  refresca el `recorded_hash` de la dependencia `time_series_set` de la
  variante de la consola, y solo esa. El contrato de guardar del prototipo debe
  incluir ese efecto, porque de el depende que ejecutar quede habilitado;
- no hay paso de revalidar ni boton equivalente en la consola. Despues de
  guardar, ejecutar procede directo;
- el selector de periodo se limita al rango que la copia operativa cubre. El
  pegado no extiende el horizonte: `validate_catalog_value_edits` rechaza todo
  `period_index` que no este ya en el set;
- una edicion no puede romper cobertura, huecos ni valores faltantes, asi que
  el contrato de error del pegado solo necesita cubrir valor no numerico, no
  finito, negativo donde la señal lo prohibe, periodo o señal desconocidos, y
  conflicto de revision base.

## Activo

[Prototipo desechable: tabla editable y pegado desde Excel](../prototypes/tabla-editable/README.md)
— tres formas de tabla (`?variant=A|B|C`) sobre 8760 periodos virtualizados,
con pegado de portapapeles real, parser de locale conmutable, validacion por
celda espejo de `validate_catalog_value_edits`, diff previo, lease ajeno y
conflicto de revision base.

## Resolucion

Decision aprobada en sesion de reaccion el 2026-08-20, sobre el prototipo
enlazado como activo.

### Forma de la tabla

La consola usa **una tabla por grupo del analista** (variante A). Se descartan
la tabla unificada por caso y la tabla por copia operativa.

Consecuencia estructural: un grupo puede contener señales que viven en copias
operativas distintas —Potencia toca dos—, asi que **la forma de la tabla no
coincide con la particion en sets**. El operador nunca ve esa particion; el
sistema la resuelve por debajo.

### Guardado transaccional entre copias

Un guardado que toca N copias operativas es **una sola transaccion**: entran las
N revisiones o no entra ninguna.

- El backend necesita un **endpoint de edicion multi-set**.
  `edit_time_series_set_values` pasa a ser la implementacion interna de un
  guardado mas grande, no el contrato de la superficie.
- El refresco del `recorded_hash` que el ticket 06 definio como atestacion
  ocurre **dentro de esa misma transaccion**, una vez, al final. No existe
  ventana en que la atestacion este fresca para una copia y vieja para otra.
- Un conflicto de revision base en **cualquiera** de las N copias rechaza el
  bloque completo, sin mezcla automatica, extendiendo la regla del ticket 05.

Motivo del rechazo de los guardados independientes: dejarian a la consola con
atestacion parcial, y "¿puedo ejecutar?" dejaria de tener una respuesta unica.

### Formato numerico: se rechaza lo ambiguo

**No hay locale configurable.** El separador decimal se deduce de la estructura
del texto, y el unico caso que no se puede deducir se rechaza.

Una cadena es ambigua cuando tiene **un unico separador seguido de exactamente
tres digitos, precedido de un grupo de miles valido** (1 a 3 digitos, sin cero a
la izquierda): `1.234`, `1,234`, `12,345`. Se marcan invalidas y obligan a
corregir en el origen.

Todo lo demas tiene lectura unica: con ambos separadores presentes gana el
ultimo (`1.234,5` y `1,234.5` son 1234,5); dos separadores iguales son miles
(`1.234.567`); cuatro digitos por delante no forman grupo de miles
(`1234,567` = 1234,567); `0` no es grupo de miles (`0,001` = 0,001).

Consecuencia para el backend: el `float()` pelado de
`validate_catalog_value_edits` se reemplaza por este parser. Hoy `1.234` se
acepta en silencio como 1,234 —un factor 1000 de error que ningun validador
detecta— y `1.234,5` revienta con un error generico.

Beneficio lateral: **la configuracion por proyecto no necesita campo de
formato numerico**, que era candidato a entrar en el modelo de datos.

### Validacion y contrato de error

**Todo o nada.** Si alguna celda del bloque es invalida, no entra ninguna. El
operador corrige las marcadas o descarta el bloque. Es la misma garantia que
TS-2 da para un import fallido y que el ticket 05 da para el conflicto de
revision.

El contrato de error del pegado cubre exactamente: valor no numerico, no
finito, negativo donde la señal lo prohibe, **formato ambiguo**, periodo
desconocido, señal desconocida y conflicto de revision base.

Exigencia nueva sobre el backend: el error debe venir **direccionado por celda**
(indice de periodo + `signal_key`), no por posicion en la lista. Hoy
`validate_catalog_value_edits` responde `edit 37: ... must be nonnegative`, en
ingles y por numero de edicion, que la superficie no puede mapear a una celda.

### Tramo editable y desborde

El selector de tramo **acota la edicion**, no solo la vista: fuera del tramo la
tabla se ve pero no se edita ni recibe pegado.

- Un bloque mas largo que el tramo **se trunca y se avisa**, no se rechaza.
- El pegado nunca extiende el horizonte: los periodos que la copia no cubre no
  existen y `validate_catalog_value_edits` los rechaza.
- **Sin tope de tamaño**: el año completo (8760 h) es un tramo editable valido.
  Un guardado de dos señales por 8760 periodos son ~17.500 celdas, del orden de
  840 KB en un solo PUT, que el contrato actual admite sin cota.

Queda para el **Modelo de datos de la configuracion por proyecto** definir quien
declara los tramos seleccionables y con que granularidad.

### Gesto de pegado

Validado en el prototipo y adoptado tal cual:

- el bloque se alinea **desde la celda anclada** hacia abajo y a la derecha;
- se aceptan **rangos rectangulares**, no solo columnas sueltas;
- una fila de encabezado pegada por accidente se **detecta y se descarta** con
  aviso (primera fila sin ningun digito);
- las columnas que el ingeniero no habilito se **omiten** del pegado y se
  informan por nombre; se distinguen visualmente con trama, candado y el motivo
  del bloqueo en el tooltip.

### Revision previa al guardado

La hoja de revision —celdas, periodos, copias tocadas, rango antes/despues por
señal, lista de rechazos— esta **siempre disponible pero nunca es obligatoria**.
Guardar procede directo.

Riesgo aceptado explicitamente: un pegado truncado puede llegar a la corrida sin
que nadie abra la revision. El unico garante es el **aviso del pegado**, que por
eso **persiste hasta que el bloque se guarde o se descarte** y no se limpia al
editar otras celdas.

### Escala

La tabla **virtualiza** obligatoriamente: 8760 filas se renderizan por ventana,
con encabezado y columna de periodo fijos. No se mantiene borrador en memoria
—los valores se leen de SQL, como fijo el ticket 02— y el estado sucio vive solo
en las celdas editadas.

### Limites de esta decision

Esta resolucion fija el contrato de la superficie de edicion. No decide donde se
persiste (ticket 05), como se atesta (ticket 06), que entidad guarda los grupos,
etiquetas, señales habilitadas y tramos (**Modelo de datos de la configuracion
por proyecto**), ni como se representa todo eso para el frontend (**Contrato del
payload de las superficies configuradas**).
