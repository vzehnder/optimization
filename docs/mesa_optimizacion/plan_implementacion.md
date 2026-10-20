# Plan de implementación de la mesa de optimización

Fecha: 2026-10-20.
Estado: desglose aprobado; prototipo conceptual validado por el usuario.
Seguimiento: [tracker](tracker.md).

El usuario confirmó el 2026-10-20 mantener granularidad, dependencias y tipos
del desglose, además de las interfaces S1/S2 y S3 condicional para TDD. Esa
confirmación no decide por sí sola la necesidad de cooptimización mixta ni las
otras decisiones técnicas que MESA-001 debe resolver.

## Resultado esperado

El analista abre una mesa en el contexto de un escenario/caso, encuentra sus
componentes, configura pestañas y paneles, consulta o edita entradas permitidas,
escoge el período, ejecuta el modelo correspondiente y compara resultados sin
abandonar la pantalla. La distribución y las configuraciones sobreviven a una
recarga. Los datos y resultados provienen de los servicios reales.

El HTML aprobado se reimplementará en la aplicación React existente. No se
promoverá su generador ficticio de datos a producción.

## Alcance visual aceptado y supuestos de implementación

Confirmado en la conversación:

- Una pantalla con pestañas para BESS, demanda, renovables y componentes
  hidráulicos, incluyendo centrales y embalses.
- Incorporar otros componentes y series manuales.
- Configurar paneles, con una distribución 2×2 como caso principal.
- Mostrar una o varias series como gráfico o tabla.
- Elegir fechas, ejecutar y comparar antes/después desde la mesa.
- Planificar primero; conectar e implementar posteriormente.
- Conservar screenshots para validar la implementación mediante TDD.

Propuestas que deberán fijarse en la primera entrega:

- Tomar A · Paneles como diseño principal. B y C no se implementan en este corte.
- Ubicar la mesa en la superficie interna del analista/admin, accesible desde el
  escenario. La consola externa y el portal cliente mantienen sus contratos.
- Una configuración visual por usuario y caso, con un valor inicial compartido
  definido por código. No altera el snapshot matemático ni las entradas.
- Un contexto activo de caso/variante/período; cambiarlo nunca mezcla resultados
  o permisos de otro caso. Los identificadores de los componentes son estables.
- Hasta seis paneles visibles por pestaña: 1×1, 1×2, 2×2 y 2×3; al reducir la
  distribución se ocultan paneles sin borrar su configuración.
- Distinguir crear un activo físico, asociar un activo existente y agregar una
  serie manual de apoyo. No todas estas acciones modifican el modelo ejecutable.
- Separar los valores previos observables de las salidas que todavía no existen.

## Base existente comprobada

Esta inspección es del árbol de trabajo local del 2026-10-20, no una afirmación
de que los cambios locales ya estén integrados en una rama compartida.

| Capacidad | Evidencia en el repositorio | Uso previsto |
| --- | --- | --- |
| React y rutas por escenario | [App.tsx](../../frontend/src/App.tsx), [Workspace.tsx](../../frontend/src/Workspace.tsx) | Incorporar la mesa al contexto del analista. |
| Caso, variante, rango y snapshot ejecutable | [Decisión TS-3](../series_tiempo/iter3/decision_record_ts3_variant_semantics.md), [input_variants.py](../../app/input_variants.py) | Reutilizar validación, materialización y linaje. |
| Identidad común de componentes | [linkable_objects.py](../../app/linkable_objects.py) | Referenciar objetos existentes, evitando deduplicación por nombre. |
| Series locales de objeto y revisiones | [object_time_series.py](../../app/object_time_series.py), [especificación TS-7](../series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md) | Editar/publicar por el recorrido canónico, sin crear otro catálogo. |
| Diagrama hidráulico y parámetros | [Tracker hidráulico](../hydro_diagram/iter1/issues/tracker_hydro_diagram_iter1.md), [checkpoint de BBDD](../db/hydro_diagram_db_checkpoint.md) | Reutilizar activos, curvas, conexiones y validación. |
| Ejecuciones y resultados | [runner.py](../../app/runner.py), [results.py](../../app/results.py), [RunResults.tsx](../../frontend/src/RunResults.tsx) | Reutilizar worker, resultados indexados y fallback a artefactos. |
| Historia matemática de resultados | [Decisión TS-4](../series_tiempo/iter4/decision_record_ts4_result_semantics.md) | Resultados asociados al run y snapshot; nunca al estado mutable actual. |
| Simulación hidráulica por fechas | [hydraulic_simulation.py](../../app/hydraulic_simulation.py), [HydraulicSimulationForm.tsx](../../frontend/src/hydro/HydraulicSimulationForm.tsx) | Adaptar preparación, cobertura, objetivo y huella de preparación. |
| Progreso de ejecución | [run_progress.py](../../app/run_progress.py), [RunProgress.tsx](../../frontend/src/RunProgress.tsx) | Compartir presentación del avance real. |
| Fachadas externas con permisos propios | [Arquitectura de configuración](../capa_configuracion/architecture_configuration_layer_final.md) | No convertir la consola externa en un editor hidráulico ni ampliar sus permisos. |
| Motor eléctrico e hidráulico | [system_dispatch.jl](../../src/system_dispatch.jl) | Resolver según las capacidades reales de cada contrato de modelo. |

La simulación hidráulica y el progreso tienen archivos nuevos o modificados sin
commit en el árbol actual. Las entregas que los reutilicen deben comprobar su
integración efectiva y coordinarse con ese trabajo; no asumir que están disponibles
solo porque aparecen en este checkout.

## Límite del modelo y componentes

Los caminos eléctricos one-bus v1/v2 y la red hidráulica v3 no deben tratarse como
un mismo contrato por compartir pantalla. La inspección muestra preparadores
distintos; no demuestra que una red v3 pueda cooptimizar BESS, demanda y renovables
en un único balance eléctrico.

La primera entrega debe documentar la matriz de capacidades y resolver si el caso
objetivo necesita esa cooptimización. Si la necesita y no existe, debe incorporar
una entrega vertical de extensión del motor antes de declarar completa la
ejecución mixta. Ejecutar dos modelos por separado y sumar sus indicadores no
satisface ese requisito.

Mientras tanto, las entregas propuestas cubren la mesa para los contratos
ejecutables existentes, con tipos admitidos, errores explícitos e identidad de la
fuente. No se fabricarán resultados para componentes no modelados.

La vista general puede mezclar componentes del contexto activo. Las centrales,
embalses, tramos y unidades usan las identidades del dominio, preservando la
distinción entre el activo base y su participación en un caso. Dos componentes
con igual nombre no se fusionan.

## Contratos funcionales propuestos

### Configuración de la mesa

La configuración contiene versión de esquema, revisión, usuario, caso, orden de
pestañas, distribución por pestaña y paneles. Cada panel referencia un componente,
series, título y modo gráfico/tabla. No contiene copias de muestras ni de outputs.

Guardar requiere una revisión esperada; un cambio concurrente informa conflicto
sin sobrescribir otra configuración. Ocultar una vista no desactiva un activo.
Un componente eliminado deja una vista identificable como no disponible; no se
reasigna por coincidencia de nombre.

### Series y unidades

El catálogo de la mesa devuelve identidad, nombre, unidad, rol, origen, revisión,
capacidad de edición y vinculación al modelo. Distingue:

- entrada editable o de solo lectura;
- salida calculada asociada a una ejecución;
- parámetro escalar;
- serie manual de referencia que no participa en el modelo.

La UI no ofrece un input editable para un output del solver. La matriz de
compatibilidad de señales decide qué puede vincularse a un componente. Varias
unidades en un panel se representan con subgráficos/ejes claramente separados,
sin convertir implícitamente MW, MWh, %, m³/s, hm³ o m.

### Significado de antes/después

| Tipo de dato | Antes | Después | Diferencia |
| --- | --- | --- | --- |
| Entrada exógena | Revisión usada en el snapshot ejecutado | La misma entrada, si el modelo no la modifica | Cero o sin cambio; no inventar una mejora. |
| Salida con referencia compatible | Resultado de una ejecución de referencia identificada, o serie operativa admitida | Resultado de la nueva ejecución | Solo entre la misma magnitud, objeto, unidad e intervalos. |
| Salida sin referencia | «Sin referencia previa» | Resultado disponible al completar el run | No disponible, nunca cero como sustituto. |
| Parámetro inicial escalar | Valor inicial del snapshot | No es automáticamente una trayectoria temporal | No se compara contra una serie como si ambas fueran equivalentes. |
| Serie manual sin binding | Serie de apoyo | «No participa en esta simulación» | No aplicable. |

En cada panel se identifica de qué revisión/run proviene cada lado. El contexto
«antes» se congela al lanzar la ejecución; no se reconstruye consultando series
editadas después. Si cambian datos o fechas, se marca el resultado como histórico
o desactualizado para la preparación actual, conservando el run original.

Este contrato corrige una simplificación intencional del HTML: allí todas las
series tenían números «antes» inventados y los resultados se borraban en memoria.
Las capturas no autorizan esos comportamientos en producción.

### Fechas y ejecución

- La UI puede mostrar fechas finales inclusivas, pero el contrato de ejecución
  usa intervalos explícitos [inicio, fin). La zona horaria es visible.
- No asumir que cada fecha local tiene 24 horas. Validar cambios de hora,
  duración, límites, huecos, solapamientos y cobertura de cada entrada.
- El límite de siete días y el paso fijo de una hora pertenecen al demo. La mesa
  real respeta las capacidades/límites del backend; no los copia sin decisión.
- El camino por variantes exige la compatibilidad temporal vigente. El camino
  hidráulico tiene preparación con remuestreo explícito. La UI no aplica un
  remuestreo silencioso para hacer compatibles ambos.
- Guardar, validar y materializar antes de encolar; rechazar preparación obsoleta
  también en el servidor. Un doble clic o reintento no debe generar runs duplicados.
- Mostrar cola, ejecución, éxito, fallo y problemas de conexión. Recuperar el run
  en curso al recargar; los resultados no se ofrecen antes del éxito.
- Exponer objetivo económico/energético, CMg y valor del agua cuando el contrato
  hidráulico los requiera, sin reducir la preparación a dos fechas.

### Edición y componentes nuevos

Las ediciones producen revisiones auditables a través del mecanismo canónico
vigente. Se muestra alcance y efecto sobre consumidores compartidos antes de
guardar; conflictos, permisos y validaciones se comprueban en servidor.

Crear una central o un embalse reutiliza las validaciones del dominio, conexiones
y parámetros mínimos. Un activo incompleto puede quedar como borrador, pero no
se presenta como ejecutable. El usuario puede completarlo mediante un panel de
edición dentro de la mesa, reutilizando los editores existentes.

Una serie manual se publica con metadatos, unidad y contrato temporal. Solo
participa en el solver al vincularse a una señal admitida. Agregar una ecuación,
un tipo de activo arbitrario o un nuevo solver no es una opción de ese formulario.

## Historias de usuario

| ID | Necesidad |
| --- | --- |
| HU-01 | Abrir el caso correcto y descubrir sus componentes reales. |
| HU-02 | Configurar pestañas, distribución y paneles; recuperarlos después. |
| HU-03 | Ver una o varias series como gráficos o tablas con unidades correctas. |
| HU-04 | Editar entradas permitidas conservando versiones y procedencia. |
| HU-05 | Elegir fechas y ejecutar desde la mesa con avance recuperable. |
| HU-06 | Comparar antes/después con referencias y diferencias válidas. |
| HU-07 | Incorporar o editar centrales y embalses del modelo. |
| HU-08 | Crear series manuales de apoyo y vincular entradas admitidas. |
| HU-09 | Recuperar ejecuciones y exportar los datos que se están comparando. |
| HU-10 | Usar la mesa con teclado, tamaños de pantalla distintos y estados claros. |
| HU-11 | Mantener permisos, aislamiento entre casos y compatibilidad existente. |

## Entregas y secuencia

El [tracker](tracker.md) enumera entregas completas, no tareas separadas de
«hacer BBDD», «hacer API» y «hacer frontend». Cada ticket AFK incluye la
persistencia o lectura necesaria, contrato público, experiencia de usuario y
validación del comportamiento.

Orden recomendado:

1. Acordar decisiones y pruebas; conectar el primer caso real.
2. Configurar vistas y ampliar familias de componentes; habilitar edición real.
3. Ejecutar los caminos eléctrico e hidráulico y comparar sus resultados.
4. Incorporar activos/series manuales y recuperar el historial.
5. Validar la experiencia completa frente a las capturas y habilitar la entrada
   del producto.

No se estiman fechas sin medir el primer recorrido real. Las dependencias
permiten tomar trabajo independiente; no asignan automáticamente agentes.

## Definición de terminado por entrega

- Camino completo demostrable con datos reales de prueba, no con el HTML.
- Lecturas y mutaciones pasan por las interfaces públicas y permisos del dominio.
- Prueba TDD en una interfaz previamente acordada, con evidencia rojo → verde.
- Si cambia un contrato: OpenAPI/tipos sincronizados y compatibilidad revisada.
- Si cambia persistencia: migración y documentación correspondientes, incluyendo
  checkpoint hidráulico cuando se afecten sus tablas.
- Estados vacío, carga, error y conflicto incluidos en el comportamiento nuevo.
- Criterios de aceptación marcados, evidencia y resultado registrados en el tracker.
- Cambios ajenos del árbol de trabajo preservados.

## Fuera del corte propuesto

Publicación externa, rediseño del portal cliente, scheduling, edición colaborativa
en tiempo real, diseñador de ecuaciones arbitrarias y reemplazo general del solver.
La necesidad de un modelo mixto no se descarta aquí: se resuelve expresamente en
la primera entrega y amplía el plan si forma parte del caso objetivo.

Las pruebas y regresión visual se detallan en [validacion_tdd.md](validacion_tdd.md).
