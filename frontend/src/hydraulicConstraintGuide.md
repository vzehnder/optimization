## 3. Cómo abrir el editor y aplicar una regla

1. Guarda el diagrama y ejecuta **Validar topologia**. Resuelve errores de conexiones, parámetros o series.
2. Para una regla sobre un tramo, selecciónalo en el dibujo y abre **Propiedades → Cálculos y restricciones · clave_del_tramo**. Para una unidad, selecciona su central y usa el enlace de esa unidad dentro de **Unidades**.
3. Se abre una página con **Nombre de la regla** y el editor **Código Python**. Es una página completa, no una ventana emergente. Si la regla viene de una revisión compartida, su código puede estar fijado; utiliza un borrador propio para editar código.
4. En **Objetos y variables del modelo**, elige un objeto, escribe su alias y pulsa **Agregar alias**. Repite para todos los objetos que leerá el script. No basta con escribir el alias en el código.
5. Agrega los parámetros y, si corresponden, las entradas horarias. Declara explícitamente sus unidades. Completa también la política temporal o las ventanas cuando un ejemplo las necesite.
6. Pulsa **Guardar borrador** y luego **Publicar revisión**.
7. En **Aplicar a la optimización**, selecciona **Variante de aplicación**, **Inicio UTC** y **Fin UTC exclusivo**. Prueba el horizonte completo mediante **Probar restricciones**.
8. Revisa las filas emitidas, sus unidades, objetos, períodos y diagnósticos. Una compilación correcta no demuestra que el problema completo sea factible.
9. Escribe el **Motivo de aplicación o desactivación** y pulsa **Aplicar a variante**. Guardar o publicar por sí solo no activa restricciones en una corrida.
10. Usa **Ejecutar variante con reglas**. Revisa después caudales, balances y cumplimiento en los resultados. Si cambias el modelo, los alias, las entradas, el horizonte o una revisión, puede ser necesario volver a probar y recuperar la aplicación.

Para comenzar con un ejemplo existente: **Biblioteca del proyecto → Ejemplos editables → Caudal mayor o igual a otros caudales**. Crea un borrador y completa sus alias antes de probar. Una biblioteca vacía de plantillas publicadas no impide usar los ejemplos editables.

Si aparece «Ejecutor aislado no disponible» o «Pruebas deshabilitadas en este proyecto», puedes preparar y guardar el código, pero la compilación requiere que el administrador habilite el ejecutor de reglas. No se debe sustituir una prueba pendiente por una corrida sin reglas.

## 4. Qué representa cada caudal

### Tramos

`ctx.objeto.caudal[t]`, cuando el objeto actual es un tramo, representa su caudal medio durante el intervalo `t`, en **m³/s**. Es una variable de decisión no negativa. Su dirección positiva es **from_node_key → to_node_key**. Un caudal negativo no invierte automáticamente la dirección.

Cada tramo posee su propio caudal. Esto incluye río, canal, túnel, compuerta, vertedero, bypass, descarga y otros tipos de tramo. El nombre del tipo por sí solo no introduce ecuaciones de pérdidas de carga, apertura de compuertas ni una relación entre nivel y caudal.

Para una filtración, selecciona el tramo y usa **Agregar comportamiento → Filtración según cota → Editar tabla y gráfico**. La tabla relaciona la cota del embalse de origen (m s. n. m.) con el caudal de filtración (m³/s). Requiere al menos dos puntos, cotas estrictamente crecientes, caudales no negativos y cobertura de todo el rango operativo. No se extrapola. En **Configuración avanzada** puedes elegir cota al inicio (por defecto; usa el volumen inicial en el primer intervalo) o al cierre. Pulsa **Listo**, guarda el diagrama y valida antes de promoverlo.

El comportamiento impone **Q = interpolación(cota)** durante la optimización y transfiere esa misma agua al nodo de destino usando los balances existentes. No agregues otro descuento por filtración. Cambiar la selección del dibujo solo oculta el formulario; **Quitar filtración** y guardar elimina la relación. Las reglas personalizadas siguen añadiéndose a esta ley física, por lo que un mínimo incompatible puede volver el caso infactible. La cota continúa sin estar expuesta en el editor Python.

Cada unión permite configurar **Tiempo de viaje** en segundos, minutos, horas o días, incluidos decimales. El software conserva internamente `travel_time_hours`; cambiar la unidad de visualización no cambia el tiempo físico. Cero mantiene el transporte instantáneo y un valor positivo usa `fixed_delay`.

El caudal de una regla sobre un tramo (`caudal[t]`) y su mínimo operativo se aplican a la **salida del origen**. La llegada al destino se calcula desplazando cada intervalo por el tiempo de viaje y repartiendo su volumen por el solapamiento con los intervalos de destino. Las duraciones pueden variar dentro del horizonte; no se redondea el retardo a un número de períodos. El calendario debe ser consecutivo, sin huecos ni solapamientos. Se trabaja con caudales medios por intervalo: para resolver la operación dentro de un intervalo se necesita una malla más fina.

Las conexiones de entrada y salida de una central tienen retardos independientes. Al generar el caso se convierten en tramos internos compartidos por las unidades conectadas a la misma toma o descarga. La potencia se calcula con el caudal que atraviesa las turbinas en ese período; el retardo de descarga afecta a la disponibilidad del agua aguas abajo.

En **Condición inicial**, el caudal previo constante define el agua que ya viaja al comenzar: volumen inicial = caudal previo × tiempo de viaje en horas × 0.0036 hm³. Por defecto es cero. El caso también admite `initial_arrivals`, un calendario de llegadas procedentes de una corrida anterior, en lugar del caudal previo constante. Los resultados por tramo incluyen caudal de salida (`hydraulic_flow_m3s`), caudal y volumen de llegada (`hydraulic_arrival_flow_m3s`, `hydraulic_arrival_volume_hm3`) y volumen en tránsito al cierre (`hydraulic_in_transit_hm3`).

El agua que sigue viajando al finalizar se conserva en `summary.json → hydraulic_transport`: `final_volume_hm3` y `terminal_arrivals`. Para continuar un horizonte, este último calendario puede usarse como `initial_arrivals` aunque cambien los tamaños de intervalo. No se conecta automáticamente a otra corrida. La política terminal actual registra ese volumen sin valor económico terminal adicional (`carry_forward_unvalued`); no se acredita como agua disponible en el destino. Las reglas temporales personalizadas no sustituyen estas ecuaciones de transporte.

### Unidades, embalses y centrales

| Objeto  | Acceso              | Significado                                          | Unidad     |
| ------- | ------------------- | ---------------------------------------------------- | ---------- |
| Tramo   | `caudal[t]`         | Caudal dirigido del tramo                            | `m3_per_s` |
| Unidad  | `caudal[t]`         | Caudal que atraviesa la unidad desde toma a descarga | `m3_per_s` |
| Unidad  | `potencia[t]`       | Generación de la unidad                              | `mw`       |
| Embalse | `almacenamiento[t]` | Volumen al cierre del intervalo                      | `hm3`      |
| Embalse | `vertimiento[t]`    | Caudal de vertimiento del embalse                    | `m3_per_s` |
| Central | `potencia[t]`       | Suma de potencia de sus unidades activas del caso    | `mw`       |

Las uniones no exponen una variable propia de caudal: selecciona los tramos que entran o salen de ellas. Las centrales no tienen un `caudal` agregado expuesto; suma los caudales de sus unidades cuando ese sea el concepto requerido. La cota, el salto, las coordenadas del dibujo y otros campos del diagrama no se convierten automáticamente en variables de Python.

### Balances de agua que ya impone el motor

- En una unión interior, la suma de caudales entrantes y descargas de unidades coincide con la suma de caudales salientes y tomas de unidades, más los aportes conocidos que incluya el caso.
- Una unión terminal sin tramos salientes ni tomas de unidades representa una salida del sistema. Puede evacuar el agua recibida; no almacena agua.
- En un embalse: **volumen final = volumen anterior + (entradas − salidas) × duración_horas × 0.0036**. El primer volumen anterior es el volumen inicial declarado.
- Los caudales de las unidades se contabilizan tanto en su toma como en su descarga. Una cascada transporta agua hacia aguas abajo; no crea aportes nuevos.
- Si un embalse tiene tramos salientes de tipo `spillway`, su variable `vertimiento` es la suma de esos caudales. Ese agua se descuenta una sola vez del balance.
- Si no tiene un vertedero explícito, se conserva una salida externa implícita de vertimiento. Para dirigir ese agua a otro nodo, dibuja el vertedero correspondiente.
- El mínimo horario de un tramo, si está presente en el período, sustituye su mínimo escalar en ese período. Una restricción personalizada se añade a ese límite; no lo borra.

Evita imponer de nuevo un balance que ya existe sin revisar su significado. En una bifurcación sin otras entradas o salidas, `Q_entrada = Q_rama1 + Q_rama2` ya puede resultar del balance. Añadir `Q_entrada >= Q_rama1 + Q_rama2` será entonces redundante. En objetos sin esa conexión física, la misma fórmula expresa una condición operativa adicional.

## 5. Contrato del código Python

El punto de entrada obligatorio es:

```python
def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion(
            "nombre_de_la_condicion",
            t,
            ctx.objeto.caudal[t] <= ctx.parametros.limite
        )
```

Para aplicar a la optimización, emite condiciones mediante `ctx.restriccion`. No retornes un valor desde `construir`. El modo de cálculo numérico aislado que retorna una cantidad es una función distinta; retornar un número no crea una restricción.

| Elemento                               | Uso                                                                    |
| -------------------------------------- | ---------------------------------------------------------------------- |
| `ctx.objeto`                           | Objeto desde el que abriste la regla                                   |
| `ctx.objetos.alias`                    | Otro objeto registrado con ese alias                                   |
| `ctx.periodos`                         | Índices válidos del horizonte, empezando por cero                      |
| `ctx.parametros.nombre`                | Parámetro escalar con tipo y unidad declarados                         |
| `ctx.entradas.alias[t]`                | Dato conocido de una serie horaria seleccionada                        |
| `ctx.restriccion(nombre, t, relacion)` | Emite una condición para el período                                    |
| `ctx.salida(nombre, t, cantidad)`      | Registra un cálculo numérico conocido, no una solución del optimizador |
| `ctx.transiciones(variable)`           | Compara períodos con la política temporal declarada                    |
| `ctx.ventanas()`                       | Recorre ventanas temporales configuradas                               |

Los nombres de restricciones deben ser no vacíos y únicos **dentro de cada período**. Puedes reutilizar `"maximo"` en todos los períodos, pero no emitir dos filas distintas llamadas `"maximo"` para el mismo `t`.

Los alias de objetos y entradas empiezan con una letra y continúan con letras, dígitos o guion bajo; tienen hasta 64 caracteres. Usa nombres ASCII como `canal_norte`. No uses espacios, guiones medios ni puntos. Los alias deben ser únicos dentro de su colección. No copies un nombre visible como si fuera un alias ya declarado.

## 6. Unidades y parámetros

Las unidades se validan: sumar MW a m³/s, o comparar volumen con caudal, es un error. Escribe los identificadores de unidad tal como aparecen aquí:

| Magnitud          | Unidad de código | Ejemplo de parámetro   |
| ----------------- | ---------------- | ---------------------- |
| Caudal            | `m3_per_s`       | `limite = 20`          |
| Potencia          | `mw`             | `potencia_maxima = 10` |
| Volumen           | `hm3`            | `agua = 0.036`         |
| Energía           | `mwh`            | `energia = 12`         |
| Fracción          | `dimensionless`  | `fraccion = 0.5`       |
| Rampa de caudal   | `m3_per_s_per_h` | `subida = 2`           |
| Rampa de potencia | `mw_per_h`       | `subida = 4`           |

Para un límite de 20 m³/s, crea un parámetro `limite`, tipo **Número**, unidad `m3_per_s`, valor `20`, y usa `ctx.parametros.limite`. Un literal `20` en Python es adimensional; no es un caudal con unidades. Un coeficiente adimensional como `0.5 * Q` sí puede multiplicar una expresión de caudal.

Los campos **Mínimo** y **Máximo** del formulario del parámetro validan el valor del parámetro. No sustituyen a una llamada a `ctx.restriccion` sobre una variable del modelo.

Los nombres y valores siguientes son ejemplos de ingeniería; no representan límites aprobados para el escenario. Cada ejemplo es un programa independiente. Si combinas ejemplos, conserva un solo `def construir(ctx)` y nombres de restricciones distintos.

## 7. Ejemplos listos para adaptar

### 7.1. Un caudal mayor o igual a la suma de otros dos

Abre la regla desde el tramo A. Agrega dos objetos con variable `caudal`, usando los alias `b` y `c`. Pueden ser otros tramos o unidades. Este ejemplo no necesita parámetros ni series.

```python
def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion(
            "suma_caudales",
            t,
            ctx.objeto.caudal[t] >= (
                ctx.objetos.b.caudal[t] + ctx.objetos.c.caudal[t]
            )
        )
```

Si A también es un alias, reemplaza `ctx.objeto.caudal[t]` por `ctx.objetos.a.caudal[t]` y registra `a` en el selector. Los nombres A, B y C no crean objetos. No uses `and` para emitir dos condiciones: llama dos veces a `ctx.restriccion`.

### 7.2. Mínimo y máximo del caudal de un tramo

Crea parámetros `minimo` y `maximo`, ambos en `m3_per_s`, por ejemplo 2 y 20. Revisa que sean compatibles con los mínimos del diagrama y los balances.

```python
def construir(ctx):
    for t in ctx.periodos:
        q = ctx.objeto.caudal[t]
        ctx.restriccion("minimo_operativo", t, q >= ctx.parametros.minimo)
        ctx.restriccion("maximo_operativo", t, q <= ctx.parametros.maximo)
```

### 7.3. Suma con margen de reserva

Registra `b` y `c`. Crea `margen` en `m3_per_s`, por ejemplo 1.5. Un margen positivo expresa una separación explícita sin usar una desigualdad estricta.

```python
def construir(ctx):
    for t in ctx.periodos:
        requerido = ctx.objetos.b.caudal[t] + ctx.objetos.c.caudal[t]
        ctx.restriccion("reserva", t,
            ctx.objeto.caudal[t] >= requerido + ctx.parametros.margen)
```

### 7.4. Fracción máxima del caudal de otro tramo

Registra `principal`. Crea `fraccion` en `dimensionless`, por ejemplo 0.30, con dominio de 0 a 1 si ese es el rango físico.

```python
def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion("fraccion_derivada", t,
            ctx.objeto.caudal[t] <= (
                ctx.parametros.fraccion * ctx.objetos.principal.caudal[t]
            ))
```

### 7.5. Límite horario a partir de disponibilidad conocida

Crea `capacidad` en `m3_per_s`. En **Entradas horarias**, selecciona una serie compatible de disponibilidad y asígnale el alias `disponibilidad`. Sus valores son fracciones conocidas, por ejemplo 1, 0.5 y 0. No son decisiones del optimizador.

```python
def construir(ctx):
    for t in ctx.periodos:
        limite = ctx.parametros.capacidad * ctx.entradas.disponibilidad[t]
        ctx.restriccion("capacidad_horaria", t, ctx.objeto.caudal[t] <= limite)
        ctx.salida("limite_calculado", t, limite)
```

### 7.6. Mínimo proporcional a un afluente conocido

Selecciona una entrada de afluente compatible, en `m3_per_s`, con alias `afluente`, y crea `fraccion` adimensional. Las entradas se seleccionan por semántica, unidad, objeto y revisión, no mediante rutas de archivos en el código.

```python
def construir(ctx):
    for t in ctx.periodos:
        minimo = ctx.parametros.fraccion * ctx.entradas.afluente[t]
        ctx.restriccion("minimo_por_afluente", t, ctx.objeto.caudal[t] >= minimo)
```

### 7.7. Condición sobre vertimiento de un embalse

Registra un embalse como `embalse` y un tramo como `canal`. Verifica si el tramo ya es uno de sus vertederos, porque el modelo enlaza esos caudales mediante el balance.

```python
def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion("vertimiento_requerido", t,
            ctx.objetos.embalse.vertimiento[t] >= ctx.objetos.canal.caudal[t])
```

### 7.8. Presupuesto de agua durante el horizonte

Crea `agua` en `hm3`, por ejemplo 0.036. Configura **Ventanas** para el horizonte completo. La integral utiliza las duraciones reales; no presupone que cada período dura una hora.

```python
def construir(ctx):
    for ventana in ctx.ventanas():
        volumen = ventana.integral(ctx.objeto.caudal).a("hm3")
        ctx.restriccion("presupuesto_agua", ventana,
            volumen <= ctx.parametros.agua)
```

También puedes configurar días civiles y su zona horaria. Declara explícitamente si aceptas o rechazas ventanas parciales; un día civil no siempre contiene 24 horas. No reemplaces la integral por `sum(Q)` cuando buscas volumen.

### 7.9. Rampa de caudal entre períodos

Crea `subida` y `bajada` en `m3_per_s_per_h`. En la política temporal selecciona **Omitir la primera comparación**, o declara una condición inicial con objeto, variable `caudal`, unidad `m3_per_s`, valor e instante anteriores al inicio del horizonte.

```python
def construir(ctx):
    for paso in ctx.transiciones(ctx.objeto.caudal):
        cambio = paso.actual - paso.anterior
        ctx.restriccion("rampa_subida", paso.periodo,
            cambio <= ctx.parametros.subida * paso.horas)
        ctx.restriccion("rampa_bajada", paso.periodo,
            -cambio <= ctx.parametros.bajada * paso.horas)
```

Las transiciones de caudal usan la distancia entre inicios de períodos, en horas. Con la política de omitir, no se restringe el salto entre un período anterior externo y el primero del horizonte. No indexes `t - 1` sin tratar el primer período ni uses períodos futuros.

### 7.10. Activación por un parámetro conocido

Crea `activar`, tipo **Booleano**, y `limite`, tipo **Número**, unidad `m3_per_s`.

```python
def construir(ctx):
    if ctx.parametros.activar:
        for t in ctx.periodos:
            ctx.restriccion("limite_activado", t,
                ctx.objeto.caudal[t] <= ctx.parametros.limite)
```

Si `activar` es falso, esta regla no emite filas. La aplicación pide aceptación explícita para una regla vacía. No confundas eso con una restricción aplicada y satisfecha.

## 8. Operaciones permitidas y errores frecuentes

Las restricciones deben ser **afines**: suma o resta de variables multiplicadas por coeficientes conocidos, más constantes con unidades compatibles. Se admiten `<=`, `>=` y `==`. Para igualdad utiliza dos signos `==`; `=` es asignación de Python.

| Intención                                    | Tratamiento                                                            |
| -------------------------------------------- | ---------------------------------------------------------------------- |
| `Q_a + Q_b <= limite`                        | Válido con caudales y límite de la misma unidad                        |
| `0.5 * Q_a >= Q_b`                           | Válido, coeficiente conocido adimensional                              |
| `Q_a * Q_b`                                  | No válido: producto de decisiones                                      |
| `Q_a / Q_b`                                  | No válido: división por una decisión                                   |
| `if Q_a > Q_b:`                              | No válido: la condición depende de una solución aún desconocida        |
| `min(Q_a, Q_b)` o `max(Q_a, Q_b)`            | No válido sobre variables simbólicas                                   |
| `abs(Q_a - Q_b)`                             | No usar sobre variables simbólicas; emitir límites superior e inferior |
| `Q_a < limite`                               | No usar desigualdades estrictas; expresar un margen explícito          |
| `ctx.salida("q", t, Q_a)`                    | No válido: una salida numérica no lee decisiones futuras               |
| `import pandas`, leer CSV o hacer peticiones | No disponible en el entorno de reglas                                  |

Para `abs(Q_a - Q_b) <= tolerancia`, emite `Q_a - Q_b <= tolerancia` y `Q_b - Q_a <= tolerancia`, con nombres diferentes. `tolerancia` debe tener unidades de caudal.

Puedes usar variables locales y funciones auxiliares de Python compatibles con el entorno. El SDK ofrece funciones básicas como `range`, `len`, `sum`, `enumerate`, `zip`, `min`, `max`, `abs`, `float`, `int`, `bool` y `print`; su disponibilidad no convierte una operación no lineal sobre decisiones en válida. Los parámetros con unidades tampoco deben convertirse a `float` para eliminar su dimensión.

El contexto es inmutable. No puedes crear variables del optimizador, cambiar la topología, editar series, importar módulos, acceder a atributos privados o usar archivos y red desde una regla. Utiliza parámetros y entradas declaradas en el formulario. La ejecución tiene límites de tiempo, memoria y salida.

## 9. Horizonte, series y revisiones

- Todos los objetos relacionados deben pertenecer al mismo modelo activo del escenario. Un objeto de otro escenario o proyecto no es una referencia válida.
- El fin del horizonte es exclusivo. Los instantes se interpretan en UTC para la compilación; no confundas una hora local con UTC.
- Cada serie de entrada debe cubrir exactamente los intervalos requeridos con unidad y semántica compatibles. Una revisión y su hash fijan qué datos utilizó la prueba.
- Los valores conocidos de afluente o disponibilidad pueden formar coeficientes y límites. Los valores de `caudal`, `potencia` y `almacenamiento` son decisiones: no tienen un resultado numérico durante la compilación.
- Una regla sin referencias temporales compara variables del mismo período. Para referencias anteriores configura la política temporal. Para acumulados usa ventanas.
- El sistema admite hasta 8.784 períodos por compilación, 100.000 filas y 500.000 términos. El editor admite hasta 50 alias de objetos y 20 entradas. Mantén los logs breves; el ejecutor limita su tamaño.
- Las reglas activas se intersectan con los límites físicos y entre sí. Ninguna tiene prioridad para anular otra. Si exiges `Q >= 15` y `Q <= 10`, el problema es contradictorio.
- La prueba detecta errores de código, referencias y algunas contradicciones escalares. Una relación entre varios caudales puede pasar la prueba y resultar infactible al resolver los balances completos.

## 10. Revisión de ingeniería y resultados

Antes de activar una regla, registra su objetivo, los objetos elegidos, el origen de cada parámetro, sus unidades, el horizonte y la variante. Verifica la dirección de los tramos con la tabla de conectividad, especialmente en bypass y vertederos.

Después de probar, revisa al menos un período de cada condición y uno en que cambie una entrada horaria. Comprueba que `Q_A >= Q_B + Q_C` tenga los signos correctos: trasladada al lado izquierdo es `Q_A - Q_B - Q_C >= 0`.

Después de resolver, compara los caudales con la regla. Los resultados por activo identifican cada tramo como `hydraulic_reach` y su clave técnica; su caudal está en la columna `hydraulic_flow_m3s` de `asset_dispatch.csv`. Los caudales de generación permanecen en `hydro_turbine_flow_m3s` de las unidades. El informe de cumplimiento utiliza las identidades y períodos de la corrida.

Si el solver informa infactibilidad, revisa conjuntamente disponibilidad de agua, volúmenes iniciales y terminales, mínimos físicos, capacidades y todas las reglas activas. Un error de factibilidad no identifica por sí solo cuál condición es incorrecta. Cambiar una restricción requiere un nuevo borrador/revisión y una nueva prueba; conserva un motivo de aplicación comprensible.

Este archivo incluye parámetros de entrada que podrían no tener soporte completo en el motor. El transporte admite tiempo de viaje fijo; otros métodos de routing siguen sin soporte. La presencia de un campo en el anexo no garantiza que sea una variable accesible ni una restricción implementada. Para un límite operativo adicional, utiliza una variable de la tabla del apartado 4 y verifica su efecto en una corrida.

## 11. Diagnóstico rápido

| Mensaje o síntoma                               | Revisión recomendada                                                                  |
| ----------------------------------------------- | ------------------------------------------------------------------------------------- |
| Guarda primero el tramo activo                  | Guarda el diagrama antes de abrir su editor                                           |
| Objeto fuera del snapshot / alias no disponible | Revisa escenario, variante, actividad del elemento y alias seleccionado               |
| Capacidad desconocida                           | Comprueba el nombre exacto de la variable y su disponibilidad para ese tipo de objeto |
| Unidades incompatibles                          | Usa parámetros tipados y no mezcles caudal, potencia y volumen                        |
| Nombre duplicado                                | Usa un nombre distinto para cada condición del mismo período                          |
| Mínimo mayor que máximo conocido                | Revisa mínimos físicos, series y otras cotas de la misma variable                     |
| Referencia temporal no soportada                | Configura la política inicial; usa `ctx.transiciones` o ventanas                      |
| No se emitieron restricciones                   | Revisa bucles, condiciones conocidas y llamadas a `ctx.restriccion`                   |
| Revisión obsoleta                               | Vuelve a probar o usa el recorrido de recuperación después de cambios                 |
| Ejecutor aislado no disponible                  | Requiere habilitar el servicio de ejecución de reglas                                 |
| Solver infactible                               | Examina las restricciones junto con los balances y las condiciones terminales         |
