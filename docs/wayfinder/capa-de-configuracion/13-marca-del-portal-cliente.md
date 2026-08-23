---
id: 13
title: "Alcance de marca del portal cliente"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
blocked_by: [03, 08]
---

## Question

¿Que elementos de marca del informe ejecutivo son configurables y a que nivel
pertenecen cuando un proyecto puede ser visible para varios usuarios cliente?

La forma del portal ya esta fijada. Falta decidir si usa siempre la marca del
producto o si la configuracion por proyecto admite nombre visible, logo y
colores; si el nombre del cliente es solo informativo; y si dominio propio o
white-label quedan fuera de esta primera especificacion.

La respuesta debe evitar una configuracion distinta por persona y encajar con
el alcance por proyecto que defina **Modelo de datos de la configuracion por
proyecto**.

## Restriccion confirmada por el modelo de datos

**Modelo de datos de la configuracion por proyecto** ya cerro el envase: la
configuracion de portal es **un documento JSON `portal_config.v1`, uno por
proyecto**, validado contra un esquema en codigo con rechazo duro. Todo elemento
de marca que se decida aqui tiene que caber dentro de ese documento y sobrevivir
esa validacion; no hay tabla de marca aparte ni columnas tipadas donde alojarlo.

Dos consecuencias que acotan el alcance de este ticket:

- la marca **no se versiona**. El documento solo lleva un contador de revision,
  asi que no se puede reconstruir como se veia el portal en una publicacion
  pasada. Si la marca necesitara esa reconstruibilidad —por ejemplo para que un
  informe entregado a un cliente siga viendose igual—, eso redibuja el corte MVP
  del modelo de datos y hay que decirlo aqui explicitamente;
- editar la configuracion `active` la cambia **en vivo**, sin borrador. Un
  cambio de logo o de paleta aparece de inmediato en el portal de todos los
  clientes del proyecto.

## Restriccion confirmada por el contrato del payload

**Contrato del payload de las superficies configuradas** cierra el sobre por el
que la marca tendria que viajar:

- del proyecto sale **unicamente `name`**. No hay campo generico de metadatos de
  proyecto por donde un logo, una paleta o un nombre visible puedan colarse sin
  declararse. Todo elemento de marca que se decida aqui tiene que aparecer
  explicitamente en `portal_config.v1` **y** como campo nombrado del sobre del
  portal, o no llega al navegador;
- eso convierte el alcance de este ticket en una lista finita y revisable. Si la
  lista crece despues, crece el sobre: no hay atajo;
- un logo obliga ademas a decidir donde vive el archivo. El sobre lleva URLs de
  descarga solo para artefactos aprobados de la publicacion, servidos por una
  ruta que valida la raiz de artefactos. Un logo no es un artefacto de corrida,
  asi que necesita su propio camino, y ese camino es parte de esta decision.

## Restriccion confirmada por la navegacion

**Navegacion y aterrizaje por perfil** le dio al portal un **layout propio**: tres
raices hermanas que no comparten header, asi que el portal ya no cuelga del shell
"BESS Workspace" del analista. Eso es precisamente lo que vuelve posible una marca
por proyecto —con header compartido la marca seria global o no existiria—, y
convierte a este ticket en quien llena ese layout. Tres consecuencias:

- **Un usuario con `operate` no aterriza en el portal.** La regla de
  `landing_path` hace que `operate` le gane a `portal_view`, de modo que quien
  tiene ambas capacidades ve primero el layout de la consola. Hay que decidir aqui
  si la marca del proyecto es **exclusiva del portal** o si el layout minimo de la
  consola tambien la lleva. La respuesta por defecto, coherente con el corte MVP,
  es exclusiva del portal: la consola es superficie de trabajo, no de entrega.
- **El archivo del logo se sirve bajo `/api/`, no bajo la ruta SPA.** El prefijo
  `/react/*` esta exento del gate de rol (`app/main.py:636-638`): sirve el shell,
  no datos, y no autoriza nada. El camino propio que este ticket tiene que definir
  para el logo es un endpoint de API con su propia comprobacion de acceso, igual
  que cualquier otra superficie nueva.
- **La ruta sigue llamandose `/client`.** No se renombro a `/portal` pese a que el
  rol pasa a `external` y la capacidad se llama `portal_view`; es deuda de nombres
  asumida. La marca que se decida aqui no depende del nombre de la ruta.

## Resolucion

Decidido el 2026-08-21. El usuario delego las decisiones con una instruccion
permanente para este ticket: **tomar la recomendacion en cada bifurcacion, con
sesgo de MVP** —lo basico bien resuelto, sin funcionalidad de mas—. Cada corte
de alcance de mas abajo se tomo bajo ese criterio, no por falta de tiempo.

### Hechos del codigo que fijaron la respuesta

- **Hoy no existe marca de ningun tipo, y la del producto no es un archivo sino
  texto.** `find -iname "*logo*"` sobre el repo vuelve vacio. La marca del
  producto son dos cadenas: un brand mark con la letra `Z` en un `<span>` mas
  "BESS Workspace" (`frontend/src/App.tsx:229-233`), y el `<title>` hardcodeado
  (`frontend/index.html:7`). Esto vuelve **no neutra** la opcion "que el portal
  use siempre la marca del producto": no existe tal marca lista para reusar; lo
  que existe es el header del analista, y ponerlo en el informe del cliente es
  exactamente la fuga de vocabulario interno que el cascaron del portal se
  comprometio a no cometer.
- **El sistema nunca acepto un binario.** Los tres `UploadFile` que existen
  (`app/main.py:1525`, `:2027`, `:2301`) hacen todos lo mismo:
  `(await file.read()).decode("utf-8")` y guardan texto. No hay almacenamiento
  de blobs, ni validacion de mime, ni tope de tamaño en ninguna parte. Un logo
  es el **primer binario del sistema**, y eso convierte una decision de
  decoracion en una de infraestructura.
- **La base es dual sqlite/postgres** (`app/database.py:165`) y los artefactos
  viven en un **root de filesystem** validado con `artifact_path_is_safe`
  (`app/main.py:725`). Un logo tiene que elegir entre esos dos mundos; no hay
  tercero.
- **El portal hoy muestra `project.name` como `h1` y `project.description`
  debajo** (`frontend/src/ClientPortal.tsx:278-279`), y el sobre que fijo
  **Contrato del payload de las superficies configuradas** solo deja pasar
  `name`.

### 1. Hay marca por proyecto, y es una lista de dos campos

La configuracion admite marca propia por proyecto: **nombre visible** y **logo**.
Nada mas. No es "personalizacion": es una lista finita, revisable y cerrada, y
crecerla despues crece el sobre, como advirtio el contrato del payload.

Lo que la hace posible es el layout propio que le dio **Navegacion y aterrizaje
por perfil**: tres raices que no comparten header. Ese layout hoy esta vacio de
identidad, y este ticket es quien lo llena.

### 2. Nombre visible: un campo, no dos

`display_name` reemplaza a `project.name` en el encabezado del portal.

Se descarta el par "nombre visible + nombre del cliente". El segundo campo no
tiene trabajo propio: si el informe es para el cliente, el nombre visible **ya
es** el que el cliente reconoce. Dos campos obligan a decidir cual gana en el
header, y eso es complejidad sin beneficio. El nombre del cliente, si hace
falta registrarlo, es dato administrativo del proyecto y no viaja al portal.

### 3. Logo: un slot, PNG/JPEG, bytes en la base, endpoint propio bajo `/api/`

- **Un solo slot.** Sin co-branding, sin logo secundario, sin variante para
  fondo oscuro.
- **PNG/JPEG unicamente.** Excluir SVG **elimina de raiz la rama de XSS** —un
  SVG servido inline es ejecutable— por el precio de una allowlist de dos
  valores. Es el mejor corte por peso de todo este ticket.
- **Tope de 256 KB**, rechazo duro al subir. Las dimensiones **no se validan**:
  el alto lo acota el CSS del encabezado. Un validador de dimensiones seria
  precisamente el linter que **Superficie del ingeniero para consolas
  bloqueadas** ya decidio no construir.
- **Los bytes viven en columnas de `portal_configurations`** —`logo_bytes` y
  `logo_media_type`—, no en el documento JSON. Ver el punto 8: es una enmienda
  declarada al modelo de datos, no un descuido.
- **Se sirve por un endpoint bajo `/api/`** con el mismo control de acceso que
  el resto del portal (`require_client_project_access`). Esto es obligatorio, no
  preferencia: el prefijo `/react/*` esta **exento** del gate de rol
  (`app/main.py:636-638`), asi que un logo colgado ahi seria publico.
- **Validador de cache: `ETag` derivado del contador de revision**, con
  `Cache-Control: private, must-revalidate`. Como la edicion es en vivo (punto
  7), un logo cacheado sin validador quedaria viejo en el navegador del cliente.
  Subir un logo sube la revision.

Este es el unico punto del ticket donde un "no" tambien era defendible, dado que
es el primer binario del sistema. Se decidio que si porque **un informe
ejecutivo entregado a un tercero sin logo no esta marcado, esta solamente
renombrado**, y porque postergarlo no ahorra el trabajo: lo mueve. Lo caro nunca
fue el logo sino su version sin limites —SVG, multiples slots, dimensiones
libres—, y eso es lo que queda afuera.

### 4. Titulo del documento por proyecto; favicon no

El `<title>` hoy dice `BESS Workspace` hardcodeado, y en un informe entregado a
un cliente es el mismo vocabulario interno que el punto 1 rechaza. En las rutas
del portal el titulo del documento pasa a ser el `display_name`.

**Favicon por proyecto queda fuera**: seria un segundo binario, con su propio
formato, su propia ruta de servido y su propio tope, para un valor marginal.

### 5. Fallback explicito: la marca del producto nunca aparece en el portal

- Sin `display_name` configurado —o sin configuracion de portal—, el portal
  muestra `project.name`.
- Sin logo, el portal **no muestra ninguno**. En particular **no cae en el brand
  mark `Z`** del header del analista.

Es la regla de marca con sabor fail-closed: ante configuracion ausente el portal
degrada a lo neutro, nunca a lo interno.

### 6. La marca la edita el ingeniero, no el operador

Mismo endpoint de configuracion de portal, mismo contador de revision, misma
auditoria (`updated_at`/`updated_by`) que el resto de `portal_config.v1`. El
`operate` del operador esta acotado a la configuracion activa y a la edicion de
series, segun **Rol y permisos del operador**; la marca no entra ahi.

### 7. Los dos recortes asumidos, dichos en voz alta

- **La marca no se versiona.** Un informe entregado hace tres meses y reabierto
  hoy se ve con la marca de hoy. **No se redibuja el corte MVP del modelo de
  datos**, y la razon es sustantiva, no de esfuerzo: los numeros del informe si
  son reconstruibles porque viven en el snapshot de la corrida; el logo del
  encabezado **no es un hecho sobre la corrida**. Cambiar el envase entero por
  decoracion es el trade equivocado.
- **La edicion es en vivo, sin borrador.** Cambiar logo o nombre lo cambia de
  inmediato para todos los usuarios cliente del proyecto. Mitigacion suficiente:
  el preview del analista ya usa el mismo constructor del sobre, asi que el
  ingeniero puede mirar el resultado antes de que lo vea un cliente.

### 8. Enmiendas declaradas a dos tickets ya cerrados

Ninguna es silenciosa; ambas tienen que viajar al spec consolidado.

- **Al modelo de datos**: el preambulo de este ticket asumia que *todo* elemento
  de marca cabria dentro de `portal_config.v1`. **Un binario no cabe.** Meterlo
  como data URI en base64 lo haria viajar entero en cada lectura del portal y
  atravesar la validacion de esquema en cada guardado. Por eso el documento JSON
  lleva **solo `display_name`**, y los bytes del logo van en dos columnas de
  `portal_configurations`. Es la excepcion unica a la regla "en columnas queda
  solo lo consultable", y se declara como tal.
- **Al contrato del payload**: el sobre del portal deja de llevar
  `project { name }` y pasa a llevar **`branding { display_name, logo_url }`**,
  con el fallback del punto 5 **ya resuelto en el backend**. Se sigue el mismo
  patron que `landing_path` en **Navegacion y aterrizaje por perfil**: la regla
  vive una sola vez en el servidor, no como logica de cliente. Mandar los dos
  nombres habria creado un segundo nombre capaz de contradecir al primero.

### 9. Fuera de alcance de este ticket

- **Colores configurables.** Una paleta por proyecto no es un campo, es una
  superficie: toca cada color de grafico, cada color de estado y el contraste de
  todo. Y como ya se decidio que **no hay linter semantico**, nada atajaria una
  paleta ilegible antes de que la vea el cliente. Nombre y logo dan identidad;
  los colores dan riesgo.
- **Dominio propio y white-label.** El portal es "el informe de este proyecto",
  no "un producto del cliente".
- **Marca en la consola de operador.** El layout minimo de la consola queda como
  lo dejo **Navegacion y aterrizaje por perfil**: la consola es superficie de
  trabajo, no de entrega.
- **Favicon por proyecto**, por el punto 4.
- **Tema oscuro, tipografia configurable y plantillas de portada.**

### Lo que este ticket destapo

- **La marca del producto no es un activo, es texto en el header del analista**
  (`Z` + "BESS Workspace"). Eso significa que "usar la marca del producto" nunca
  fue la opcion conservadora: era exponer el shell interno en la superficie de
  entrega.
- **El logo es el primer binario del sistema.** No hay precedente de
  almacenamiento, mime ni tope de tamaño que copiar, asi que el corte PNG/JPEG
  con tope fijo no es cautela sino la definicion misma del alcance.
- **`project.description` se cae del portal** y nadie lo habia notado: hoy se
  muestra (`ClientPortal.tsx:279`) y el sobre nuevo no la deja pasar. Se
  registra como **regresion consciente**, no como omision: es texto interno del
  analista, no copy para el cliente, y la publicacion ya tiene `comment` para
  dar contexto.
