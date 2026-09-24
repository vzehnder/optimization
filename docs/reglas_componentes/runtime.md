# Operación y verificación de REG-001 a REG-008

REG-001 guarda borradores y calcula un máximo escalar de caudal. REG-002 incorpora
publicación, aplicaciones a variantes y restricciones afines en el optimizador
hidráulico v3. REG-003 calcula límites horarios desde entradas canónicas fijadas.
REG-004 relaciona unidades, plantas y embalses del mismo modelo.
REG-005 añade rampas y referencias a períodos anteriores con política inicial explícita.
REG-006 integra potencia y caudal por horizonte o día civil, con zona IANA y
aceptación explícita de días parciales.
REG-007 publica salidas numéricas completas como series derivadas y permite
regenerarlas explícitamente conservando revisiones, propietarios y consumidores.
REG-008 ofrece una biblioteca del proyecto con revisiones compartidas e instancias
independientes por unidad y variante, comparación y clonación con remapeo explícito.
Las revisiones `sealed_preview` son copias inmutables
de pruebas; el estado de la definición editable sigue siendo `draft`.

## Contrato del primer SDK

```python
def construir(ctx):
    return ctx.parametros.capacidad * ctx.parametros.disponibilidad
```

`capacidad` declara tipo `number`, unidad canónica `m3_per_s` y valor 80;
`disponibilidad` declara `number`, unidad `dimensionless`, valor 0.75 y rango
0–1. El resultado es 60 m³/s. El SDK `reg-006.1` conserva la unidad en la
multiplicación, acepta funciones, bucles y comprensiones, y exige una cantidad
finita de caudal como retorno. El contexto expone identidad del objeto y
parámetros inmutables. La prueba escalar de REG-001 se conserva.

## Restricciones de caudal (REG-002)

Publicar crea una revisión inmutable. Seleccionar variante y rango UTC completo
habilita la compilación simbólica; no se muestrean períodos:

```python
def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion("maximo", t,
            ctx.objeto.caudal[t] <= ctx.parametros.capacidad * ctx.parametros.disponibilidad)
```

Con capacidad 5 m³/s y disponibilidad 1, cada fila limita el caudal a 5 m³/s.
Los períodos usan índices desde cero en Python/IR; la UI los presenta desde uno.
Se admiten `<=`, `>=`, `==`, suma/resta y multiplicación/división por datos
adimensionales conocidos. Las condiciones Python solo pueden usar datos conocidos:
una decisión simbólica como booleano, los productos de decisiones y referencias
a otros períodos sin política temporal u objetos sin alias se rechazan. `construir` no devuelve un escalar en este
modo: emite filas con nombre, unidad, período y línea de origen.

La UI muestra todas las filas paginadas. Aplicar exige motivo y fija revisión,
objeto, parámetros, variante y horizonte; cero filas requiere aceptación explícita.
Para reemplazar una aplicación, desactivar con motivo, volver a publicar/probar
y aplicar. Se conservan las aplicaciones anteriores y sus actores/motivos. Editar
un borrador no cambia pins; una publicación nueva, cambio de modelo, entradas,
rango o runtime exige probar y aplicar otra vez. Se puede probar una publicación
histórica explícita por API para conservar un pin con un motivo nuevo.

El IR `affine_flow.v1` se valida en Python y nuevamente en Julia. El motor declara
esa capacidad en su validación; si no la declara se bloquea antes de crear la
corrida. Los límites se suman a capacidades y balances físicos. La validación
rechaza contradicciones simples de cotas; la factibilidad global la determina
el solver.

Materializar congela código, parámetros, fuentes, grilla, runtime e IR con hashes.
Julia valida fuera de la transacción; al confirmar se comprueban otra vez contexto,
publicaciones y aplicaciones. SQLite usa una transacción de escritura y PostgreSQL
una vista consistente con conflictos reportados como HTTP 409. Versión, corrida y
clave `X-Request-Id` se confirman juntas. Repetir la clave devuelve la misma corrida,
incluso tras desactivar la aplicación, sin volver a ejecutar Python. La revisión y
los parámetros aparecen en la pantalla de corrida.

Los productores que aún no soportan reglas bloquean con motivo: consolas y
programaciones requieren REG-014. La ejecución directa de una versión sin reglas
también bloquea si el caso tiene aplicaciones activas. Deshabilitar la función
no permite ejecutar ignorando sus restricciones.

Esta capacidad inicial no admite importaciones, atributos privados ni clases
del usuario. Incluye utilidades deterministas de Python (`range`, `len`, `sum`,
`min`, `max`, `abs`, `enumerate`, `zip`, conversiones y `print` acotado), sujetas
a los tipos que soporta este SDK. No permite paquetes arbitrarios. El filtro
de sintaxis complementa el contenedor; no constituye la frontera de aislamiento.

## Entradas y límites horarios (REG-003)

Cada puerto declara alias, objeto, dimensión, semántica y rol, y fija señal,
revisión sellada y hash. El selector distingue catálogo y series específicas de
la unidad; la API comprueba de nuevo propiedad y compatibilidad. Los roles
`rule_inflow` y `rule_availability` admiten respectivamente afluente en `m3_per_s`
y disponibilidad `dimensionless` entre 0 y 1. El catálogo añade la semántica
`availability_factor` por clave, sin reutilizar IDs de tipos personalizados.

```python
def construir(ctx):
    for t in ctx.periodos:
        minimo = ctx.entradas.afluente[t] * ctx.parametros.fraccion
        maximo = ctx.parametros.capacidad * ctx.entradas.disponibilidad[t]
        ctx.restriccion("minimo", t, ctx.objeto.caudal[t] >= minimo)
        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= maximo)
        ctx.salida("minimo", t, minimo)
        ctx.salida("maximo", t, maximo)
```

Los valores conocidos permiten cálculos Python no lineales; las decisiones
siguen sujetas al contrato afín. Solo se aceptan medias con inicio de intervalo
y unidad canónica compatible. La grilla completa debe coincidir en instantes y
duraciones: faltantes, duplicados y valores inválidos bloquean con alias/período.
Las zonas distintas de UTC necesitan offsets explícitos; no se completa ni
transforma una serie durante la compilación.

La preview presenta límites efectivos y salidas numéricas con unidades, tabla
y gráficos de 20 períodos por página. La paginación solo afecta la presentación:
se valida el horizonte completo. Se detectan cruces de mínimo/máximo contra las
filas de la regla y los límites físicos conocidos antes del solve; esto no
sustituye la comprobación de factibilidad global de Julia. `ctx.salida` conserva
cálculos en la preview y snapshot; REG-007 permite publicarlos como series derivadas.

Publicar una entrada nueva invalida la evidencia anterior y bloquea la corrida,
sin mover el pin. Para conservar una revisión antigua: **Probar revisión fijada**,
desactivar la aplicación anterior con motivo y aplicar la nueva evidencia con
motivo. Para usar otra revisión, cambiar la selección, guardar, publicar y probar.
Se vuelven a comprobar las entradas al aplicar y antes de confirmar la corrida,
incluyendo cambios ocurridos durante la validación Julia. El snapshot conserva
valores, identidad/hash de las fuentes, compatibilidad, parámetros, salidas e IR;
una publicación posterior no modifica corridas guardadas.

## Relaciones entre objetos hidráulicos (REG-004)

Desde la unidad, «Objetos y variables del modelo» permite declarar alias hacia
unidades, plantas y embalses activos del mismo caso. `ctx.objetos.<alias>` conserva
la identidad estable; la selección, guardado, prueba, aplicación y corrida
vuelven a comprobar pertenencia y membresía. No basta compartir proyecto.

| Objeto | Variables | Unidades |
| --- | --- | --- |
| Unidad | `caudal`, `potencia` | `m3_per_s`, `mw` |
| Planta | `potencia`, expandida a sus unidades activas | `mw` |
| Embalse | `almacenamiento` al final del intervalo, `vertimiento` | `hm3`, `m3_per_s` |

No se ofrecen caudal de tramo ni cota como decisiones. La dimensión `volume` y
la unidad `hm3` se incorporan al catálogo existente por clave, sin reservar IDs.
Las sumas/restas y comparaciones exigen la misma unidad; los coeficientes son
datos adimensionales conocidos. Se conservan los rechazos a productos de
variables y condiciones simbólicas; las referencias anteriores requieren REG-005.

```python
def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion("generacion", t,
            ctx.objeto.potencia[t] + ctx.objetos.segunda.potencia[t]
            <= ctx.parametros.limite)
        ctx.restriccion("reserva", t,
            ctx.objetos.agua.almacenamiento[t] >= ctx.parametros.reserva)
```

`limite` puede ser 10 `mw` y `reserva` una cantidad en `hm3`. Usar
`ctx.objetos.central.potencia[t]` emite los términos de todas las unidades de la
planta; Julia no crea otra variable física. La preview identifica cada objeto y
variable de los términos expandidos. Una regla de potencia no muestra curvas de
caudal que no haya emitido.

Los parámetros pueden declarar `object_id`; los puertos se seleccionan desde el
objeto actual o un alias explícito. Los permisos, propiedad y compatibilidad se
comprueban con el objeto de ese puerto. Las series específicas conservan su dueño.
Los roles disponibles siguen siendo los autorizados por la matriz TS-7: declarar
un alias no añade compatibilidades nuevas para plantas o embalses.

Las relaciones ampliadas usan `affine_hydraulic.v1`; el motor sigue aceptando
`affine_flow.v1`. La corrida conserva objetos, alias, miembros de planta, código,
entradas, parámetros e IR. Todas las aplicaciones activas se intersectan y sus
filas se distinguen por aplicación. Cambios de membresía o referencias ausentes
marcan la aplicación obsoleta y bloquean nuevas corridas; las históricas conservan
sus snapshots. Un motor sin la capacidad requerida no puede omitir las filas.

El SDK `reg-006.1` exige reconstruir la imagen y reiniciar el worker con su digest.
Las publicaciones/aplicaciones de un SDK anterior necesitan publicar, probar y
aplicar de nuevo antes de ejecutar; los datos históricos siguen legibles.

## Rampas y períodos anteriores (REG-005)

En «Referencias temporales y rampas», elegir **Omitir la primera comparación**
o **Usar condición inicial declarada**. La segunda exige un valor finito con
unidad y un instante ISO con `Z` u offset para cada variable recorrida. Los
valores no se rellenan automáticamente. El instante debe preceder al primer
inicio del horizonte. Una planta usa su valor agregado inicial y expande las
decisiones de cada período a las unidades de su snapshot.

```python
def construir(ctx):
    for paso in ctx.transiciones(ctx.objeto.potencia):
        diferencia = paso.actual - paso.anterior
        ctx.restriccion("subida", paso.periodo,
            diferencia <= ctx.parametros.subida * paso.horas)
        ctx.restriccion("bajada", paso.periodo,
            -diferencia <= ctx.parametros.bajada * paso.horas)
```

`subida` y `bajada` son parámetros `mw_per_h` (MW/h). Para caudal, usar
`ctx.objeto.caudal` y `m3_per_s_per_h` (m³/s por hora). La cantidad
`paso.horas` tiene unidad `h`; multiplicarla por la tasa conserva la dimensión
de la variable. No se permite comparar una rampa de caudal con potencia.

Cada paso expone `periodo` (índice desde cero), `actual`, `anterior`, `inicio`,
`inicio_anterior` y `horas`. Las horas son la distancia entre **inicios** en UTC,
no la duración del intervalo actual. La primera comparación utiliza el instante
inicial declarado o se omite visiblemente. Un horizonte de un período produce
una comparación inicial por dirección o cero filas; aplicar cero filas sigue
requiriendo aceptación expresa. También se permiten referencias directas como
`ctx.objeto.caudal[t - 1]` en períodos válidos, con política temporal declarada.
Ni las variables ni `ctx.periodos` aceptan índices negativos; no hay wraparound.
Una fila puede referenciar su período y los anteriores, nunca uno futuro.

El campo HTTP `temporal` se conserva en borrador, publicación, prueba,
aplicación y snapshot. Ejemplo de condición inicial (el ID debe ser el del objeto):

```json
{
  "first_period": "initial",
  "initial_values": [
    {"object_id": 7, "variable": "potencia", "value": 2,
     "unit": "mw", "timestamp": "2025-12-31T23:30:00Z"}
  ]
}
```

Para omitir: `{"first_period":"omit","initial_values":[]}`. Ausencia o `null`
conserva el modo sin referencias temporales. La capacidad nueva es
`affine_temporal.v1`: servidor y Julia distinguen términos por objeto, variable
y período, y el motor debe anunciarla antes de encolar. Los contratos previos
siguen exigiendo términos del mismo período. La preview presenta la política,
valores iniciales, cobertura, índices, instantes y distancias de cada comparación;
las rampas no se presentan como cotas horarias independientes. Los errores
conservan línea y período. Cambiar horizonte requiere nueva prueba y aplicación,
sin modificar snapshots anteriores.

Julia interpreta `Z` y offsets como UTC para resolver, y conserva las cadenas
originales de la grilla en el documento resuelto. El SDK `reg-006.1` requiere
reconstruir la imagen, fijar su digest y reiniciar el worker; las publicaciones
de SDK anteriores requieren publicar, probar y aplicar nuevamente.

## Presupuestos por ventana (REG-006)

En «Presupuestos de agua y energía», elegir **Horizonte completo** o **Días
civiles**, indicar una zona IANA y, si corresponde, aceptar explícitamente días
parciales. Esta política `windows` se guarda en el borrador, publicación,
aplicación, snapshot y lineage de la corrida. Cada regla tiene una política;
para combinar presupuestos diarios y de horizonte, aplicar dos reglas.

```python
def construir(ctx):
    for ventana in ctx.ventanas():
        agua = ventana.integral(ctx.objeto.caudal).a("hm3")
        ctx.restriccion("agua", ventana, agua <= ctx.parametros.agua)
```

`agua` declara unidad `hm3`. Sin `.a("hm3")`, la integral de caudal queda en
`m3`: cada término usa la duración en segundos. La conversión explícita inversa
es `.a("m3")`. Para energía, `ventana.integral(ctx.objeto.potencia)` produce
`mwh`, con coeficientes en horas. La suma de potencia o caudal sin duración no
es una integral y no se puede comparar con energía o volumen. Se pueden sumar
integrales de varios alias; la potencia de planta expande sus unidades y el
vertimiento de un embalse se integra como caudal. No se integra almacenamiento.

La ventana expone `inicio`, `fin`, `horas`, `periodos` y `parcial`. Los índices
son los mismos de la grilla UTC. Un día civil puede contener 23 o 25 horas,
incluidos cambios a medianoche. La agrupación usa
[ZoneInfo y datos IANA](https://docs.python.org/3/library/zoneinfo.html); Windows
requiere `tzdata`, declarado en `requirements.txt`. El contenedor usa los datos
incluidos en su imagen fijada por digest. Un solve consume las ventanas congeladas.

Los intervalos deben ser contiguos, positivos y coincidir con los bordes de día.
Una ventana parcial bloquea salvo `partial: "allow"`; esa aceptación conserva
el presupuesto completo. No se dividen intervalos ni se prorratean límites.
Los errores de ventanas vacías, unidades incompatibles o bordes desalineados
incluyen la línea y el período. Cambiar rango exige probar y aplicar de nuevo.

La preview muestra inicio/fin UTC, duración, cantidad de períodos y términos,
unidad, presupuesto efectivo y aceptación parcial. Las filas se paginan de 20
en 20 y las expresiones extensas muestran 20 términos por página; se compila y
valida siempre el horizonte completo.

`affine_budget.v1` conserva una ventana en cada fila de presupuesto y usa
coeficientes con unidad `h`, `s` o `hm3_per_m3_per_s` (hm³ por m³/s). Servidor y
Julia validan referencias y dimensiones; el servidor reconstruye las ventanas
con la política fijada y Julia verifica su correspondencia con la grilla y
duración. Las filas se añaden al mismo modelo físico y objetivo. El motor debe
declarar esta capacidad antes de encolar; no se pueden descartar sus restricciones.

## Runtime Linux compartido por desarrollo y CI

La imagen se construye únicamente con `runtime/component_rules/`, sin enviar
el repositorio completo como contexto. El Dockerfile fija CPython 3.12.14 por
digest. El SDK está incluido en la imagen y su digest final fija ambos.

```sh
docker build -t component-rules:reg-007 runtime/component_rules
export RULE_RUNTIME_IMAGE="$(docker image inspect component-rules:reg-007 --format '{{.Id}}')"
export RULE_RUNTIME_COMMAND='["docker"]'
export RULE_ENABLED_PROJECTS='*'
python -m app.rule_worker
```

Para producción, publicar la imagen en el registro de la organización y usar
`registro/imagen@sha256:...`; para una imagen local se admite el identificador
completo `sha256:...`. No se aceptan tags mutables como configuración del worker.
El worker verifica Linux, seccomp y disponibilidad de la imagen antes de
anunciarse. Debe usar la misma `DATABASE_URL` que FastAPI. En producción vive en
un host de ejecución separado; FastAPI no necesita el socket ni la CLI Docker.
El worker confiable sí necesita acceso a la base de trabajos y al runtime.

En Windows, Docker Desktop con contenedores Linux usa los mismos comandos,
con variables PowerShell:

```powershell
docker build -t component-rules:reg-007 runtime/component_rules
$env:RULE_RUNTIME_IMAGE = (docker image inspect component-rules:reg-007 --format '{{.Id}}').Trim()
$env:RULE_RUNTIME_COMMAND = '["docker"]'
$env:RULE_ENABLED_PROJECTS = '*'
.venv/Scripts/python.exe -m app.rule_worker
```

También se puede usar un Docker instalado en WSL configurando la lista de
argumentos, por ejemplo `["wsl","-d","Ubuntu","--","docker"]`. La CLI se
invoca sin shell. No hay ejecución alternativa en Windows ni dentro de FastAPI.

`RULE_ENABLED_PROJECTS` acepta `*` (predeterminado), IDs separados por comas o
la cadena vacía para deshabilitar pruebas, aplicaciones y corridas con reglas. Los borradores e historial
siguen siendo legibles. La autorización existente concede los proyectos a los
roles internos `analyst`/`admin`; la API verifica además la pertenencia del
objeto. Los externos no alcanzan estas rutas, aunque conozcan sus URLs.

## Publicar y regenerar series calculadas (REG-007)

Desde una revisión publicada, probar el horizonte completo y abrir **Publicar
serie calculada**. El recorrido tiene cuatro pasos: destino, salida y clasificación,
revisión de todos los intervalos e impacto con motivo obligatorio. El destino es
el catálogo del proyecto o una serie específica del objeto actual. La unidad
proviene del cálculo; solo se ofrecen semánticas compatibles y, para series
específicas, roles válidos del propietario. Los datos quedan clasificados como
`derived`, con intervalos UTC y convención `period_start`.

Ejemplo: declarar `capacidad` como número en `mw` con valor 20 y seleccionar una
entrada `disponibilidad` con semántica `availability_factor` y unidad
`dimensionless`:

```python
def construir(ctx):
    for t in ctx.periodos:
        ctx.salida("potencia", t,
                   ctx.parametros.capacidad * ctx.entradas.disponibilidad[t])
```

Publicar `potencia` con semántica `renewable_available_power`. Su revisión puede
seleccionarse en una renovable compatible mediante el recorrido canónico de
bindings. Una salida parcial o con variables de decisión no puede publicarse.
La creación no sustituye una fuente existente del mismo nombre.

Las rutas relativas a `/api/projects/{project}/linkable-objects/{object}/rules/{rule}` son:

- `GET /tests/{job}/series-options`: salidas completas, unidades, semánticas y roles.
- `POST /series-publications`: `job_id`, `output_name`, `name`, `series_key`,
  `semantic_type_key`, `unit_key`, `series_kind`, `intended_binding_role_key`
  (para serie específica) y `reason`.
- `GET /series-publications` y `GET /series-publications/{id}`: recibos,
  definición, lineage y vigencia de cada receta.
- `POST /series-publications/{id}/regenerations`: `job_id`,
  `expected_revision_id` y `reason`; conserva identidad, clasificación y propietario.

Ambos POST exigen sesión interna, CSRF e `Idempotency-Key`. Repetir la misma
solicitud devuelve su recibo; cambiar la intención con la misma clave devuelve
409. La escritura canónica, lineage, receta y recibo se confirman en una sola
transacción. La pausa operativa C6 y el interruptor del proyecto impiden nuevas
publicaciones. Una colisión concurrente exige reintentar; no quedan sets parciales.

La receta fija código, revisión de regla, SDK/imagen/runtime, parámetros,
referencias de inputs con revisiones/hash y valores, grilla, política temporal,
ventanas y hash de salida. Las dependencias enlazan revisiones canónicas y se
rechazan ciclos, incluidas dependencias históricas. Consultar no ejecuta Python.

Una nueva publicación de la regla o fuente marca la receta obsoleta con explicación.
Para regenerar: seleccionar o revalidar las entradas, publicar y probar la regla,
y confirmar **Regenerar** con motivo. Esta acción registra **una revisión nueva
incluso con valores idénticos**; es la excepción explícita de REG-007 al no-op
canónico habitual de republicación idéntica. Los bindings conservan sus pins y
quedan pendientes de revalidación; ninguna corrida histórica cambia. No hay
regeneración ni selección automática de revisiones.

## Límites y ciclo de vida

Cada trabajo recibe solo JSON por stdin. No hay bind mounts, red ni secretos
del host dentro del contenedor. Se ejecuta como UID/GID 65532, sin capacidades,
con `no-new-privileges`, seccomp predeterminado y raíz de solo lectura. `/tmp`
es privado, no ejecutable y está limitado a 16 MiB.

Límites: 1 CPU, 512 MiB sin swap adicional, 32 procesos, 64 descriptores, sin
core dumps, 64 KiB de código/logs y 64 MiB de entrada/salida. La ejecución
de preview dura como máximo 5 segundos, además de operaciones de control OCI
acotadas a 15 segundos cada una. Se admiten hasta 8784 períodos, 20 entradas por
regla, 50 aplicaciones por corrida, 100000 filas, 100000 salidas numéricas y
500000 términos, con snapshot máximo de 64 MiB. La lectura de cada entrada
también está acotada a 100000 intervalos en el rango consultado.

Medición local del 2026-09-22, OCI real sobre WSL: 8784 períodos con 17568 filas
y 17568 salidas se completaron en 4,103 s; 8785 períodos fueron rechazados en
3,281 s. Son tiempos de pared del ejecutor, incluyendo operaciones OCI, y no una
garantía de latencia. La cancelación anual devuelve un estado cancelado sin
resultados parciales.

Hay dos ejecuciones globales, una prueba pendiente por usuario y como máximo
20 trabajos esperando. La espera expira a los 30 segundos. `RuleWorker` permite
configurar el timeout de cola y `OCIExecutor` el de ejecución; los límites de
recursos restantes son parte de la política versionada `reg-001.1`.

La API devuelve 202 y un ID durable. Consultar no espera al contenedor. Cancelar
una prueba en cola es inmediato; una en ejecución solo termina como cancelada
después de la limpieza. El worker tiene una concesión exclusiva en la base,
actualizada periódicamente. Sin heartbeat durante 10 segundos, la API deja de
aceptar trabajos. Al reiniciar, limpia los contenedores de trabajos interrumpidos
y registra `RULE_INTERRUPTED`. La recuperación reserva la concesión por más
tiempo para completar las operaciones OCI antes de anunciar disponibilidad.
Si no se puede confirmar la limpieza, conserva el trabajo para recuperación
y retira la disponibilidad. No instalar varios workers activos por base.

Los resultados conservan revisión del borrador, hashes de código/contexto y
runtime fijado. `/revisions/{id}` devuelve la copia usada por una prueba sin
seguir cambios posteriores del borrador. No existe una ruta de edición de esas
revisiones. Las tablas nuevas son aditivas y no se borran al deshabilitar la
función. Los datos históricos referenciados impiden su eliminación accidental.

## Biblioteca e instancias reutilizables (REG-008)

Desde una unidad del diagrama, guardar y publicar una definición y seleccionar
**Ofrecer en biblioteca**. **Biblioteca del proyecto** muestra nombre, revisión,
tipos compatibles y capacidades. También contiene ejemplos editables de máximo
de caudal, salida horaria, suma de unidades, rampa y presupuestos de agua/energía;
sus alias y entradas deben completarse en el contexto del modelo.

En otra unidad, elegir la revisión y declarar nombre, variante, motivo, valores
tipados, alias y entradas requeridos. El formulario no hereda valores ni IDs del
objeto original. Los candidatos de entradas se filtran por propietario, dimensión,
semántica y rol del puerto. Código, tipos y unidades pertenecen a la revisión
compartida; los valores, referencias y activación pertenecen a la instancia.
**Preparar revisión fijada**, probar y aplicar usan el recorrido de ejecución
existente. El listado de comparación muestra parámetros y hasta 100 filas de la
última preview vigente, junto al total de filas; una edición local invalida esa
preview sin modificar otras instancias.

La aplicación conserva publicación compartida, revisión local, parámetros,
contexto y origen. Publicar otra revisión de la definición no mueve los pins:
las aplicaciones quedan obsoletas hasta su resolución explícita. Editar valores
locales exige desactivar, probar y aplicar de nuevo antes de ejecutar. Las
corridas históricas conservan sus snapshots y sus identificadores de aplicación.

**Datos → Gestionar variantes → Clonar variante activa** copia también instancias
pendientes y aplicaciones activas. Conserva sus pins y registra variante, regla y
aplicación de origen, actor y remapeo. Las aplicaciones copiadas requieren nueva
prueba y aplicación. Si falta un objeto, el formulario solicita un destino del
mismo tipo dentro del modelo; la transacción rechazada no deja una variante
parcial. Las entradas siguen verificando sus propios pins y propietarios: cuando
también cambian sus fuentes deben configurarse explícitamente en la instancia.

Rutas nuevas (analista/admin, CSRF en escrituras):

- `POST /api/projects/{project}/linkable-objects/{object}/rules/{rule}/library`
  con `publication_id` ofrece una revisión inmutable.
- `GET /api/projects/{project}/rule-library` descubre sus contratos sin valores
  ni referencias de la instancia de origen.
- `POST /api/projects/{project}/linkable-objects/{object}/rules/instances` recibe
  `publication_id`, `scenario_id`, `variant_id`, `name`, listas explícitas de
  `parameters`, `aliases`, `inputs`, políticas `temporal`/`windows` cuando proceda,
  `request_id` idempotente y `reason`.
- `GET /api/projects/{project}/rule-library/{publication}/instances` compara
  configuración, activación, obsolescencia y filas vigentes.
- El endpoint existente `POST /api/scenarios/{scenario}/case/variants/{variant}/clone`
  admite `rule_object_map`, mapa de ID original a destino. `RULE_REMAP_REQUIRED`
  identifica objetos pendientes y candidatos compatibles.

La biblioteca es local al proyecto y permanece inaccesible para usuarios externos.
Las tablas aditivas `component_rule_templates` y `component_rule_instance_requests`
referencian publicaciones y borradores existentes; no duplican el código ejecutable.
Esta entrega reutiliza el SDK `reg-006.1` y no modifica la matemática del solver.

## Comprobaciones reproducibles

Usar una base PostgreSQL **exclusiva de pruebas**, nunca una base de proyectos.
La suite crea fixtures con identidades únicas. `POSTGRES_TEST_DATABASE_URL`
habilita el mismo contrato HTTP sobre PostgreSQL; SQLite se prueba siempre.
`RULE_RUNTIME_IMAGE` habilita los casos OCI reales: si falta, se registran como
omitidos y eso no acredita el aislamiento.

```sh
export DATABASE_URL=sqlite:///:memory:
export POSTGRES_TEST_DATABASE_URL=postgresql://test:test@127.0.0.1:5432/rules_test
# Configurar RULE_RUNTIME_COMMAND / RULE_RUNTIME_IMAGE como arriba; no levantar
# un worker adicional: las pruebas administran sus propios workers.
python -m unittest tests.test_reg001_rules tests.test_reg001_runtime tests.test_reg002_rules tests.test_reg002_runtime tests.test_reg003_rules tests.test_reg003_runtime tests.test_reg003_classification tests.test_reg004_rules tests.test_reg004_runtime tests.test_reg005_rules tests.test_reg005_runtime tests.test_reg006_rules tests.test_reg006_runtime tests.test_reg007_rules tests.test_reg008_rules tests.test_ts7_001_classification_catalog tests.test_ts3_input_variants tests.test_ts3_case_variant_api -v
julia --project=. test/component_rules.jl
cd frontend
npm ci
npm run api:generate
npm run api:check
npm test -- --run src/ComponentRules.test.tsx src/HourlyRules.test.tsx src/RelatedRules.test.tsx src/TemporalRules.test.tsx src/BudgetRules.test.tsx src/CalculatedSeries.test.tsx src/ReusableRules.test.tsx src/App.test.tsx src/RunExperience.test.tsx src/ProtectedMutationJourney.test.tsx
npm run build
npx playwright test e2e/component-rules.spec.ts
# Requiere Julia disponible (PATH o variable JULIA) y la imagen OCI configurada.
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-execution.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-hourly.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-related.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-temporal.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-budgets.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-series.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-reuse.spec.ts
```

El smoke de navegador usa el servidor aislado existente, comprueba la entrada
desde la unidad, edición CodeMirror, guardado, recarga y retorno. Las pruebas
de React cubren la interacción asíncrona; las pruebas HTTP/OCI verifican cálculo,
cancelación, cuotas y recuperación con contenedores reales.

El segundo recorrido arranca `scripts/run_rule_acceptance_app.py` con una base y
artefactos temporales, un worker OCI real y Julia. Verifica 5 m³/s en cuatro horas,
desactiva la aplicación, recupera 40 m³/s y consulta el resultado histórico intacto.
En PowerShell, establecer `$env:RULE_ACCEPTANCE_SERVER = '1'` antes de ese comando
y eliminar la variable al terminar. El recorrido horario añade selección de
afluente/disponibilidad, solución `[20, 10, 15, 20]`, publicación nueva,
revalidación con motivo, hueco y cruce de límites, conservando el resultado
histórico. El recorrido de REG-004 comprueba la suma de dos unidades a 10 MW,
la equivalencia del alias de planta y el bloqueo tras cambiar sus miembros,
conservando el mapa de alias y el resultado histórico. REG-005 compara ambas políticas
iniciales con tres intervalos de 0,5, 2 y 1 horas, comprueba las rampas de caudal
y conserva el resultado histórico al cambiar la política y el rango. CI incluye
los ocho recorridos y la prueba Julia. Cada comando inicia su servidor y base
temporal; ejecutar los recorridos por separado. REG-006 compara un presupuesto de 12 MWh,
uno diario de 36.000 m³ aceptando la ventana parcial y el caso libre de 105 MWh
y 504.000 m³, con duraciones de 0,5, 2 y 1 horas e historial intacto.
REG-007 publica `[20, 10, 15, 20]` MW, abre su inspector en el catálogo y resuelve
un caso con esa entrada. Tras cambiar la disponibilidad, regenera `[10, 10, 10, 10]`
MW, comprueba el pin anterior obsoleto y conserva la corrida y su snapshot.
REG-008 crea una definición desde un ejemplo, reutiliza su segunda revisión en
dos unidades de distinta capacidad y resuelve 17 m³/s (5 + 12). Tras editar solo
la segunda instancia resuelve 13 m³/s (5 + 8), compara filas y conserva el snapshot
inicial al publicar otra revisión. La API verifica también idempotencia y aplicación
concurrentes, clonación sin resultados parciales y rechazos de contratos incompatibles.

Regresión adicional del escritor canónico:

```sh
python -m unittest tests.test_ts7_002_canonical_content_model tests.test_ts7_009_run_materialization -v
# Usar otra base PostgreSQL vacía: esta suite comprueba también el catálogo vacío.
POSTGRES_TEST_DATABASE_URL=postgresql://test:test@127.0.0.1:5432/object_series_test python -m unittest tests.test_ts7_010_object_specific_series -v
```

Referencia del mecanismo OCI: [Docker, ejecución de contenedores](https://docs.docker.com/engine/containers/run/).
Los tests de esta entrega no constituyen una auditoría de escapes del kernel.
