---
id: 14
title: "Superficie del ingeniero para consolas bloqueadas"
map: capa-de-configuracion
label: wayfinder:grilling
status: open
assignee:
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
