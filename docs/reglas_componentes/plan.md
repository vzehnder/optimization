# Plan: motor de cálculos y restricciones por componente

Fecha: 2026-09-21.
Estado: decisiones adoptadas por delegación del usuario; REG-001 a REG-007 implementados y verificados, REG-008 a REG-014 pendientes.
Tracker: [issues](issues/tracker.md).

## 1. Objetivo y decisiones de la entrevista

Permitir que un analista escriba Python desde la web para calcular series y
construir restricciones sobre las variables de los componentes de un caso.
Conservar React, FastAPI, el catálogo canónico y Julia/JuMP con HiGHS.

El usuario eligió la opción 3 y aceptó seguir las recomendaciones en las preguntas
restantes. Esta tabla registra esas recomendaciones como decisiones de este plan.

| Pregunta de diseño | Decisión adoptada |
| --- | --- |
| ¿Qué matemática admite la primera versión? | Expresiones afines sobre variables existentes y restricciones `<=`, `>=`, `==`; cálculos y condiciones sobre datos conocidos. |
| ¿Cuál es el primer componente? | Una unidad hidráulica del modelo v3, empezando por un máximo de caudal turbinado. |
| ¿Se calculan series o se construyen restricciones? | Ambos; las series numéricas se calculan antes de optimizar y las restricciones producen una representación simbólica. |
| ¿Python real o un lenguaje que se le parece? | CPython con SDK propio, funciones y bucles; superficie disponible acotada y ejecución aislada en servidor. |
| ¿Quién escribe código? | Usuarios internos `analyst` y `admin`, con las autorizaciones del proyecto; externos no pueden editar ni ejecutar código arbitrario. |
| ¿Dónde vive una regla? | Definición versionada del proyecto e instancia aplicada a un objeto y una variante; la revisión aplicada queda fijada. |
| ¿Cómo se referencian objetos y series? | Alias legibles declarados en UI y resueltos a identidades estables; nunca depender del nombre visible ni de la posición en una lista. |
| ¿Qué gana ante límites existentes? | Todas las restricciones se aplican conjuntamente. Una regla no elimina balances, límites físicos ni otras reglas. |
| ¿Cómo se tratan tiempo y unidades? | Grilla exacta del caso, duraciones explícitas, UTC y unidades verificadas; transformaciones temporales previas y explícitas. |
| ¿Se sigue automáticamente una revisión nueva? | No. Se señala obsolescencia y se bloquea una nueva ejecución hasta revalidar o reemplazar con motivo, conforme a TS-7. |
| ¿Se pueden compartir reglas? | Dentro del proyecto, mediante plantillas versionadas y asignaciones independientes; compartición global queda fuera. |
| ¿Dónde corre Python? | Ejecutor aislado con contenedores Linux efímeros; FastAPI coordina y Julia solo recibe datos y restricciones validados. |
| ¿Qué necesita ver el analista? | Entradas disponibles, editor, parámetros con unidades, preview, errores localizados y efecto de las restricciones en resultados. |
| ¿Cuándo entran consolas y automatización? | Al final de esta secuencia; hasta entonces se bloquean esos recorridos si el caso contiene reglas activas que aún no pueden respetar. |
| ¿Cómo se entrega? | Catorce issues AFK verticales; MVP utilizable al completar REG-001 a REG-003. |

## 2. Base existente y precedencias

La inspección es de lectura; no se verificó el estado de un despliegue ni se
ejecutaron migraciones. Los archivos siguientes son puntos de integración,
no una obligación de concentrar nueva lógica en esos módulos.

| Base observada | Uso en la propuesta |
| --- | --- |
| [React y FastAPI](../../README.md) | Editor integrado y API autenticada; reutilizar navegación, OpenAPI y errores existentes. |
| [Objetos vinculables](../../app/linkable_objects.py) | Identidad y pertenencia de componentes, unidades, plantas y embalses. |
| [Clasificación](../../app/time_series_classification.py) | Dimensiones, unidades, semántica y compatibilidad; no crear un catálogo paralelo. |
| [Modelo canónico](../../app/time_series_canonical.py) y [bindings](../../app/time_series_bindings.py) | Selección de revisiones selladas, hash, propiedad de series específicas y escrituras transaccionales. |
| [Transformaciones](../../app/transformations.py) | Precedente de entradas y resultados derivados con lineage. |
| [Materialización comprobada por tests](../../tests/test_ts7_009_run_materialization.py) y [ejecutor](../../app/runner.py) | Snapshot inmutable, cola y corrida Julia existentes. |
| [Motor de sistemas](../../src/system_dispatch.jl) | Adaptadores diferentes para sistemas v1/v2 y para hidráulica v3; ambos deben interpretar el mismo contrato de reglas. |
| [Recorrido protegido](../../frontend/src/ProtectedMutationJourney.tsx) | Integrar selecciones/publicaciones de series en el patrón existente y conservar el retorno al objeto. |

### Ampliación explícita de TS-6

El [PRD TS-6](../series_tiempo/iter6/prd.md) y su
[decisión 3](../series_tiempo/iter6/decision_record_ts6_transformation_semantics.md)
excluyeron almacenar y ejecutar scripts proporcionados por usuarios. El usuario
solicita ahora esa capacidad mediante una API de modelado. Este plan sustituye
esa exclusión **solo para las reglas versionadas del nuevo subsistema**, ejecutadas
por su sandbox y validadas mediante su contrato. El registro TS-6 conserva sus
transformaciones declarativas y no se convierte en un ejecutor de texto Python.
La nueva regla no debilita revisiones selladas, permisos ni compatibilidad TS-7.

La [especificación TS-7](../series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md)
sigue gobernando catálogo, series específicas, revisiones y bindings. Los archivos
de importación PostgreSQL son una propuesta independiente y no son bloqueadores.

### Límite real del motor hidráulico

En v3 existen variables de caudal y potencia por unidad, y volumen almacenado y
vertimiento por embalse. La potencia de una planta puede exponerse como suma
derivada de sus unidades; no debe introducirse una variable física duplicada.
Los tramos no tienen una variable de caudal independiente general. No exponer
`tramo.caudal` ni inferirlo de una topología arbitraria en esta iteración.
La cota de embalse v3 se obtiene después de resolver: no está disponible como
variable simbólica para las nuevas reglas. Tampoco se amplía el soporte físico
existente de curvas, redes o acoplamiento hidroeléctrico.

## 3. Historias de usuario

| ID | Historia |
| --- | --- |
| HU-01 | Como analista, quiero escribir, guardar y probar una regla desde un componente, con errores comprensibles. |
| HU-02 | Quiero que un límite personalizado participe realmente en la optimización y pueda activar/desactivar su aplicación con trazabilidad. |
| HU-03 | Quiero calcular límites horarios usando series y parámetros con revisiones y unidades verificadas. |
| HU-04 | Quiero relacionar variables de varias unidades, plantas y embalses del mismo modelo. |
| HU-05 | Quiero expresar rampas y relaciones entre períodos con una condición inicial explícita. |
| HU-06 | Quiero limitar energía y agua acumuladas por una ventana temporal definida. |
| HU-07 | Quiero guardar un cálculo numérico como serie derivada reutilizable sin modificar su origen. |
| HU-08 | Quiero reutilizar el mismo código en varios componentes cambiando parámetros y entradas. |
| HU-09 | Quiero comparar revisiones, resolver obsolescencia y consultar qué versión usó cada corrida. |
| HU-10 | Quiero inspeccionar cumplimiento y errores de reglas en los resultados. |
| HU-11 | Quiero usar la misma API sobre otros tipos de componentes que el optimizador ya soporta. |
| HU-12 | Quiero que consolas y programaciones respeten las reglas preparadas por el analista. |

## 4. Experiencia y ciclo de vida

Entrada contextual «Cálculos y restricciones». Panel de lectura con reglas
aplicadas y estado; acción de edición con origen/alcance, definición, comprobación
y aplicación. El editor Python usa CodeMirror y autocompleta únicamente capacidades
que la combinación de componente y motor soporta. Las acciones sobre series
reutilizan el recorrido de mutación de TS-7.

Estados separados:

- Definición: borrador editable, revisiones publicadas inmutables, archivada.
- Instancia: definición y revisión fijadas, objeto, variante, alias, parámetros,
  entradas, activación y revisión de concurrencia.
- Validación: pendiente, válida, obsoleta o inválida, calculada por el servidor.
- Trabajo de prueba/compilación: en cola, ejecutando, terminado, fallido o cancelado.

Guardar borrador no altera aplicaciones existentes. Publicar sella código,
contrato de entradas/parámetros y versión del SDK; no lo aplica automáticamente.
Aplicar, reemplazar, desactivar o revalidar deja un evento con actor y motivo.
La edición usa control optimista; una revisión desactualizada produce conflicto
sin sobrescribir al otro editor. Archivar impide nuevas aplicaciones y mantiene
revisiones y referencias históricas; aplicaciones vigentes requieren resolución
explícita antes de una nueva corrida. No hay borrado físico de historia utilizada.

La prueba usa el horizonte completo seleccionado aunque la UI muestre una muestra.
Una prueba exitosa acredita compilación, tipos y datos, no factibilidad del modelo.
Los errores incluyen regla, línea de código cuando sea posible, alias, objeto y
período. Una regla con cero restricciones informa el hecho; aplicarla como regla
de restricciones exige aceptar explícitamente ese resultado, no parece activa
con efecto inexistente.

## 5. API Python y contrato matemático

El SDK expone contexto inmutable, parámetros tipados, series numéricas, objetos
simbólicos y métodos para emitir restricciones y salidas numéricas. No expone
ORM, sesión HTTP, archivos de aplicación ni un objeto JuMP.

El siguiente ejemplo es una propuesta de API, no código existente ni un prototipo:

```python
def construir(ctx):
    unidad = ctx.objeto
    for t in ctx.periodos:
        q_min = ctx.entradas.afluente[t] * ctx.parametros.fraccion_minima
        q_max = ctx.parametros.capacidad * ctx.entradas.disponibilidad[t]
        ctx.restriccion("caudal_minimo", t, unidad.caudal[t] >= q_min)
        ctx.restriccion("caudal_maximo", t, unidad.caudal[t] <= q_max)
        ctx.salida("limite_calculado", t, q_max)
```

Los parámetros declaran tipo, unidad, rango y valor; un número dimensional se
introduce como cantidad con unidad, no se adivina su dimensión. La disponibilidad
es adimensional. Las series y variables conservan dimensiones en las operaciones.
Se permiten conversiones explícitas soportadas por el catálogo; una conversión
no autoriza por sí sola un binding semánticamente incompatible. Añadir unidades
de energía, volumen, tiempo, rampas y adimensionales mediante migraciones aditivas
si faltan; no asumir que ya existen todas las semillas.

Capacidades matemáticas del corte:

- Suma/resta de expresiones, multiplicación por datos conocidos y división por
  datos conocidos distintos de cero. Constantes finitas y coeficientes conocidos
  pueden variar por período.
- Igualdades y desigualdades no estrictas, combinadas con todos los límites base.
- Condiciones Python sobre datos conocidos. Prohibir conversión de una expresión
  simbólica a booleano, incluso en `if`, `and`, `or` y comparaciones encadenadas.
- Rechazar productos/divisiones entre variables, `abs`, `min`, `max`, potencias
  no lineales o condiciones sobre decisiones del solver. Esas funciones pueden
  operar sobre datos numéricos ya conocidos.
- Los cálculos numéricos pueden ser no lineales sin convertir el modelo en no
  lineal: lo determinante es la expresión que involucra variables de decisión.

No se crean nuevas variables del usuario, binarias ni penalizaciones; no se
modifica el objetivo ni se ejecutan callbacks durante el solve. El modelo base
puede conservar sus propias binarias o formulaciones por tramos existentes.

Una regla es genérica por operadores y capacidades. Registrar una nueva clase
de componente requiere mapear sus variables reales, sin cambiar el lenguaje ni
prometer compatibilidad antes de implementar ese adaptador.

## 6. Flujo de compilación y materialización

```mermaid
flowchart LR
    A[Editor y selección de entradas] --> B[Revisiones y contexto congelados]
    B --> C[Python aislado y SDK]
    C --> D[Series calculadas e IR de restricciones]
    D --> E[Validación del servidor y hashes]
    E --> F[Snapshot inmutable del caso]
    F --> G[Adaptador Julia y JuMP]
    G --> H[Resultados y cumplimiento]
```

IR significa representación intermedia. Cada fila contiene identidad de regla y
aplicación, nombre local, referencia de código, relación, constante y términos
afines. Cada término referencia una identidad estable de objeto, clave de variable,
período y coeficiente con unidad. El servidor normaliza orden y términos repetidos,
rechaza datos no finitos, claves desconocidas, referencias externas al snapshot y
límites de volumen excedidos. Un SDK o JSON válido no sustituye esta validación.
Julia verifica de nuevo contrato, referencias y tipos antes de añadir filas.

Los alias se resuelven contra el snapshot del caso, no contra el proyecto completo.
Dos componentes en proyectos iguales pero corridas/modelos separados no se pueden
relacionar. Los puertos de series respetan semántica, proyecto, objeto propietario
y revisión exacta; una serie específica no se vuelve global al leerla desde Python.

La materialización tiene dos fases: congelar dependencias y compilar fuera de una
transacción larga; luego comprobar que las revisiones de la variante y dependencias
siguen siendo las esperadas y confirmar el snapshot atómicamente. Si hubo cambios,
rechazar con conflicto y recompilar. Usar una clave idempotente por solicitud.
No dejar una versión parcialmente visible ni mantener bloqueos durante el sandbox.

El snapshot conserva código y su hash, SDK e imagen por digest, política de ejecución,
IR y hash, parámetros efectivos, fuentes/revisiones/hash, grilla, zona horaria,
objetos, topología y versiones de contratos/motor. Un solve consume esa IR congelada;
no vuelve a ejecutar Python ni sigue punteros actuales del catálogo. Un reintento
usa el mismo snapshot. Recompilar un caso es otra operación y conserva nuevo lineage.

Versionar el bloque opcional de reglas del contrato de caso, y negociar/verificar
la capacidad correspondiente antes de encolar. Ausencia del bloque conserva el
comportamiento anterior; una versión desconocida o un motor viejo con reglas
presentes bloquea la corrida. El soporte debe atravesar validación, carga y
normalización de ambos caminos Julia; nunca descartar campos desconocidos y
resolver silenciosamente sin las restricciones.

## 7. Tiempo, agregaciones y series derivadas

Cada intervalo tiene inicio UTC y duración positiva; entradas de una aplicación
comparten exactamente la grilla del caso. Huecos, duplicados, cobertura insuficiente
y desalineación bloquean. Reutilizar transformaciones explícitas para corregirlos.
No descargar datos externos durante el cálculo ni rellenar valores automáticamente.

Los valores de potencia y caudal representan medias por intervalo; almacenamiento
representa estado al final del intervalo. Una rampa entre medias usa la distancia
entre inicios de intervalos, expresada en horas, incluso con duraciones variables.
Al usar referencias anteriores, declarar política de borde: omitir el primer
período de forma visible o proporcionar valor inicial tipado y su instante. No hay
wraparound por índices negativos. El almacenamiento inicial del modelo se expone
como dato conocido; no se inventa una generación o un caudal inicial.

Los presupuestos convierten potencia por horas a MWh y caudal por segundos a m³
o hm³ con conversión explícita. Las ventanas son el horizonte completo o días
civiles en una zona IANA explícita. Un día de cambio horario puede tener 23/25 horas.
Los bordes de ventana deben coincidir con los intervalos; rechazar intervalos que
los crucen en esta versión. Días parciales bloquean salvo política explícita de
ventana parcial; no prorratear presupuestos silenciosamente.

Las salidas numéricas pueden previsualizarse sin persistir. REG-007 permite publicar
un set/revisión derivado a través del escritor canónico y con su contrato de
clasificación. Las salidas de variables de decisión son resultados de corrida,
no series de entrada precomputadas. Regenerar una serie requiere acción explícita,
produce revisión nueva y conserva lineage completo. No hay cadenas automáticas
entre scripts: consumir una salida de otro cálculo exige que esté publicada y
seleccionar su revisión; rechazar ciclos de recetas/dependencias.

## 8. Aislamiento, recursos y operación

El runtime elegido para el plan es un ejecutor de contenedores OCI Linux, con
CPython/SDK fijados por digest. En desarrollo Windows puede alojarse en un runtime
Linux local; CI debe disponer de la misma frontera. No se instala nada en esta
entrega documental. El despliegue debe aportar el runtime; su ausencia deja la
función no disponible, sin fallback a `exec` dentro de FastAPI.

Cada trabajo tiene un contenedor efímero sin red, no privilegiado, usuario sin root,
capacidades retiradas, `no-new-privileges`, perfil seccomp y raíz de solo lectura.
No monta repositorio, secretos, base de datos ni socket de Docker. Recibe solo un
payload inmutable y devuelve datos estructurados por un canal acotado. Temporales,
si hacen falta, son privados y limitados. El gestor confiable vive fuera del sandbox;
producción lo aísla de los servicios de aplicación/datos. Filtrar AST/importaciones
es una capa de política, no una frontera de seguridad suficiente.

Primera distribución: SDK y utilidades numéricas deterministas incluidas; no `pip`,
red, reloj/azar del sistema, archivos de usuario ni importaciones generales. La
política admite sintaxis Python útil como funciones, bucles y comprensiones. El
servidor valida cada salida como no confiable, aunque la API sea de uso interno.
No afirmar que un contenedor o filtro garantiza ausencia absoluta de escapes.

Cuotas iniciales propuestas, configurables y pendientes de medir en implementación:

| Recurso | Límite inicial |
| --- | --- |
| Tiempo de ejecución de preview / compilación para corrida | 5 s / 30 s, aparte de una espera de cola también acotada |
| CPU / memoria / procesos por sandbox | 1 CPU / 512 MiB / 32 procesos |
| Código / logs | 64 KiB / 64 KiB |
| Payload de entrada / salida estructurada | 64 MiB / 64 MiB |
| Instancias activas / períodos por solicitud | 50 / 8.784 |
| Restricciones / términos afines totales | 100.000 / 500.000 |
| Concurrencia inicial | 1 trabajo por usuario y 2 globales; cola máxima de 20 |

Se aplica el primer límite alcanzado. El gestor impone cuotas del SO, cancela todo
el grupo de ejecución y limpia recursos; se documenta por separado el timeout del
solver. La UI pagina errores/filas y limita muestras/gráficos, sin truncar la IR ni
validar solamente lo visible. La ejecución HTTP es asíncrona con estado y cancelación
desde REG-001; un reinicio marca trabajos interrumpidos y elimina contenedores
huérfanos. No se promete rendimiento a partir de estas cifras.

## 9. Cambios, resultados y recorridos existentes

Desde el primer binding ejecutable, cambios incompatibles de topología, parámetros,
SDK, revisiones de reglas o entradas invalidan la validación; las nuevas publicaciones
no reescriben los pins. Mantener una revisión antigua exige revalidación explícita
y motivo, como TS-7. Un borrador nuevo no afecta aplicaciones publicadas.
REG-009 añade comparación y recuperación guiadas; las comprobaciones básicas no
se posponen hasta ese issue.

Los resultados factibles permiten evaluar cada fila con la solución y mostrar
holgura/margen y tolerancia en la unidad de la fila. Una igualdad muestra residuo.
Registrar tolerancias absolutas y relativas usadas; conservar coeficientes y
unidades del snapshot. No mostrar un valor de variable si no hay solución primal.
Las contradicciones simples se detectan antes del solve; una infactibilidad general
se presenta con el conjunto de reglas y estado del solver, sin afirmar que se
identificó una causa única ni prometer un IIS o un diagnóstico mínimo.

Hasta REG-014, las rutas de consola y programación con reglas activas bloquean
explícitamente. Al habilitarlas, usarán revisiones preparadas por el analista y
parámetros operativos efectivos antes de compilar. Los externos solo ven mensajes
operativos seguros; no reciben código, IR, trazas ni referencias internas. Los
modelos sin reglas siguen funcionando en todas las etapas.

## 10. Validación y salida de cada entrega

Cada issue prueba el comportamiento nuevo y sus negativas relevantes, incluyendo
permisos, concurrencia o transacciones cuando corresponda. Las modificaciones de
persistencia se verifican en SQLite y PostgreSQL; no basta un test de esquema.
Las nuevas capacidades de modelo tienen tests Julia que comprueban el efecto en
la solución, además de roundtrip de la IR y rechazo de capacidades desconocidas.
Un smoke del runtime real prueba límites y cancelación: un mock no acredita aislamiento.
Las pruebas de UI incluyen retorno contextual, errores y ausencia de cambios antes
de aplicar. Regenerar y verificar OpenAPI cuando cambie el contrato HTTP.

Fixtures mínimas: cuatro intervalos y una unidad para el tracer bullet; series con
revisiones distintas; dos unidades para un límite conjunto; duraciones distintas
para rampas; días civiles con cambio horario para presupuestos; un problema
intencionalmente infactible. Antes de considerar disponible el MVP, probar un
horizonte anual dentro de cuotas y otro que las exceda, con cancelación y medición
registrada. No convertir cuotas propuestas en cifras de capacidad verificadas.

La disponibilidad se controla por proyecto y capacidades implementadas. Desactivar
la función bloquea nuevas ejecuciones con reglas activas y conserva historial;
nunca omite restricciones para permitir una corrida. No borrar tablas ni revisiones
como mecanismo de rollback. Las migraciones de cada slice son aditivas.

## 11. Fuera de alcance

- Nuevas variables libres, binarias de usuario, restricciones no lineales sobre
  decisiones, modificación del objetivo o reglas blandas con penalización.
- Sustituir los modelos físicos, implementar caudal genérico de tramos, nuevas
  cascadas, altura variable, redes eléctricas o curvas no soportadas por el motor.
- Notebooks, paquetes arbitrarios, conectores externos desde scripts, ejecución
  de Python en el navegador, creación automática de código con IA.
- Biblioteca global entre proyectos, cadenas automáticas de scripts, resultados
  posteriores al solve usados circularmente como entradas de la misma corrida.
- Despliegue o implementación durante esta entrega de planificación.

## 12. Fuentes técnicas consultadas

- [JuMP: restricciones](https://jump.dev/JuMP.jl/stable/manual/constraints/):
  construcción y gestión de restricciones del modelo.
- [HiGHS.jl: capacidades](https://jump.dev/JuMP.jl/stable/packages/HiGHS/):
  restricciones y objetivos soportados; fundamento del corte afín.
- [Docker: ejecución](https://docs.docker.com/engine/containers/run/):
  aislamiento configurable, identidad, mounts y referencia de imagen por digest.
- [Docker: cuotas](https://docs.docker.com/engine/containers/resource_constraints/):
  límites explícitos de CPU y memoria, que no se deben asumir activos por defecto.
- [CodeMirror para Python](https://github.com/codemirror/lang-python):
  editor y soporte de sintaxis; el autocompletado de dominio será parte de la app.

Estas fuentes documentan mecanismos disponibles. La arquitectura, cuotas y secuencia
anteriores son decisiones propuestas para este proyecto, no garantías de esas herramientas.
