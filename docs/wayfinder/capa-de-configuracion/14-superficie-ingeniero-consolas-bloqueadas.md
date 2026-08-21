---
id: 14
title: "Superficie del ingeniero para consolas bloqueadas"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
blocked_by: [06]
---

## Question

**Edicion del operador frente a la regla fail-closed** decidio que el operador
nunca revalida: cuando la variante de su consola queda stale por una causa
ajena —topologia o parametros que movio el ingeniero— la consola bloquea la
ejecucion, traduce el motivo y ofrece avisar a quien preparo la configuracion.
Ese aviso apunta hoy a una superficie que no existe. ¿Como es?

Lo que hay que decidir:

- **¿Como se entera el ingeniero?** ¿El aviso del operador es el unico
  disparador, o el sistema le muestra al analista, en el momento de guardar un
  cambio de caso, que hay consolas activas que quedaran bloqueadas? Lo segundo
  convierte un incidente reactivo en una advertencia previa.
- **¿Donde vive esa superficie?** ¿Una vista propia de consolas por proyecto,
  una columna de estado en la pantalla de escenario que ya existe, o una
  bandeja de avisos? Notar que hoy no hay ninguna superficie que liste consolas
  de operador; se crea junto con el resto de la capa de configuracion.
- **¿Que ve el ingeniero al abrirla?** Que consola, quien esta esperando, desde
  cuando, que dependencia se movio y quien la movio. Y si puede ver las
  ediciones pendientes del operador antes de desbloquear, dado que revalidar
  habilita a correr con esos valores.
- **¿Desbloquear es un solo gesto?** El endpoint de validar variante ya existe
  y ya hace el trabajo. ¿Alcanza con exponerlo, o el ingeniero necesita
  confirmar explicitamente que reviso el cruce entre su cambio y los datos del
  operador?
- **¿Y el caso inverso, silencioso?** La copia operativa es un set plano que no
  se regenera nunca. Si el ingeniero cambia la transformacion que produjo el
  set de origen, la copia queda vieja **sin que nada se marque stale** y el
  operador sigue corriendo con datos que ya no reflejan la receta actual. ¿Se
  detecta y se avisa, o se acepta como precio del aislamiento? Esta es la unica
  grieta que abrio la decision del set plano.
- **¿Hay caducidad?** Una consola bloqueada durante semanas porque nadie
  atendio el aviso, ¿escala a `admin`, se archiva, o queda esperando?

La respuesta es una seccion del spec: la superficie del ingeniero sobre las
consolas de su proyecto, sus estados y el gesto de desbloqueo, mas la regla de
notificacion en ambas direcciones.

## Restricciones confirmadas por el modelo de datos

**Modelo de datos de la configuracion por proyecto** le agrega un caso a este
ticket y le quita trabajo:

- **caso nuevo, el puntero colgando.** Un campo expuesto apunta al caso con
  `{asset_id, field}`. Si el ingeniero borra o renombra el activo, el puntero
  queda colgando; se detecta al cargar la consola y bloquea fail-closed, igual
  que el stale ajeno. Este ticket debe cubrir por tanto **dos** motivos de
  bloqueo y no uno —variante stale y puntero roto— con la misma superficie de
  aviso y desbloqueo. El override no se borra: queda inerte, y vuelve a aplicar
  si el campo reaparece con el mismo nombre;
- **facilidad nueva.** Listar las consolas de un proyecto pasa a ser una
  consulta sobre `operator_consoles`, no una derivacion. La superficie que este
  ticket diseña ya tiene de donde leer, incluido el estado `draft`/`active`;
- la consola tiene **variante propia**, clonada de la del analista, asi que el
  aviso puede nombrar exactamente que consola quedo bloqueada sin confundirla
  con las variantes de trabajo del analista;
- este ticket es candidato natural a **absorber** la mitad de niebla que quedo
  abierta en *Estrategia de validacion de la configuracion*: que chequea el
  esquema al guardar y como se le muestra al ingeniero antes de que un operador
  choque con ello. Decidir al resolverlo si lo absorbe o si merece ticket
  propio.

## Restricciones confirmadas por el contrato del payload

**Contrato del payload de las superficies configuradas** le da a este ticket su
contraparte exacta:

- **esta superficie es del analista y no esta sujeta a la allowlist del
  operador.** Es el unico lugar donde vive el detalle tecnico que el operador
  nunca ve: `stderr`, `exit_code`, `error_message`, las `reasons` crudas de
  `VariantStaleError` y los hashes de dependencia;
- **el puente entre ambas es `reference`.** Cuando una corrida falla por una
  causa que el backend no sabia antes de invocar al motor, el operador recibe un
  generico con el id de la corrida. Esa superficie tiene que poder recibir ese
  id y llevar al ingeniero al detalle. Si no, el operador queda con un numero
  que nadie sabe usar;
- **el operador ve exactamente dos motivos de bloqueo**, `dependencia_movida` y
  `campo_no_disponible`, ambos con una frase accionable y un contacto. La
  superficie que este ticket diseña debe poder explicar los dos y desbloquear
  los dos, porque son los dos unicos que el operador puede reportar;
- el `contact` que el operador ve sale del sobre como **nombre de persona**. A
  quien apunta —quien preparo la configuracion, o quien movio la dependencia—
  es una decision de este ticket, no del payload.

## Resolucion

Decision tomada en sesion de grilling el 2026-08-21, con **lente MVP explicito**:
lo basico completo, sin funcionalidad de mas. Cada recorte queda nombrado abajo.

### El reencuadre: no se crea una superficie

El ticket preguntaba donde vive una superficie nueva. La respuesta es que no hay
ninguna: **la lista de consolas de un proyecto tiene que existir igual**, porque
el ingeniero necesita donde crearlas y editarlas, y **Modelo de datos de la
configuracion por proyecto** ya la dejo como consulta directa sobre
`operator_consoles` en vez de una derivacion.

El bloqueo es por tanto una **columna de estado en una lista que ya se
construye**, no una vista aparte, ni una bandeja, ni un incidente con su propio
flujo. Todo lo que decide este ticket se apoya sobre ese unico artefacto.

La lista cuelga del workspace de escenario, junto a las variantes, porque ahi ya
viven el caso y la variante de la que la consola clona la suya. **Navegacion y
aterrizaje por perfil** decide como se llega globalmente; aqui no se inventa
ruta nueva.

### Los dos hallazgos que cambian la pregunta

**El primero: los dos motivos de bloqueo no se desbloquean igual.** El ticket
los trataba como un par simetrico que una misma superficie explica y resuelve.
Lo son para explicar, no para resolver:

- `dependencia_movida` —variante stale por causa ajena— se arregla
  **revalidando la variante de la consola**. El endpoint ya existe
  (`app/main.py:2235`) y ya hace exactamente el trabajo;
- `campo_no_disponible` —puntero `{asset_id, field}` colgando— **no se arregla
  revalidando**. Revalidar recompone hashes; no hace reaparecer un activo
  borrado. Se arregla **editando el documento de configuracion**: quitando el
  parametro expuesto o re-apuntandolo a un campo que exista.

Solo el primero es un boton. El segundo es una consecuencia de arreglar la
configuracion, y la superficie lo dice con esas palabras en vez de ofrecer una
accion que no funcionaria.

**El segundo: quien movio la dependencia no es contestable.**
`validation_dependencies` tiene `owner_type`, `owner_id`, `dependency_type`,
`dependency_id`, `recorded_hash` y timestamps (`app/persistence.py:740-750`).
**No tiene columna de actor**, tal como **Edicion del operador frente a la regla
fail-closed** ya habia observado al llamarla atestacion anonima.

El ticket pedia mostrar que dependencia se movio y quien la movio. La primera
mitad sale de las `reasons`; la segunda **se cae del alcance**. Agregarla es una
columna nueva y una escritura en cada camino que toca una dependencia: aditivo,
fuera del MVP, y con consecuencia directa sobre el `contact` (ver abajo).

### Como se entera el ingeniero: dos mitades, ningun inbox

No existe infraestructura de notificaciones en la aplicacion, y no se crea. Las
dos mitades se resuelven sin ella:

- **Advertencia previa, sincrona.** Al guardar un cambio de caso —topologia o
  parametros— el backend consulta las consolas `active` de ese proyecto y
  responde, **en el mismo request**, cuantas quedaran bloqueadas y cuales. No es
  un evento ni una cola: es un campo mas de la respuesta del guardado. Convierte
  el incidente reactivo en una advertencia previa, que era el punto del ticket.
  **No bloquea el guardado**: informa. El ingeniero es dueño de su caso.
- **El aviso del operador es un flag, no una notificacion.** Cuando el operador
  usa el avisar que fijo la regla fail-closed, se escribe `esperando_desde` en
  la fila de la consola. El ingeniero lo ve cuando abre la lista. Se limpia al
  desbloquear.

El stale no es un evento sino una comparacion perezosa —`evaluate_variant_staleness`
(`app/variant_staleness.py:44`) compara hashes grabados contra actuales cuando
alguien pregunta—, asi que ambas mitades son consultas en el momento de mirar.
Nada que persistir salvo el flag.

### Que ve el ingeniero

Esta superficie es del analista y **no esta sujeta a la allowlist del operador**,
como fijo **Contrato del payload de las superficies configuradas**. Es el unico
lugar donde vive el detalle tecnico.

Por fila de la lista: nombre de la consola, estado `draft`/`active`, estado de
bloqueo (ninguno / `dependencia_movida` / `campo_no_disponible`), y si hay
alguien esperando, desde cuando. Al abrir la fila bloqueada: las `reasons`
crudas de `VariantStaleError` —con `dependency_type` y `dependency_id`, que es
justamente lo que el operador nunca ve— o el puntero exacto que quedo colgando.

Las ediciones pendientes del operador se alcanzan por **link al historial de
revisiones de la copia operativa**, que ya tiene actor, diff y nota. No se
construye vista de diff propia: el historial ya existe y ya dice lo necesario
para juzgar el cruce antes de desbloquear.

### Desbloquear es un solo gesto, sin ceremonia

Para `dependencia_movida`: un boton que llama al endpoint de validar variante
que ya existe. **Sin confirmacion explicita** de que el ingeniero reviso el
cruce con los datos del operador. Un checkbox de confirmo que revise es un
sello de goma —exactamente lo que la regla fail-closed elimino del lado del
operador— y no habria coherencia en reponerlo del lado del ingeniero. El link al
historial de la copia es la manera de revisar; usarlo o no es criterio
profesional, no un tramite.

Para `campo_no_disponible`: link a la edicion de la configuracion de esa
consola, con el parametro roto señalado. El desbloqueo ocurre al guardar la
configuracion arreglada.

### La copia vieja se detecta y no bloquea

El caso inverso silencioso —el ingeniero cambia la transformacion que produjo el
set de origen y la copia plana no se entera— se resuelve con la comparacion mas
barata posible: `origin_revision_number`, que `operator_console_series_copies`
ya guarda, contra el `MAX(revision_number)` actual del set de origen. Dos
enteros que ya estan almacenados.

Si el origen avanzo, la fila muestra un **badge informativo**: la receta de
origen tiene revisiones nuevas que esta copia no refleja. **No bloquea.**
Bloquear contradiria el aislamiento del set plano que **Edicion del operador
frente a la regla fail-closed** eligio a proposito, y le quitaria al operador
una consola que funciona por un motivo que no es suyo.

El camino de salida ya existe y no se diseña aqui: crear una copia nueva desde
la version base actual, que **Donde aterriza la edicion de series del operador**
ya contempla.

Se acepta el badge en vez del silencio porque el costo es una consulta y la
alternativa es que el operador corra indefinidamente sobre datos que ya no
reflejan la receta vigente, sin que nadie pueda verlo. La grieta no se cierra;
se hace visible.

### Sin caducidad

Una consola bloqueada no escala a `admin`, no se archiva y no expira. El flag
`esperando_desde` espera hasta que alguien lo atienda, y la fecha que muestra es
toda la presion que el sistema ejerce.

Caducar exige un scheduler que la aplicacion no tiene. Es el recorte mas claro
del ticket y es aditivo de revertir.

### El `reference` ya tiene donde aterrizar

Cuando una corrida falla por una causa que el backend no sabia antes de invocar
al motor, el operador recibe `ejecucion_fallida` con `reference` = el id de la
corrida. Ese id **es** el id de `runs`, y la ruta `runs/:runId` ya existe y ya
muestra `exit_code` (`frontend/src/Workspace.tsx:7716`) y `stderr`
(`frontend/src/Workspace.tsx:7899`) al analista.

El puente que el contrato del payload pedia no hay que construirlo: hay que no
romperlo. La unica adicion es que el historial de corridas de la consola, visto
desde esta superficie, enlace a esa ruta.

### El `contact` apunta a quien preparo la configuracion

**Contrato del payload de las superficies configuradas** dejo esta decision
aqui. La respuesta la fuerza el dato disponible: `console.prepared_by` ya viaja
en el sobre, y quien movio la dependencia no se sabe.

Es ademas la eleccion correcta por contenido y no solo por disponibilidad: quien
preparo la configuracion sabe que hace esa consola y para quien. Quien movio la
topologia puede ser alguien que no sabe que esa consola existe.

### Absorbe la niebla de validacion, y la cierra por decision

**Modelo de datos de la configuracion por proyecto** marco este ticket como
candidato a absorber la mitad abierta de *Estrategia de validacion de la
configuracion*. La absorbe, y la resuelve recortando:

**no hay linter semantico en el MVP.** La estrategia de validacion completa son
dos piezas que ya estan decididas: rechazo duro contra el esquema en codigo al
guardar, y fail-closed al cargar la consola para el puntero colgando. Un rango
por defecto invalido o un grupo con una señal que el caso no requiere **no se
detectan al guardar**: aparecen cuando alguien abre la consola.

Se recorta porque cada chequeo semantico es una regla nueva que hay que
mantener sincronizada con la forma del caso, y porque la advertencia previa al
guardar un cambio de caso ya cubre el error que de verdad duele —dejar
bloqueados a operadores que estan trabajando—. Los demas los paga el ingeniero
al probar su propia consola, que es un ciclo corto.

La niebla del mapa se cierra: deja de ser no suficientemente nitida para
ticketear y pasa a ser un corte asumido.

### Cortes MVP asumidos

Todos aditivos de revertir. Se listan para que nadie los confunda con descuidos:

- **No se registra quien movio una dependencia.** Requiere columna de actor en
  `validation_dependencies` y escritura en cada camino que la toca.
- **No hay caducidad ni escalamiento** de una consola bloqueada sin atender.
- **No hay linter semantico** de la configuracion al guardar.
- **La advertencia previa no bloquea el guardado** del cambio de caso, ni ofrece
  deshacerlo.
- **El badge de copia vieja no ofrece regenerar**: solo informa. Crear una copia
  nueva es el camino existente, manual.
- **La advertencia previa cubre `active` solamente.** Una consola en `draft` que
  quedara bloqueada no se menciona: no hay nadie esperando.

### Consecuencias para el resto del mapa

- **Navegacion y aterrizaje por perfil** hereda una superficie mas que ubicar:
  la lista de consolas del ingeniero, dentro del workspace de escenario. No es
  una ruta nueva de nivel superior.
- **Especificacion consolidada de la capa de configuracion** gana una seccion:
  la superficie del ingeniero sobre las consolas de su proyecto, sus estados y
  los dos gestos de desbloqueo.
- El mapa pierde un item de niebla: *Estrategia de validacion de la
  configuracion* queda cerrada por decision, no por especificacion.
