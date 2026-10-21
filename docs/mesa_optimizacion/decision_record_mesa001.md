# MESA-001 · Alcance y contratos observables

Fecha: 2026-10-20. Responsable: Codex.
Estado: aceptado por el usuario el 2026-10-20; MESA-001 Done.
Issue: [MESA-001](issues/MESA-001-acordar-alcance-y-contratos.md).
Base inspeccionada: commit `817bf25`; árbol inicialmente limpio.

## Decisión de alcance aceptada

El usuario respondió «confirmo» el 2026-10-20 al registro propuesto con los modelos
actuales. Se conservan las 14 entregas: una mesa para consultar, preparar y
ejecutar los contratos existentes, seleccionando el caso/modelo correspondiente.
Esto incluye cooptimización eléctrica con **hidro simple v2**, y ejecución de
**red hidráulica v3** por su camino propio. No incluye cooptimizar una red v3
con BESS, demanda y renovables en un único balance eléctrico.

La alternativa de exigir cooptimización de red v3 queda fuera del primer corte
aprobado. Si se solicita en el futuro, requerirá una entrega vertical de motor
con entradas, balance común, objetivo, resultados por entidad y pruebas físicas
públicas, además de actualizar las dependencias de ejecución y comparación.

Compartir pestañas no prueba que los objetos pertenezcan al mismo modelo.
Tampoco ejecutar dos modelos y sumar indicadores constituye cooptimización.

## Diseño, contexto y persistencia acordados

1. Usar **A · Paneles**, una pantalla con pestañas horizontales y matriz 2×2;
   B/C permanecen como referencias. Mantener gráfico/tabla por panel, controles
   de preparación y comparación dentro de la mesa. Admitir 1×1, 1×2, 2×2 y 2×3;
   reducir la distribución conserva los paneles ocultos.
2. Incorporar la mesa al área interna `AnalystRoot`, para `analyst`/`admin`,
   desde el escenario. Ruta acordada para MESA-002:
   `/react/scenarios/:scenarioId/mesa`, con caso/variante explícitos y validados
   contra el escenario. Resolver el proyecto desde el contexto autorizado;
   parámetros URL y selección guardada no conceden acceso.
3. Mantener un contexto activo de proyecto, escenario, caso y preparación.
   El camino de variantes identifica `case_input_variant_id`; el camino
   hidráulico de simulación identifica su `source_scenario_version_id` v3 y sus
   opciones. No inventar una variante equivalente cuando ese camino no la usa.
   La UI debe distinguir ambos y no mezclar respuestas tardías al cambiar contexto.
4. Guardar preferencias por **usuario autenticado + caso**, con versión de
   esquema y revisión esperada. Cambiar variante del mismo caso puede conservar
   la disposición, reconsultando las series compatibles. No copiar muestras,
   resultados o parámetros matemáticos dentro de las preferencias. La persistencia
   se implementa en MESA-003; este registro no crea tablas ni endpoints.
5. Referenciar identidades del dominio: `linkable_object_id` y pertenencia al
   caso cuando corresponda, conservando el vínculo entre activo base, entidad de
   caso y entidad del resultado. Los nombres son etiquetas. Un objeto eliminado
   queda «No disponible»; no se sustituye por otro de igual nombre.
6. Reutilizar autorización interna, CSRF y permisos de cada recurso. La consola
   externa/portal conserva sus rutas y capacidades. MESA-002 debe probar identidad
   ajena y acceso externo con autenticación habilitada; los fixtures de API sin
   autenticación no demuestran aislamiento por sí solos.

Fuentes: [rutas React](../../frontend/src/App.tsx),
[frontera HTTP](../../app/main.py),
[identidades vinculables](../../app/linkable_objects.py),
[catálogo y series por objeto TS-7](../series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md).

## Matriz de capacidades comprobadas en el código

| Contrato | Combinaciones y límites actuales | Entrada y ejecución | Resultado observable |
| --- | --- | --- | --- |
| `bess_system_dispatch.v1` | Un bus/PCC, BESS y red; demanda y renovables opcionales. El normalizador exige al menos una batería y una red. No admite nodos hidro. | Caso/variante, bindings y períodos compatibles; snapshot inmutable y worker existente. | Carga/descarga/energía BESS, importación/exportación, demanda y uso/vertimiento renovable. |
| `bess_system_dispatch.v2` | Lo anterior más activos `hydro` simples, con embalse, aporte, curva de cota y generación lineal o por tramos. Su potencia sí participa en el mismo balance que BESS, carga, renovables y red. No representa la topología hidráulica v3. | Mismo despacho de un bus; los activos y límites deben satisfacer el contrato v2. | Potencia/caudal/volumen/cota hidro simple además de los resultados eléctricos. |
| `bess_system_dispatch.v3` | Red hidráulica con embalse, tramos, central y unidad; al menos un embalse, una central y una unidad. Generación, sin bombeo/reversibilidad ni potencia dependiente de la altura. Admite tránsito `none`/`fixed_delay` bajo validación y rechaza ciclos. | Versión promovida, rango, resolución, objetivo `energy`/`market_value`, CMg cuando aplica, valor del agua y gap; preview con huella y ejecución de snapshot. También existe el camino de variantes hidráulicas, con su contrato temporal propio. | Resultados hidráulicos por entidad, energía e ingresos según objetivo. No modela BESS, demanda o renovables en un balance eléctrico compartido. |

Evidencia en [system_dispatch.jl](../../src/system_dispatch.jl):
`validate_system_case` limita hidro a v2; `normalize_system_case` exige BESS/red;
`build_system_dispatch_model` incorpora `hydro_power_mw` al balance eléctrico;
`run_system_case` deriva v3 a `run_hydraulic_v3_system_case`, que construye un
modelo hidráulico distinto. `validate_hydraulic_v3_system_case_document` define
los tipos y restricciones v3. No basta adjuntar campos eléctricos a un JSON v3:
la mesa debe rechazar una combinación no soportada, sin insinuar que se optimizó.

La tabla describe capacidad del motor, no una mesa ya implementada. La nueva
consulta, edición, idempotencia y recuperación desde la mesa siguen perteneciendo
a MESA-002–013.

## Contrato de entradas, referencias y diferencias

| Dato | Antes | Después | Δ |
| --- | --- | --- | --- |
| Entrada exógena | Revisión y valores del snapshot ejecutado. Antes de ejecutar se identifica como preparación actual. | Misma entrada si el modelo no la modifica. | Cero solo si ambos lados existen y coinciden; no es una mejora. |
| Salida con referencia | Run exitoso elegido explícitamente, del mismo caso y con identidad, magnitud, unidad e intervalos compatibles. | Run exitoso seleccionado. | Después − antes, con ambos orígenes visibles. |
| Salida sin referencia | «Sin referencia previa». | Output disponible al completar el run. | No disponible; nunca reemplazar ausencia con cero. |
| Parámetro inicial | Escalar del snapshot, por ejemplo energía o volumen inicial. | No equivale a una trayectoria calculada. | No se calcula entre escalar y serie. |
| Serie manual sin binding | Serie de apoyo con revisión identificada. | «No participa en esta simulación». | No aplicable. |

El primer corte usa runs compatibles como referencia de outputs. Una serie
operativa solo podrá servir como referencia si una entrega define y valida
explícitamente ese contrato; no se ofrece como comparación arbitraria.

No comparar solo por etiqueta o posición. Verificar caso, identidad y
compatibilidad de topología, magnitud, unidad, inicio y duración de cada intervalo.
Las unidades distintas se separan en ejes/subgráficos; no hay conversiones ni
remuestreo implícitos para calcular Δ. Tabla y gráfico consumen la misma selección.

Editar entradas actuales no cambia la comparación de un run anterior: conserva
snapshot, revisiones y resultados, e identifica la preparación actual como
pendiente/desactualizada. Reutilizar el índice de resultados por run y su fallback
a artefactos, sin duplicarlos en el catálogo editable.

Estos contratos respetan las decisiones aceptadas
[TS-3](../series_tiempo/iter3/decision_record_ts3_variant_semantics.md) y
[TS-4](../series_tiempo/iter4/decision_record_ts4_result_semantics.md).

## Fechas y ejecución

- Usar `[inicio, fin)` con zona visible. Una fecha final inclusiva se convierte
  al siguiente inicio de día local; no sumar siempre 24 horas en cambios de hora.
- Variantes: compatibilidad exacta de períodos, sin remuestreo silencioso.
  Preparador hidráulico: remuestreo explícito que integra promedios ponderados de
  aportes/precios y usa máximos para caudales mínimos. Presentar la transformación
  antes de ejecutar; su límite actual es 1–100000 pasos completos, no siete días.
- `market_value` requiere CMg cubriendo el rango. `energy` requiere valores
  terminales del agua iguales a cero en la API de preparación. Mantener unidades
  visibles y no combinar MWh y USD como si fueran la misma magnitud.
- Congelar versión fuente, parámetros, revisiones y rango. Revalidar vigencia
  en servidor; una huella hidráulica distinta devuelve 409.
- Reutilizar cola, worker, estado y resultados. Los porcentajes ficticios del
  HTML no son progreso: mostrar etapa real y gap solo si el solver lo reporta.
- La idempotencia completa exigida por MESA-007/008 debe comprobarse en esas
  entregas. La huella de preparación hidráulica no es una clave de idempotencia:
  el endpoint actual crea una versión y un run por cada envío válido.

Fuente: [preparación hidráulica](../../app/hydraulic_simulation.py),
[variantes](../../app/input_variants.py), [worker](../../app/runner.py).

## Integración existente y demostración

La advertencia del plan sobre archivos hidráulicos sin commit quedó obsoleta.
`d206e78` (`feat(hydraulics): prepare economic simulations with live progress`)
ya es ancestro del HEAD inspeccionado e incluye API, motor, tipos, formulario,
progreso y pruebas. Se confirmó integración local; no se afirma publicación remota.

`create_app` registra las rutas de simulación; `ScenarioVersionDetailView` monta
`HydraulicSimulationForm` para v3; `RunDetailView` monta `RunProgressPanel`.
El formulario actual navega al detalle del run: MESA-008 debe adaptar ese recorrido
para permanecer en la mesa. No hay una dependencia pendiente de otro checkout.

Ejemplo eléctrico: [hybrid_system](../../data/cases/hybrid_system/system_case.json)
contiene BESS, solar, red y demanda con cuatro períodos horarios. La demanda
«antes» procede del snapshot; carga/descarga BESS y uso renovable requieren
outputs. Sin otro run compatible no existe una trayectoria «antes» de esas salidas.

Ejemplo hidráulico: [fixture v3](../../tests/fixtures/reg002_hydraulic.json),
preparado por [la prueba HTTP](../../tests/test_hydraulic_simulation.py), usa
embalse `reservoir`, central `plant`, unidad `unit`, aportes [2, 4, 6, 8] m³/s y
CMg [10, 20, 80, 100] USD/MWh. A resolución de dos horas se obtienen aportes
[3, 7] y CMg [15, 90]. El embalse parte en 10 hm³: eso es un parámetro, no una
serie histórica. El caso económico sin valor terminal espera 120 MWh y 6300 USD;
con 50000 USD/hm³ espera conservar agua, 0 MWh y volumen final 10.072 hm³.

Los números anteriores son fixtures de prueba, no datos operativos del usuario
ni los valores inventados del prototipo. El ticket registra 29 pruebas Python
verificadas (dos integraciones reales con Julia), seis regresiones React y
ejecuciones CLI v1/v2 con resultado OPTIMAL. También contiene los comandos y
el fallo inicial de acceso al entorno Julia, resuelto al repetir fuera del sandbox.

## Validación y cierre

S1 navegador y S2 HTTP, más S3 público del motor si cambia su contrato, ya fueron
confirmadas por el usuario. No se solicita otro acuerdo ni se añade otra interfaz.
MESA-001 dice «No escribir pruebas como parte de este trabajo de planificación».
Por tanto, se ejecutan regresiones existentes para comprobar la base; no se
presentan como evidencia rojo → verde de una capacidad nueva.

MESA-002 iniciará el ciclo TDD en S1/S2 con demanda conocida, alternancia
tabla/gráfico y recarga, y luego identidad/permisos en otro ciclo. Un fallo de
infraestructura o la ausencia de baseline visual no cuenta como rojo funcional.

La conformidad humana del 2026-10-20 cierra MESA-001 en **Done**, con los contratos
de este registro aceptados. MESA-002 permanece **Todo**, con su dependencia
satisfecha. Se conservan las 14 entregas, su grafo y las referencias PNG/HTML.
