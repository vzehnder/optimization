---
id: 12
title: "Navegacion y aterrizaje por perfil"
map: capa-de-configuracion
label: wayfinder:grilling
status: closed
assignee: vzehnder
blocked_by: [02, 03, 04]
---

## Question

¿Como conviven la aplicacion de analista, la consola de operador y el portal
cliente dentro de la navegacion global, y a que ruta aterriza cada perfil al
iniciar sesion?

Los dos cascarones ya fijan sus superficies. Esta decision debe precisar:

- si cada perfil tiene una ruta raiz y navegacion propias;
- si `admin`/`analyst` pueden entrar a las tres superficies y como cambian entre
  ellas sin confundir la vista operativa con la configuracion;
- que ocurre con usuarios que tienen mas de un perfil utilizable;
- como se reemplazan las comprobaciones React repetidas de `isClient` por una
  politica de rutas coherente con **Rol y permisos del operador**;
- que breadcrumbs y selector de proyecto conserva cada superficie.

## Restriccion confirmada por el modelo de datos

Las consolas son **N por proyecto**, colgando del caso; el portal es **uno por
proyecto**. La navegacion no puede tratarlos igual:

- un usuario `external` con `operate` en un proyecto con varias consolas
  necesita elegir cual abrir, mientras que con `portal_view` no hay nada que
  elegir. Si tiene exactamente una consola, el aterrizaje deberia saltarse la
  eleccion en vez de mostrar una lista de un elemento;
- las consolas en estado `draft` no existen para un usuario `external`: no
  aparecen en su navegacion y no son direccionables por URL;
- `admin` y `analyst` entran a las consolas con su identidad real para probarlas
  —lo fijo **Rol y permisos del operador**—, asi que la misma ruta sirve a dos
  perfiles con navegacion de origen distinta.

## Restriccion confirmada por el contrato del payload

**Contrato del payload de las superficies configuradas** fija que la navegacion
tambien es superficie configurada, no una excepcion:

- **el listado de consolas de un proyecto es un sobre mas**, sujeto a la misma
  allowlist escrita a mano. Por consola sale nombre, descripcion, quien la
  preparo y cuando se actualizo; no salen `case_id`, la variante propia, la
  copia operativa ni el `revision` de la configuracion;
- las consolas en `draft` **no existen en ese sobre**. La navegacion no las
  omite en el frontend: el backend no las incluye;
- `console.id` si cruza, porque la ruta lo necesita. Es una clave subrogada de
  un objeto de configuracion, no del linaje, y es el unico identificador
  direccionable que este mapa deja del lado del operador;
- el aterrizaje que se decida aqui no puede apoyarse en campos que el sobre no
  lleva. Si el salto directo cuando hay exactamente una consola necesita algun
  dato mas, hay que declararlo como campo del sobre, no leerlo de otra ruta.

## Restriccion confirmada por la superficie del ingeniero

**Superficie del ingeniero para consolas bloqueadas** agrega una superficie mas
al inventario que este ticket tiene que rutear, y decide de antemano que no es
una raiz:

- **la lista de consolas del ingeniero vive dentro del workspace de escenario**,
  junto a las variantes, porque ahi ya viven el caso y la variante de la que la
  consola clona la suya. No es una ruta de nivel superior y no compite con las
  tres superficies que este ticket ordena. Si la navegacion que se decida aqui
  la mueve a nivel de proyecto, hay que decirlo explicitamente y asumir que
  agregar consolas pasa a ser una agregacion sobre escenarios;
- **son dos vistas distintas del mismo objeto.** El ingeniero abre una consola
  desde su lista para configurarla o desbloquearla; `admin`/`analyst` tambien
  entran a la consola **con su identidad real para probarla**, que es lo que
  fijo **Rol y permisos del operador**. La navegacion tiene que distinguir esos
  dos destinos sin confundirlos: configurar no es operar;
- **la ruta de detalle de corrida `runs/:runId` queda como destino compartido.**
  El `reference` que el operador recibe cuando una corrida falla apunta ahi, y
  es superficie exclusiva de analista. Un `external` no puede alcanzarla por
  URL, aunque tenga el numero;
- el flag `esperando_desde` y el estado de bloqueo son **columnas de la lista**,
  no un destino navegable propio. No hay bandeja de avisos que rutear.

## Resolucion

Decidido el 2026-08-21. El usuario delego las decisiones con una instruccion
permanente para este ticket: **tomar la recomendacion en cada bifurcacion, con
sesgo de MVP** —lo basico bien resuelto, sin funcionalidad de mas—. Cada corte
de alcance de mas abajo se tomo bajo ese criterio, no por falta de tiempo.

### Hechos del codigo que fijaron la respuesta

Tres hallazgos verificados antes de decidir, porque contradicen lo que el ticket
suponia:

- **La regla de aterrizaje ya existe y esta escrita tres veces.**
  `react_authenticated_landing_path` (`app/main.py:589`) la calcula para la SPA y
  viaja como `redirect_path` en la respuesta de login (`app/main.py:908` y
  `:936`); una variante legacy vive en `app/main.py:585`; y
  `landingRoute()` (`frontend/src/App.tsx:66`) la repite en el cliente para la
  ruta `index`. Son tres implementaciones de la misma regla que hoy coinciden
  por casualidad, con un solo `if` cada una.
- **El nombre de la ruta SPA no autoriza nada.** La SPA se monta bajo `/react/*`
  y ese prefijo esta **exento** del gate de rol (`app/main.py:636-638`): sirve el
  shell, no datos. Las ramas `/client` y `/api/client` del middleware
  (`app/main.py:656-667`) gatean la superficie legacy server-rendered, no las
  rutas de React. Toda la autorizacion real vive en `/api/*`.
- **El gate compartido cierra por defecto.** La rama final de
  `require_authenticated_app_boundary` es `require_internal`
  (`app/main.py:668-671`), asi que **cualquier prefijo de API nuevo que no se
  liste explicitamente queda negado a un `external`**. Olvidar registrar los
  endpoints de la consola los deja inaccesibles para el operador, no abiertos.
- Ademas, la distincion 403/404 ya tiene precedente:
  `require_client_project_access` (`app/main.py:533-541`) devuelve 403 ante
  `PermissionError` y 404 ante `KeyError`.

### 1. Tres raices hermanas, un layout por raiz

La navegacion global se parte en tres raices que no comparten header:

| Raiz | Rutas | Perfil |
| --- | --- | --- |
| Analista | `/projects/*`, `/scenarios/*`, `/runs/*`, `/scenario-versions/*`, `/publications/*`, `/system`, `/admin/users` | `admin`, `analyst` |
| Consola | `/console`, `/console/:consoleId` | `external`+`operate`, y `admin`/`analyst` probando |
| Portal | `/client/*` | `external`+`portal_view` |

Se descarta el shell unico de hoy: el header actual —"BESS Workspace", brand
mark `Z`, enlaces a Sistema y Admin— ya es un shell de analista disfrazado de
global, y **Alcance de marca del portal cliente** puede ponerle marca por
proyecto al portal, lo que lo volveria incompatible. Se descarta tambien colgar
la consola del portal: `portal_view` y `operate` son capacidades independientes,
asi que quien solo tiene `operate` no puede entrar por una casa llamada portal.

**Corte MVP**: el layout de analista queda **exactamente como esta hoy**. El de
la consola es minimo —identidad publica del plan, usuario, salir—. El del portal
lo fija **Alcance de marca del portal cliente**.

### 2. La consola es una ruta plana: `/console/:consoleId`

No `/projects/:projectId/console/:consoleId`. El sobre del listado lleva
`console.id` y nada del linaje, asi que una ruta con `projectId` obligaria a
validar coherencia entre dos identificadores y a que el frontend cargue algo que
el sobre no le entrega. `console.id` es clave subrogada global y se basta sola.

`/console` es la **lista de consolas del usuario, cruzada por proyecto** —no una
lista por proyecto—: un operador con consolas en dos proyectos necesita verlas
juntas. Eso amplia lo que fijo **Contrato del payload de las superficies
configuradas**, que describio el listado como sobre por proyecto: se resuelve
con el mismo sobre mas `project.name` por fila, declarado como campo, nunca
leido de otra ruta. Sigue sin cruzar `case_id`, variante, copia operativa ni
`revision`.

### 3. Configurar no es operar: dos rutas para el mismo objeto

- **Operar o probar**: `/console/:consoleId`, layout de consola. Es la misma ruta
  para el `external` con `operate` y para el interno que la prueba con su
  identidad real, como fijo **Rol y permisos del operador**.
- **Configurar**: `/scenarios/:scenarioId/consoles/:consoleId`, layout de
  analista, dentro del workspace de escenario donde **Superficie del ingeniero
  para consolas bloqueadas** puso la lista. No sube a nivel de proyecto.

Cuando un interno esta en `/console/:consoleId`, el layout de consola muestra
una **franja delgada de contexto** —"Estas probando esta consola"— con enlace de
vuelta a su configuracion. Es la unica concesion al riesgo de confundir las dos
vistas.

**Corte MVP**: sin modo de impersonacion, sin conmutador de perfil, sin banner
de simulacion. Una franja y un enlace.

### 4. El aterrizaje es un campo del sobre de identidad

Con tres perfiles y capacidades por proyecto, las tres copias de la regla de
aterrizaje divergen. Se unifica: **`/api/auth/me` y la respuesta de login
devuelven `landing_path`**, calculado en un unico lugar del backend.
`landingRoute()` se borra de `App.tsx`; la ruta `index` redirige a
`user.landing_path` y el frontend no vuelve a derivar ruta desde el rol.

Esto satisface por construccion la restriccion de **Contrato del payload**: si
el salto directo necesita un dato mas, se declara como campo del sobre.

Regla unica de `landing_path`, en orden:

1. si hay un `next` seguro y permitido para el perfil, gana —el deep link tras
   login ya existe y se conserva—;
2. `admin` / `analyst` -> `/projects`;
3. `external` con `operate` en algun proyecto: **exactamente una** consola
   visible -> `/console/:id`; cero o varias -> `/console`;
4. `external` sin `operate` -> `/client`.

**`operate` gana sobre `portal_view`** cuando el usuario tiene ambas: quien puede
ejecutar viene a trabajar, y el informe queda a un clic en la nav.

El salto directo con una sola consola vive **solo** dentro de `landing_path`. La
ruta `/console` siempre renderiza la lista y **nunca** redirige, aunque haya un
solo elemento. Asi no existen dos comportamientos para la misma URL ni la trampa
del boton atras que devuelve al mismo sitio.

### 5. Tres guardas reemplazan los diecinueve `isClient`

Hoy `isClient ? <ForbiddenView /> : <X />` aparece **19 veces** en
`frontend/src/App.tsx:266-369`. La guarda pasa a ser **por raiz, no por ruta**:
cada uno de los tres grupos se envuelve una sola vez.

- Analista: `role in {admin, analyst}`.
- Consola: `role in {admin, analyst}` **o** el usuario tiene `operate` en algun
  proyecto.
- Portal: el usuario tiene `portal_view`.

Dentro de una raiz no hay guardas por ruta. La unica excepcion es
`/admin/users`, que conserva su chequeo propio de `admin` porque ya esta escrito
asi y es un requisito estricto dentro de la raiz de analista.

La guarda de consola **no** verifica el acceso a la consola concreta: eso lo
resuelve el backend al servir el sobre. Principio que queda fijado aqui: **las
guardas del frontend son experiencia de usuario, la frontera es el backend.** El
frontend nunca decide si un `consoleId` es alcanzable.

**Corte MVP**: no se construye tabla declarativa de rutas ni motor de politicas.
Tres wrappers y la excepcion que ya existia.

### 6. Politica 403 / 404

Hoy `ForbiddenView` devuelve 403 y con eso revela que la ruta existe: un cliente
que escribe `/runs/7` confirma que esa corrida es direccionable.

- **`external` fuera de su superficie -> 404** (`NotFoundView`), siempre. Para un
  externo, lo que no le pertenece no existe.
- **Interno sin permiso -> 403** (`ForbiddenView`). De hecho solo aplica a
  `/admin/users` visitado por un `analyst`.

Consecuencias que este ticket confirma en vez de dejar implicitas:

- `runs/:runId` es **404 para un `external`** aunque tenga el numero de
  referencia que la consola le entrego al fallar una corrida. Coincide con lo que
  fijo **Superficie del ingeniero para consolas bloqueadas**: ese `reference` es
  para escalarlo a un humano, no para navegar.
- una consola en `draft` da **404** a un `external`: no aparece en el sobre y
  tampoco se sirve por id.

### 7. Navegacion dentro de cada raiz

- **Analista**: la de hoy, sin cambios. **No** se agrega una entrada "Consolas"
  al nav global, porque la lista del ingeniero vive dentro del workspace de
  escenario.
- **Consola**: sin nav de secciones —es una pantalla unica—. Aparece un enlace
  "Mis consolas" solo si el usuario tiene mas de una, y un enlace "Informes" solo
  si tiene `portal_view`.
- **Portal**: como hoy, mas lo que decida **Alcance de marca del portal
  cliente**.

### 8. Breadcrumbs y selector de proyecto

- **Analista**: se conserva lo actual, sin agregados.
- **Consola**: **sin breadcrumbs y sin selector de proyecto.** Un breadcrumb
  tendria que nombrar proyecto y caso, que es exactamente la jerarquia que la
  consola existe para esconder. La identidad publica del plan, que ya encabeza la
  mesa de trabajo por **Forma del cascaron de la consola de operador**, cumple la
  funcion de ubicar al operador. La vuelta es el enlace "Mis consolas".
- **Portal**: se conserva el camino plano actual (Portal -> Proyecto ->
  Publicacion), que no expone nada interno.

**No hay selector global de proyecto en ninguna superficie**: al proyecto se
entra, no se conmuta. Es corte MVP explicito.

### 9. Fuera de alcance de este ticket

- **No se renombra `/client` a `/portal`** pese a que el rol pasa a `external` y
  la capacidad se llama `portal_view`. Es deuda de nombres con cero
  funcionalidad; renombrar obliga a tocar la rama legacy del middleware y los
  redirects de `legacy_path_to_react_path`.
- **No hay pagina selectora de perfil** al iniciar sesion. `landing_path`
  resuelve y la nav ofrece el resto.
- **No se recuerda la ultima superficie visitada** entre sesiones.
- **No se toca** el mount `/react/*` ni la rama `/client` del middleware legacy.

### Lo que este ticket destapo

- La regla de aterrizaje esta **triplicada** en el codigo de hoy (dos copias
  backend, una frontend). Con capacidades por proyecto eso deja de ser
  sostenible, y por eso `landing_path` pasa a ser campo del sobre de identidad en
  vez de logica de cliente.
- El listado que la navegacion necesita es **cruzado por proyecto**, mientras que
  **Contrato del payload de las superficies configuradas** lo describio por
  proyecto. Se amplia con `project.name` por fila, declarado en el sobre.
- `ForbiddenView` deja de ser la respuesta por defecto: para un `external` la
  respuesta correcta es 404, y 403 queda solo para internos.
