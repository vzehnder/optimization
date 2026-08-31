---
id: 06
title: "Prototipo del catalogo global y la vinculacion contextual"
map: catalogo-global-series-genericas
label: wayfinder:prototype
status: closed
assignee: codex
blocked_by: [02, 03, 04, 05, 11, 12]
---

## Question

¿Que forma concreta debe tener la experiencia de descubrir, inspeccionar y
vincular series desde el catalogo y desde un objeto?

Crear un prototipo desechable para reaccionar en vivo, sin modificar
`frontend/src`. Debe cubrir como minimo: tabla global con filtros; separacion
entre entradas, resultados y legacy; detalle de una señal dentro de su set;
objetos y bindings actuales; selector compatible iniciado desde ambos lados;
vinculacion masiva con previsualizacion; reemplazo comparado; estados vacio,
carga, error, sin permiso, incompatible, stale y archivado.

Debe cubrir tambien el flujo iniciado desde un objeto ya creado para elegir
entre una serie generica reutilizable y una serie especifica del objeto. Para
la opcion especifica debe mostrar definicion, primera carga, preview y
actualizacion por archivo o API, sin crear una entrada visible en el catalogo
global. Debe hacer visibles la procedencia, revision vigente, validacion y el
hecho de que la serie especifica no puede reasignarse a otro objeto.

Cuando la serie asociada sea generica, el prototipo debe mostrar el alcance de
la actualizacion, los otros consumidores afectados y la alternativa de derivar
una serie especifica antes de cargar los nuevos valores. Ninguna actualizacion
compartida puede quedar implicita por haberse iniciado desde un solo objeto.

La resolucion enlaza el activo del prototipo y fija el comportamiento aceptado,
no codigo de produccion.

## Activo de prototipo

- [Tres variantes del catalogo global y la vinculacion contextual](../prototypes/catalogo-global-series-genericas/README.md)
  - abrir localmente con `?variant=A`, `?variant=B` o `?variant=C`;
  - estado: validado en sesion HITL; la variante C fija el patron de
    interaccion y la resolucion siguiente conserva aportes acotados de A y B.

## Resolucion

Resuelto el 2026-08-30. El usuario eligio la variante C y autorizo adoptar la
recomendacion propuesta para todas las decisiones y preguntas restantes de
este ticket.

### Decision de experiencia

La experiencia canonica combina las variantes, pero les asigna funciones
distintas y no intercambiables:

- **C, Recorrido protegido**, gobierna toda mutacion: crear una serie
  especifica, asociar una generica, crear o reemplazar un binding, cargar
  valores, publicar una revision y ejecutar operaciones masivas.
- **A, Catalogo en capas**, se conserva como superficie de lectura para
  descubrir y comparar entradas genericas. Su tabla, filtros e inspector son
  el selector al que entra C cuando el usuario elige reutilizar una fuente.
- **B, Mesa de vinculacion**, no se convierte en una tercera superficie
  principal. Su contexto objeto -> necesidad -> fuente se incorpora al
  resumen del objeto y a los pasos de seleccion y revision de C.

C no se muestra para navegar sin modificar. Explorar el catalogo, inspeccionar
procedencia, revisar consumidores y consultar historia son acciones directas.
En cuanto aparece intencion de cambiar estado, la UI abre el recorrido
protegido con contexto, pasos, prevalidacion y confirmacion. Asi C es el patron
principal de accion sin convertir tareas de lectura en un wizard innecesario.

Se mantienen dos puntos de entrada simetricos:

```text
catalogo -> senal generica -> objeto/rol compatible -> revision -> confirmar

objeto -> rol/necesidad -> generica compatible o especifica
       -> revision/datos -> confirmar
```

El camino desde el objeto es el recomendado para completar una necesidad. El
catalogo sigue siendo el recomendado cuando la intencion inicial es descubrir
o reutilizar una fuente. Ambos convergen en la misma prevalidacion y revision
final; ninguno posee una mutacion abreviada.

### Estructura del recorrido protegido

El recorrido usa cuatro momentos conceptuales, adaptando su contenido a la
accion:

1. **Origen y alcance**: objeto, rol funcional y eleccion explicita entre
   fuente generica reutilizable o serie especifica del objeto.
2. **Definicion o seleccion**: contrato compatible, identidad, propietario,
   alcance y candidato. Los incompatibles pueden explicarse, pero no elegirse.
3. **Datos o revision ejecutable**: archivo/API y preview para cargas, o
   revision/hash para asociaciones y bindings.
4. **Impacto y confirmacion**: cambios exactos, permisos, consumidores,
   staleness, atomicidad e historia antes de guardar.

El rail de C conserva siempre el objeto y el alcance visibles. Un usuario
puede volver a un paso anterior sin perder su borrador; cambiar objeto, fuente,
revision o archivo invalida la prevalidacion posterior y obliga a recalcularla.

### Lenguaje de asociacion y binding

La UI no depende de que el usuario conozca la palabra `binding`. Presenta dos
acciones diferentes y secuenciales:

- **Asociar fuente al objeto**: la fuente queda disponible para esa necesidad
  funcional y sigue la identidad vigente de la senal generica.
- **Usar revision en una variante**: se fija revision/hash para ejecutar un
  caso. En ayuda secundaria puede mostrarse `binding de ejecucion`.

Las tarjetas y la revision final muestran ambos estados por separado:
`asociada al objeto` y `usada en <variante> con <revision/hash>`. Asociar nunca
activa una variante y publicar una revision nunca mueve un binding en
silencio. Un reemplazo compara fuente, revision, hash, cobertura y resolucion,
exige motivo y conserva el binding anterior como historia.

### Serie especifica desde el objeto

La opcion especifica sigue el orden visible:

```text
objeto existente -> definicion local -> archivo o API -> preview completo
-> publicar revision -> prevalidar binding por separado
```

El propietario inmutable y la etiqueta `Solo este objeto` permanecen visibles
en todos los pasos. La revision final declara que la serie no aparecera en el
catalogo global y que no modifica otras fuentes u objetos. Guardar solo la
definicion es valido; la serie no queda seleccionable hasta tener una revision
sellada y compatible. Cambiar de archivo o payload no reasigna la identidad.

### Actualizacion de una generica compartida

La advertencia visible en el prototipo es necesaria, pero no suficiente como
unico control. El comportamiento aceptado es:

1. mostrar alcance, propietario, revision vigente, cantidad de asociaciones,
   otros objetos, proyectos y bindings que quedaran stale;
2. listar una muestra de consumidores con acceso a la lista completa;
3. ofrecer primero **Crear especifica para este objeto** cuando la intencion
   declarada es local;
4. rotular la alternativa compartida como **Publicar para todos**, nunca como
   `Guardar` o `Actualizar`;
5. exigir permiso, motivo, checkbox de comprension y una revision final que
   repita el impacto antes de habilitar la publicacion;
6. volver a validar ETag, token e impacto al confirmar. Cualquier cambio desde
   el preview bloquea la accion y exige una nueva confirmacion.

Derivar una especifica conserva linaje y no reemplaza asociaciones o bindings
automaticamente. Publicar para todos crea una revision comun y deja visibles
los estados stale que resulten; no los resuelve en la misma accion.

### Vinculacion masiva y estados

Las operaciones masivas usan la densidad de A dentro de C: seleccion,
prevalidacion tabular y resumen antes/despues. El guardado es atomico. Una fila
incompatible bloquea el lote completo, conserva las selecciones y ofrece un
reporte descargable; no hay exitos parciales implicitos.

Los estados del prototipo fijan estas respuestas comunes:

| Estado | Comportamiento aceptado |
| --- | --- |
| Vacio | Explica filtros; desde un objeto ofrece crear una especifica, pero el catalogo no la publica. |
| Cargando | Conserva contexto y comunica que valida permisos y compatibilidad. |
| Error | Conserva filtros o borrador, muestra `request_id` y confirma que no hubo mutacion. |
| Sin permiso | No revela identificadores, conteos ni existencia fuera del alcance. |
| Incompatible | Bloquea seleccion y muestra razon legible mas codigo estable. |
| Stale | Bloquea ejecucion y ofrece comparar revision vigente, revalidar pin o reemplazar. |
| Archivado | Permite lectura e historia, pero no nuevas asociaciones, bindings ni revisiones. |

Resultados y legacy siguen en superficies separadas. Un resultado es
read-only y solo entra como input mediante transformacion versionada; legacy
se muestra por adaptador y todo vinculo nuevo termina en el modelo generico.

### Consecuencias y traspasos

La implementacion no debe copiar literalmente ninguna de las tres variantes.
Debe construir una superficie de catalogo de lectura, un resumen contextual
por objeto y un solo patron protegido de mutacion. Esto reduce caminos
divergentes y hace que la misma prevalidacion del backend sostenga UI, archivo
y API.

No aparecieron preguntas nuevas ni niebla adicional. "Migracion y
coexistencia con el modelo actual" debe preservar estos puntos de entrada;
"Rendimiento, indices e integridad transaccional" debe sostener previews y
confirmaciones sin cargar consumidores o puntos completos; y "Corte de
entrega y criterios de aceptacion" debe probar cada estado y la ausencia de
mutaciones implicitas.
