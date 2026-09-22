# Operación y verificación de REG-001 a REG-004

REG-001 guarda borradores y calcula un máximo escalar de caudal. REG-002 incorpora
publicación, aplicaciones a variantes y restricciones afines en el optimizador
hidráulico v3. REG-003 calcula límites horarios desde entradas canónicas fijadas.
REG-004 relaciona unidades, plantas y embalses del mismo modelo.
Las revisiones `sealed_preview` son copias inmutables
de pruebas; el estado de la definición editable sigue siendo `draft`.

## Contrato del primer SDK

```python
def construir(ctx):
    return ctx.parametros.capacidad * ctx.parametros.disponibilidad
```

`capacidad` declara tipo `number`, unidad canónica `m3_per_s` y valor 80;
`disponibilidad` declara `number`, unidad `dimensionless`, valor 0.75 y rango
0–1. El resultado es 60 m³/s. El SDK `reg-004.1` conserva la unidad en la
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
a otros períodos u objetos sin alias se rechazan. `construir` no devuelve un escalar en este
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
cálculos en la preview y snapshot; publicar series derivadas corresponde a REG-007.

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
variables, condiciones simbólicas y referencias a otros períodos.

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

El SDK `reg-004.1` exige reconstruir la imagen y reiniciar el worker con su digest.
Las publicaciones/aplicaciones de un SDK anterior necesitan publicar, probar y
aplicar de nuevo antes de ejecutar; los datos históricos siguen legibles.

## Runtime Linux compartido por desarrollo y CI

La imagen se construye únicamente con `runtime/component_rules/`, sin enviar
el repositorio completo como contexto. El Dockerfile fija CPython 3.12.14 por
digest. El SDK está incluido en la imagen y su digest final fija ambos.

```sh
docker build -t component-rules:reg-004 runtime/component_rules
export RULE_RUNTIME_IMAGE="$(docker image inspect component-rules:reg-004 --format '{{.Id}}')"
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
docker build -t component-rules:reg-004 runtime/component_rules
$env:RULE_RUNTIME_IMAGE = (docker image inspect component-rules:reg-004 --format '{{.Id}}').Trim()
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
python -m unittest tests.test_reg001_rules tests.test_reg001_runtime tests.test_reg002_rules tests.test_reg002_runtime tests.test_reg003_rules tests.test_reg003_runtime tests.test_reg003_classification tests.test_reg004_rules tests.test_reg004_runtime tests.test_ts7_001_classification_catalog -v
julia --project=. test/component_rules.jl
cd frontend
npm ci
npm run api:generate
npm run api:check
npm test -- --run src/ComponentRules.test.tsx src/HourlyRules.test.tsx src/RelatedRules.test.tsx src/RunExperience.test.tsx src/ProtectedMutationJourney.test.tsx
npm run build
npx playwright test e2e/component-rules.spec.ts
# Requiere Julia disponible (PATH o variable JULIA) y la imagen OCI configurada.
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-execution.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-hourly.spec.ts
RULE_ACCEPTANCE_SERVER=1 npx playwright test e2e/component-rules-related.spec.ts
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
conservando el mapa de alias y el resultado histórico. CI incluye los cuatro
recorridos y la prueba Julia.

Referencia del mecanismo OCI: [Docker, ejecución de contenedores](https://docs.docker.com/engine/containers/run/).
Los tests de esta entrega no constituyen una auditoría de escapes del kernel.
